"""Pipeline do World Bank orquestrado pelo Airflow.

Etapa atual: ingest_world_bank (API do World Bank → MinIO/Bronze).
A lógica da ingestão continua em src/; esta DAG só decide quando e como chamá-la.
"""

from datetime import datetime, timedelta

from airflow.sdk import dag, get_current_context, task

from src.ingestion.world_bank.config import DATASETS


@dag(
    dag_id="world_bank_pipeline",
    schedule=None,                      # manual até o pipeline completo estar na DAG
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,                  # nunca duas execuções do pipeline ao mesmo tempo
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["world_bank"],
)
def world_bank_pipeline():

    @task(
        max_active_tis_per_dagrun=3,            # no máximo 3 datasets baixando ao mesmo tempo
        execution_timeout=timedelta(minutes=30),
        map_index_template="{{ dataset_name }}",  # a UI mostra "gdp" em vez de "1"
    )
    def ingest_world_bank(dataset_name: str) -> str:
        # Imports dentro da task: o dag-processor relê este arquivo a cada ~30s,
        # e boto3/requests só precisam ser carregados quando a task executa.
        from src.ingestion.world_bank.ingest import ingest_dataset
        from src.storage.minio import create_storage_client

        get_current_context()["dataset_name"] = dataset_name

        dataset = next(d for d in DATASETS if d.name == dataset_name)
        return ingest_dataset(dataset, create_storage_client())

    @task(
        # Roda mesmo se algum dataset falhou na ingestão: os que completaram são
        # carregados. A DAG run continua marcada como falha, então o erro não some.
        trigger_rule="all_done",
        execution_timeout=timedelta(minutes=30),
    )
    def load_raw_staging() -> None:
        from src.staging.world_bank import create_pg_connection, ensure_schema, load_pending_runs
        from src.storage.minio import create_storage_client

        storage = create_storage_client()
        conn = create_pg_connection()
        try:
            ensure_schema(conn)
            failures = load_pending_runs(storage, conn)
        finally:
            conn.close()

        if failures:
            raise RuntimeError(f"Runs com falha na carga: {', '.join(failures)}")

    @task.bash(
        retries=0,                      # falha do dbt é determinística (teste ou SQL): repetir não ajuda
        execution_timeout=timedelta(minutes=30),
    )
    def dbt_build() -> str:
        # Pastas do projeto e de saída vêm das variáveis DBT_* do docker-compose.
        return "/opt/airflow/dbt-venv/bin/dbt build"

    ingested = ingest_world_bank.expand(dataset_name=[d.name for d in DATASETS])
    ingested >> load_raw_staging() >> dbt_build()
world_bank_pipeline()
