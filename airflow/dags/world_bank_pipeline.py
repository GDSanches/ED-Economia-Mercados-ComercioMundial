"""Pipeline do World Bank orquestrado pelo Airflow.

    ingest_world_bank (×9, mapeada)  →  load_raw_staging  →  dbt_build  →  check_ingestion_results
    API → MinIO (Bronze)                MinIO → Postgres     raw_staging     falha a execução se
                                                             → Silver        alguma ingestão falhou

A lógica continua em src/ e dbt/; esta DAG só decide quando, em que ordem
e o que fazer quando algo falha.
"""

from datetime import datetime, timedelta

from airflow.sdk import dag, get_current_context, task

from src.ingestion.world_bank.config import DATASETS

# Caminhos dentro do container (ver volumes e Dockerfile em airflow/).
DBT_BIN = "/opt/airflow/dbt-venv/bin/dbt"
DBT_PROJECT_DIR = "/opt/airflow/project/dbt"
DBT_ARTIFACTS_DIR = "/tmp/dbt"

# Ordem da lista = map_index de ingest_world_bank (0 = countries, 1 = gdp, ...).
DATASET_NAMES = [d.name for d in DATASETS]


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
        # carregados. Quem marca a execução como falha é check_ingestion_results.
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
        # O BashOperator executa num diretório temporário, então todos os caminhos são
        # explícitos: o comando não depende do diretório atual nem de variáveis DBT_*.
        # O projeto é montado somente leitura; os artefatos do dbt vão para /tmp.
        return (
            f"{DBT_BIN} build"
            f" --project-dir {DBT_PROJECT_DIR}"
            f" --profiles-dir {DBT_PROJECT_DIR}"
            f" --target-path {DBT_ARTIFACTS_DIR}/target"
            f" --log-path {DBT_ARTIFACTS_DIR}/logs"
        )

    @task(
        # O Airflow decide o resultado da execução pelas tasks terminais. Com load_raw_staging
        # em all_done, uma ingestão falha não chega a dbt_build, e a execução ficaria verde.
        # Esta task é a terminal que olha para todas as ingestões e falha se alguma falhou.
        trigger_rule="all_done",
        retries=0,
    )
    def check_ingestion_results() -> None:
        context = get_current_context()
        # No Airflow 3 as tasks não acessam o banco de metadados; get_task_states pergunta
        # ao api-server. Retorno: {run_id: {"ingest_world_bank_<map_index>": estado}}.
        states = context["ti"].get_task_states(
            dag_id=context["dag"].dag_id,
            task_ids=["ingest_world_bank"],
            run_ids=[context["run_id"]],
        )[context["run_id"]]

        failed = sorted(
            DATASET_NAMES[int(key.rsplit("_", 1)[1])]
            for key, state in states.items()
            if state != "success"
        )
        if failed:
            raise RuntimeError(f"Ingestão falhou para: {', '.join(failed)}")

        print(f"Todas as {len(states)} ingestões concluídas com sucesso.")

    ingested = ingest_world_bank.expand(dataset_name=DATASET_NAMES)
    built = ingested >> load_raw_staging() >> dbt_build()
    [ingested, built] >> check_ingestion_results()


world_bank_pipeline()
