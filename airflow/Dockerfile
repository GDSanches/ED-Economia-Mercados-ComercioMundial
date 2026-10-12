FROM apache/airflow:3.3.2-python3.13

# dbt num virtualenv separado: as dependências do dbt e as do Airflow não se misturam.
RUN python -m venv /opt/airflow/dbt-venv \
 && /opt/airflow/dbt-venv/bin/pip install --no-cache-dir dbt-postgres==1.11.0
