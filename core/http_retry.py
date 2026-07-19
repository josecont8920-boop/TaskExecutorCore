"""
core/http_retry.py
Utilidad compartida: reintenta una peticion HTTP con espera progresiva
cuando Google devuelve 429 (limite de peticiones) o 503 (servicio
temporalmente ocupado). La usan gemini_client.py y tts_client.py.
"""

import logging
import time

import requests

logger = logging.getLogger("contentbotmxl.http_retry")

CODIGOS_REINTENTABLES = (429, 503)


def post_con_reintentos(
    url: str,
    max_intentos: int = 4,
    espera_base_seg: float = 5.0,
    **kwargs,
) -> requests.Response:
    """
    Hace requests.post(url, **kwargs) y reintenta automaticamente si Google
    devuelve 429/503. Espera de forma progresiva entre intento e intento
    (5s, 10s, 20s, ...), respetando el header Retry-After si Google lo envia.
    Lanza la respuesta final (con raise_for_status) si se agotan los intentos.
    """
    ultimo_error = None

    for intento in range(1, max_intentos + 1):
        resp = requests.post(url, **kwargs)

        if resp.status_code not in CODIGOS_REINTENTABLES:
            return resp

        ultimo_error = resp

        if intento == max_intentos:
            break

        espera = espera_base_seg * (2 ** (intento - 1))
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                espera = max(espera, float(retry_after))
            except ValueError:
                pass

        logger.warning(
            "Google devolvio %s (intento %s/%s). Esperando %.0fs antes de reintentar...",
            resp.status_code, intento, max_intentos, espera,
        )
        time.sleep(espera)

    ultimo_error.raise_for_status()
    return ultimo_error  # inalcanzable: raise_for_status ya lanzo la excepcion
