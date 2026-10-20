import time
import argparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import BASE_URL, DATASETS, ENDPOINT, MIN_INTERVAL_SECONDS, PERIOD, TIMEOUT, query_params
from .validation import (
    RejectedResponseError,
    ensure_complete,
    ensure_not_empty,
    ensure_within_limit,
    validate_records,
)

RETRY = Retry(
    total=5,
    connect=5,
    read=5,
    status=5,
    backoff_factor=2,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
    respect_retry_after_header=True,
)

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=RETRY))


class ComtradeAPIError(Exception):
    """A API respondeu, mas com erro ou num formato fora do contrato."""


_last_call_at = 0.0


def _throttle() -> None:
    # Intervalo mínimo entre chamadas deste processo. Entre execuções concorrentes,
    # quem serializa é o Pool do orquestrador (contrato, seção 8.6).
    global _last_call_at
    wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()


def _get(params: dict) -> tuple[dict, requests.Response]:
    _throttle()
    response = session.get(f"{BASE_URL}/{ENDPOINT}", params=params, timeout=TIMEOUT)

    try:
        body = response.json()
    except ValueError:
        raise ComtradeAPIError(
            f"HTTP {response.status_code}: resposta não é JSON: {response.text[:200]!r}"
        ) from None

    # O envelope do contrato é um objeto JSON ({elapsedTime, count, data, error}, seção 4.1).
    # Um JSON válido em outro formato (lista, texto, número) não tem os campos esperados.
    if not isinstance(body, dict):
        raise ComtradeAPIError(
            f"HTTP {response.status_code}: envelope deveria ser um objeto JSON, veio {type(body).__name__}"
        )

    # Erros vêm como HTTP 4xx com a mensagem no campo "error" (contrato, seção 4.4).
    if response.status_code != 200 or body.get("error"):
        raise ComtradeAPIError(f"HTTP {response.status_code}: {body.get('error') or 'sem mensagem'}")

    return body, response


def count_records(params: dict) -> tuple[int, requests.Response]:
    """Total de registros da consulta, sem os dados (countOnly)."""
    body, response = _get({**params, "countOnly": "true"})
    count = body.get("count")
    if not isinstance(count, int) or count < 0:
        raise ComtradeAPIError(f"countOnly sem contagem válida: {count!r}")
    return count, response


def fetch_records(params: dict) -> tuple[list[dict], requests.Response]:
    """Registros da consulta. Pode vir truncada: compare com count_records()."""
    body, response = _get(params)
    records = body.get("data")
    if not isinstance(records, list):
        raise ComtradeAPIError(f"'data' deveria ser uma lista, veio {type(records).__name__}")
    return records, response


def main() -> None:
    # Teste manual do cliente, isolado da ingestão e da DAG.
    parser = argparse.ArgumentParser(description="Teste manual do cliente do UN Comtrade.")
    parser.add_argument("--cmd-code", default="TOTAL", help="Produto (ex.: AG2 para testar o limite)")
    parser.add_argument("--period", default=PERIOD, help="Ano (ex.: 2030 para testar resposta vazia)")
    args = parser.parse_args()

    dataset = DATASETS[0]
    params = {**query_params(dataset, period=args.period), "cmdCode": args.cmd_code}

    expected_count, count_response = count_records(params)
    print(f"countOnly:        {expected_count} registros esperados")
    ensure_not_empty(expected_count)             # antes de baixar os dados
    ensure_within_limit(expected_count)          # antes de baixar os dados

    records, data_response = fetch_records(params)
    ensure_complete(expected_count, records)     # depois de baixar os dados
    validate_records(records, params)            # depois de baixar os dados

    world = next((r for r in records if r["partnerCode"] == 0), None)
    partners = sorted((r for r in records if r["partnerCode"] != 0), key=lambda r: -r["primaryValue"])

    print(f"Dataset:          {dataset.name}")
    print(f"Dados:            {data_response.url}")
    print(f"Completo:         {len(records)} de {expected_count} registros")
    if world:
        print(f"World:            US$ {world['primaryValue'] / 1e9:,.2f} bi")
    print("Maiores parceiros:")
    for r in partners[:5]:
        print(f"  {r['partnerCode']:>4} {r['partnerISO']:<4} {r['partnerDesc']:<20} US$ {r['primaryValue'] / 1e9:>7,.2f} bi")


if __name__ == "__main__":
    try:
        main()
    except RejectedResponseError as error:
        print(f"REJEITADO: {type(error).__name__}: {error}")
        raise SystemExit(1)