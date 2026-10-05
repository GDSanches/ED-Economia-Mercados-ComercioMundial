"""Carrega runs completed do Bronze (MinIO) para raw_staging.world_bank_pages."""

import argparse
import json
import os
import sys
from datetime import datetime

import psycopg2
from psycopg2.extras import Json

from src.ingestion.world_bank.config import BUCKET
from src.storage.minio import PROJECT_ROOT, create_storage_client

SQL_DIR = PROJECT_ROOT / "sql" / "raw_staging"

INSERT_SQL = """
    INSERT INTO raw_staging.world_bank_pages (
        run_id, dataset, indicator_id, page_number, pages_expected,
        payload, source, source_url, object_key, extracted_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (run_id, dataset, page_number) DO NOTHING
"""


class RunNotCompletedError(Exception):
    """O manifest existe, mas o run não terminou com status completed."""


def create_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def read_json_object(storage, key: str):
    try:
        response = storage.get_object(Bucket=BUCKET, Key=key)
    except storage.exceptions.NoSuchKey:
        raise FileNotFoundError(f"Objeto não encontrado no MinIO: s3://{BUCKET}/{key}") from None

    data = json.loads(response["Body"].read())
    return data, response


def list_manifest_keys(storage, dataset: str | None = None):
    """Gera as chaves de todos os manifests (de um dataset ou de todos)."""
    prefix = f"world_bank/{dataset}/" if dataset else "world_bank/"

    paginator = storage.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith("/manifest.json"):
                yield obj["Key"]


def find_manifest_key(storage, dataset: str, run_id: str) -> str:
    suffix = f"run_id={run_id}/manifest.json"
    for key in list_manifest_keys(storage, dataset):
        if key.endswith(suffix):
            return key

    raise FileNotFoundError(
        f"Manifest não encontrado para dataset={dataset}, run_id={run_id}"
    )


def validate_manifest(manifest: dict, dataset: str, run_id: str) -> int:
    if manifest.get("run_id") != run_id or manifest.get("dataset") != dataset:
        raise ValueError("Manifest não corresponde ao run/dataset solicitado.")

    status = manifest.get("status")
    if status != "completed":
        raise RunNotCompletedError(
            f"Run {run_id} ({dataset}) está com status '{status}'. Não será carregado."
        )

    pages_expected = manifest.get("pages_expected")
    if not isinstance(pages_expected, int) or pages_expected < 1:
        raise ValueError(f"pages_expected inválido no manifest: {pages_expected!r}")

    if manifest.get("pages_saved") != pages_expected:
        raise ValueError(
            f"Manifest inconsistente: pages_saved={manifest.get('pages_saved')} "
            f"!= pages_expected={pages_expected}"
        )

    return pages_expected


def validate_page(payload, page_number: int, pages_expected: int) -> None:
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[0], dict):
        raise ValueError(f"Página {page_number}: formato inesperado (esperado [header, registros]).")

    header, records = payload

    if header.get("page") != page_number:
        raise ValueError(f"Arquivo da página {page_number} contém page={header.get('page')}.")

    if header.get("pages") != pages_expected:
        raise ValueError(
            f"Página {page_number}: header diz pages={header.get('pages')}, "
            f"manifest diz {pages_expected}."
        )

    if records is not None and not isinstance(records, list):
        raise ValueError(f"Página {page_number}: registros não são uma lista.")


def read_extracted_at(response: dict, object_key: str) -> datetime:
    value = response["Metadata"].get("extracted-at")
    if value is None:
        raise ValueError(
            f"{object_key} não tem o metadado extracted-at "
            "(gravado antes de a ingestão registrar o horário da extração)."
        )
    return datetime.fromisoformat(value)


def build_row(manifest: dict, page_number: int, pages_expected: int,
              payload, response: dict, object_key: str) -> tuple:
    return (
        manifest["run_id"],                          # run_id
        manifest["dataset"],                         # dataset
        manifest["indicator_id"],                    # indicator_id
        page_number,                                 # page_number
        pages_expected,                              # pages_expected
        Json(payload),                               # payload -> JSONB
        manifest["source"],                          # source
        response["Metadata"].get("source-url"),      # source_url (None em runs antigos)
        object_key,                                  # object_key
        read_extracted_at(response, object_key),     # extracted_at (horário da resposta da API)
    )


def ensure_schema(conn) -> None:
    # Aplica as migrations em ordem (001, 002, ...). Cada arquivo pode rodar mais de uma vez.
    with conn:
        with conn.cursor() as cur:
            for sql_file in sorted(SQL_DIR.glob("*.sql")):
                cur.execute(sql_file.read_text(encoding="utf-8"))


def get_loaded_run_ids(conn) -> set[str]:
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT run_id::text FROM raw_staging.world_bank_pages")
            return {row[0] for row in cur.fetchall()}


def load_run(storage, conn, dataset: str, run_id: str,
             manifest_key: str | None = None) -> tuple[int, int]:
    # 1. Localizar e ler o manifest (quem já sabe a chave pode passá-la direto)
    if manifest_key is None:
        manifest_key = find_manifest_key(storage, dataset, run_id)
    manifest, _ = read_json_object(storage, manifest_key)

    # 2. Regra de ouro: só runs completed passam daqui
    pages_expected = validate_manifest(manifest, dataset, run_id)

    # 3. FASE 1 (só leitura): baixar e validar TODAS as páginas
    run_prefix = manifest_key.rsplit("/", 1)[0]
    rows = []
    for page_number in range(1, pages_expected + 1):
        object_key = f"{run_prefix}/page={page_number:04d}.json"
        payload, response = read_json_object(storage, object_key)
        validate_page(payload, page_number, pages_expected)
        rows.append(build_row(manifest, page_number, pages_expected, payload, response, object_key))
        print(f"  página {page_number}/{pages_expected} validada")

    # 4. FASE 2 (escrita): tudo em UMA transação
    inserted = 0
    with conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(INSERT_SQL, row)
                inserted += cur.rowcount

    skipped = len(rows) - inserted
    return inserted, skipped


def load_pending_runs(storage, conn, dataset: str | None = None) -> list[str]:
    """Carrega todo run completed do MinIO que ainda não está no raw_staging.

    Retorna a lista de runs que falharam ao carregar.
    """
    loaded = get_loaded_run_ids(conn)
    failures = []

    for manifest_key in list_manifest_keys(storage, dataset):
        manifest, _ = read_json_object(storage, manifest_key)
        run_id, run_dataset = manifest.get("run_id"), manifest.get("dataset")

        if run_id in loaded:
            continue
        if manifest.get("status") != "completed":
            print(f"Ignorado: {run_dataset} {run_id} (status '{manifest.get('status')}')")
            continue

        print(f"Carregando {run_dataset} {run_id}")
        try:
            inserted, _ = load_run(storage, conn, run_dataset, run_id, manifest_key)
            print(f"  {inserted} página(s) inserida(s)")
        except Exception as error:
            failures.append(f"{run_dataset} {run_id}")
            print(f"  FALHA: {type(error).__name__}: {error}")

    return failures


def parse_args():
    parser = argparse.ArgumentParser(
        description="Carrega runs do Bronze para raw_staging. "
                    "Sem argumentos, carrega todos os runs completed pendentes."
    )
    parser.add_argument("--dataset", help="Restringe a um dataset. Ex.: gdp, inflation")
    parser.add_argument("--run-id", help="Carrega um run específico (exige --dataset)")
    args = parser.parse_args()
    if args.run_id and not args.dataset:
        parser.error("--run-id exige --dataset")
    return args


def main() -> None:
    args = parse_args()
    storage = create_storage_client()
    conn = create_pg_connection()

    try:
        ensure_schema(conn)

        if args.run_id:
            print(f"Carregando dataset={args.dataset} run_id={args.run_id}")
            inserted, skipped = load_run(storage, conn, args.dataset, args.run_id)
            print(f"Concluído: {inserted} página(s) inserida(s), {skipped} já existia(m).")
            return

        failures = load_pending_runs(storage, conn, args.dataset)
        if failures:
            print(f"Runs com falha: {', '.join(failures)}")
            sys.exit(1)
        print("Staging em dia: todos os runs completed estão no raw_staging.")
    except RunNotCompletedError as error:
        print(f"REJEITADO: {error}")
        sys.exit(2)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
