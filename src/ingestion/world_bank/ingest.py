import argparse
import json
from datetime import datetime, timezone
from uuid import uuid4

from src.storage.minio import create_storage_client

from .cliente import request_page
from .config import BUCKET, COUNTRY, DATASETS, DatasetConfig

 

def upload_manifest(storage, key: str, manifest: dict) -> None:
	body = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
	storage.put_object(
		Bucket=BUCKET,
		Key=key,
		Body=body,
		ContentType="application/json",
	)


def ingest_dataset(dataset: DatasetConfig, storage) -> str:
	ingestion_time = datetime.now(timezone.utc)
	run_id = str(uuid4())

	run_prefix = "/".join(
		(
			"world_bank",
			dataset.name,
			f"year={ingestion_time:%Y}",
			f"month={ingestion_time:%m}",
			f"day={ingestion_time:%d}",
			f"run_id={run_id}",
		)
	)
	manifest_key = f"{run_prefix}/manifest.json"
	manifest = {
		"run_id": run_id,
		"source": "world_bank",
		"dataset": dataset.name,
		"indicator_id": dataset.indicator_id,
		"country": COUNTRY,
		"status": "started",
		"started_at": ingestion_time.isoformat(),
		"completed_at": None,
		"pages_expected": None,
		"pages_saved": 0,
		"error": None,
	}
	upload_manifest(storage, manifest_key, manifest)

	try:
		first_response = request_page(dataset.path, page=1, extra_params=dataset.params)
		first_extracted_at = datetime.now(timezone.utc)
		payload = first_response.json()
		if (
			not isinstance(payload, list)
			or len(payload) < 2
			or not isinstance(payload[0], dict)
			or "pages" not in payload[0]
		):
			raise ValueError("Formato inesperado na resposta da API do Banco Mundial.")

		total_pages = int(payload[0]["pages"])
		if total_pages < 1:
			raise ValueError("A API retornou um total de páginas inválido.")
		manifest["pages_expected"] = total_pages
		upload_manifest(storage, manifest_key, manifest)

		for page in range(1, total_pages + 1):
			if page == 1:
				response, extracted_at = first_response, first_extracted_at
			else:
				response = request_page(dataset.path, page=page, extra_params=dataset.params)
				extracted_at = datetime.now(timezone.utc)

			object_key = f"{run_prefix}/page={page:04d}.json"
			storage.put_object(
				Bucket=BUCKET,
				Key=object_key,
				Body=response.content,
				ContentType="application/json",
				Metadata={
					"source-url": response.url,
					"extracted-at": extracted_at.isoformat(),
				},
			)
			manifest["pages_saved"] = page
			upload_manifest(storage, manifest_key, manifest)
			print(f"Página {page}/{total_pages} enviada ao MinIO.")

		manifest["status"] = "completed"
		manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
		upload_manifest(storage, manifest_key, manifest)
	except (Exception, KeyboardInterrupt) as error:
		manifest["status"] = "failed"
		if isinstance(error, KeyboardInterrupt):
			manifest["error"] = "KeyboardInterrupt: execução interrompida pelo usuário (Ctrl+C)"
		else:
			manifest["error"] = f"{type(error).__name__}: {error}"
		try:
			upload_manifest(storage, manifest_key, manifest)
		except Exception as manifest_error:
			print(f"Não foi possível atualizar o manifest: {manifest_error}")
		raise

	print(f"Dataset {dataset.name} salvo em s3://{BUCKET}/{run_prefix}/")
	print(f"Páginas salvas: {manifest['pages_saved']}")
	return run_id



def parse_args():
	parser = argparse.ArgumentParser(
		description="Ingere datasets do World Bank no MinIO. Sem argumentos, ingere todos."
	)
	parser.add_argument(
		"--dataset",
		action="append",
		choices=[dataset.name for dataset in DATASETS],
		help="Ingere só este dataset (pode ser repetido).",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	selected = [d for d in DATASETS if not args.dataset or d.name in args.dataset]

	storage = create_storage_client()
	failed_datasets = []

	for dataset in selected:
		try:
			ingest_dataset(dataset, storage)
		except Exception as error:
			failed_datasets.append(dataset.name)
			print(f"Falha no dataset {dataset.name}: {error}")

	if failed_datasets:
		failed_names = ", ".join(failed_datasets)
		raise RuntimeError(f"Falha na ingestão dos datasets: {failed_names}")


if __name__ == "__main__":
	main()
