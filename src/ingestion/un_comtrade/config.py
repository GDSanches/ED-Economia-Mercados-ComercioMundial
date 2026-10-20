from dataclasses import dataclass

BASE_URL = "https://comtradeapi.un.org"
# Pré-visualização pública (contrato, seção 2): sem chave, até 500 registros e
# 1 período por chamada. C = mercadorias, A = anual, HS = qualquer versão do HS
# (versões específicas como H6 devolvem resultado vazio neste endpoint).
ENDPOINT = "public/v1/preview/C/A/HS"
RECORD_LIMIT = 500
MIN_INTERVAL_SECONDS = 1.5      # entre chamadas deste processo (contrato, seção 8.6)
TIMEOUT = (10, 60)

SOURCE = "un_comtrade"
BUCKET = "bronze"

# Escopo do piloto (contrato, seção 1).
REPORTER_CODE = "76"            # Brasil, código numérico do Comtrade
PERIOD = "2023"


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    flow_code: str


DATASETS = (
    DatasetConfig("goods_exports_by_partner", "X"),
    DatasetConfig("goods_imports_by_partner", "M"),
)


def query_params(dataset: DatasetConfig, reporter_code: str = REPORTER_CODE, period: str = PERIOD) -> dict:
    """Parâmetros da consulta de um dataset (contrato, seção 3)."""
    return {
        "reporterCode": reporter_code,
        "period": period,
        "flowCode": dataset.flow_code,
        "cmdCode": "TOTAL",
        # Totais explícitos: sem eles a API já devolve os totais, mas isso não é documentado.
        "partner2Code": "0",
        "customsCode": "C00",
        "motCode": "0",
        "includeDesc": "true",
    }