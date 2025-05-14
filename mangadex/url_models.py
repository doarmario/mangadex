import json
from typing_extensions import Dict, Union, Any
import requests
import logging

from .errors import ApiError

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode


class URLRequest:
    """
    Classe responsável por realizar requisições HTTP com sessão persistente.
    """
    _session: requests.Session = None

    @classmethod
    def _get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=100,
                pool_maxsize=100,
                max_retries=3,
                pool_block=True
            )
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)
        return cls._session

    @classmethod
    def request_url(
        cls,
        url: str,
        method: str,
        timeout: Union[int, float] = 10,
        params: Union[Dict[str, Any], None] = None,
        headers: Union[Dict[str, str], None] = None,
    ) -> dict:
        session = cls._get_session()

        if params is None:
            params = {}

        # Decodifica bytes para string, se necessário
        if any(isinstance(v, bytes) for v in params.values()):
            params = {k: (v.decode("utf-8") if isinstance(v, bytes) else v) for k, v in params.items()}

        method = method.upper()

        try:
            if method == "GET":
                full_url = cls.__build_url(url, params)
                response = session.get(full_url, headers=headers, timeout=timeout)
            elif method == "POST":
                response = session.post(url, data=params, headers=headers, timeout=timeout)
            elif method == "DELETE":
                response = session.delete(url, headers=headers, timeout=timeout)
            elif method == "PUT":
                response = session.put(url, params=params, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Método HTTP inválido: {method}")
        except requests.RequestException as e:
            logging.exception(f"[URLRequest] Falha na requisição {method} {url}")
            raise

        if not response.ok:
            raise ApiError(response)

        return cls.__parse_data(response.content)

    @staticmethod
    def __build_url(url: str, params: dict) -> str:
        return url + "?" + URLRequest.__encode_parameters(params) if params else url

    @staticmethod
    def __encode_parameters(params: dict) -> str:
        params_tuple = []
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, (list, tuple)):
                params_tuple.extend((k, item) for item in v)
            else:
                params_tuple.append((k, v))
        return urlencode(params_tuple)

    @staticmethod
    def __parse_data(content: Union[str, bytes]) -> Union[dict, str]:
        try:
            decoded = content if isinstance(content, str) else content.decode("utf-8")
            data = json.loads(decoded)
            URLRequest._check_api_error(data)
            return data
        except json.JSONDecodeError:
            # Resposta não-JSON (ex: ping), retorna como string
            return content.decode("utf-8") if isinstance(content, bytes) else content

    @staticmethod
    def _check_api_error(data: Union[dict, list]):
        # Padroniza o objeto para dicionário
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            if data.get("result") == "error" or "error" in data:
                raise ApiError(data.get("errors", "Erro desconhecido"))
