"""Regras que decidem se uma resposta do UN Comtrade pode virar um snapshot completed.

Contrato: docs/data-contracts/un-comtrade.md (seções 4.2, 6 e 8.4). A API pode
truncar, devolver vazio ou registros fora do pedido sem sinalizar erro: estas
regras transformam esses casos em exceções.
"""

from .config import RECORD_LIMIT


class RejectedResponseError(Exception):
    """A resposta não pode virar um snapshot completed."""


class EmptyQueryError(RejectedResponseError):
    """A consulta não tem registros. Não pode substituir um snapshot válido."""


class IncompleteQueryError(RejectedResponseError):
    """A consulta não pode ser obtida, ou não foi obtida, de forma completa."""


class QueryExceedsLimitError(IncompleteQueryError):
    """O total da consulta passa do limite do endpoint: a resposta viria truncada."""


class RecordCountMismatchError(IncompleteQueryError):
    """A quantidade recebida difere do total informado pelo countOnly."""


class InvalidRecordError(RejectedResponseError):
    """Algum registro não tem a estrutura esperada ou não corresponde ao que foi pedido."""


# Campos que as camadas seguintes usam (chave lógica e valor), com o tipo esperado.
REQUIRED_FIELDS = {
    "reporterCode": int,
    "period": str,
    "flowCode": str,
    "partnerCode": int,
    "partner2Code": int,
    "classificationCode": str,
    "cmdCode": str,
    "customsCode": str,
    "motCode": int,
    "primaryValue": (int, float),
}

# Parâmetros da consulta que cada registro deve repetir com o mesmo valor.
ECHOED_PARAMS = ("reporterCode", "period", "flowCode", "cmdCode", "partner2Code", "customsCode", "motCode")

MAX_PROBLEMS_SHOWN = 5


def ensure_not_empty(expected_count: int) -> None:
    """Aplicar ANTES de baixar os dados: vazio nunca vira completed."""
    if expected_count == 0:
        raise EmptyQueryError(
            "A consulta não tem registros (countOnly = 0). O snapshot anterior continua valendo."
        )


def ensure_within_limit(expected_count: int, limit: int = RECORD_LIMIT) -> None:
    """Aplicar ANTES de baixar os dados: acima do limite, a resposta viria truncada."""
    if expected_count > limit:
        raise QueryExceedsLimitError(
            f"A consulta tem {expected_count} registros (countOnly), acima do limite de "
            f"{limit} do endpoint. A resposta viria truncada; os dados não foram baixados."
        )


def ensure_complete(expected_count: int, records: list) -> None:
    """Aplicar DEPOIS de baixar os dados: o recebido precisa ser igual ao esperado."""
    if len(records) != expected_count:
        raise RecordCountMismatchError(
            f"Esperados {expected_count} registros (countOnly), recebidos {len(records)}."
        )


def validate_records(records: list, params: dict) -> None:
    """Aplicar DEPOIS de baixar os dados: estrutura de cada registro e eco dos parâmetros."""
    problems = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            problems.append(f"registro {index}: deveria ser um objeto, veio {type(record).__name__}")
            continue

        for field, expected_type in REQUIRED_FIELDS.items():
            value = record.get(field)
            # bool é subclasse de int em Python: True passaria como reporterCode.
            if isinstance(value, bool) or not isinstance(value, expected_type):
                problems.append(f"registro {index}: {field} = {value!r} (tipo inválido ou ausente)")

        for param in ECHOED_PARAMS:
            # Parâmetros de URL são texto; a API devolve alguns como número (76, 0).
            if param in params and str(record.get(param)) != str(params[param]):
                problems.append(
                    f"registro {index}: {param} = {record.get(param)!r}, mas a consulta pediu {params[param]!r}"
                )

    if problems:
        shown = "; ".join(problems[:MAX_PROBLEMS_SHOWN])
        raise InvalidRecordError(
            f"{len(problems)} problema(s) em {len(records)} registros. Primeiros: {shown}"
        )
