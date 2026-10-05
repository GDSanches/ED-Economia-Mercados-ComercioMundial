import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import PER_PAGE, TIMEOUT

BASE_URL = "https://api.worldbank.org/v2"

# A API do World Bank tem lentidões e erros 5xx momentâneos. Com o escopo global
# (~18 páginas por indicador), uma falha isolada derrubaria o run inteiro.
# Retry repete a requisição com espera crescente (2s, 4s, 8s, 16s, 32s).
RETRY = Retry(
    total=5,
    connect=5,
    read=5,
    status=5,
    backoff_factor=2,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
)

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=RETRY))


def request_page(path: str, page: int, extra_params: dict | None = None) -> requests.Response:
    url = f"{BASE_URL}/{path}"
    params = {
        **(extra_params or {}),
        "format": "json",
        "per_page": PER_PAGE,
        "page": page,
    }

    response = session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response
