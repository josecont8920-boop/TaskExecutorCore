"""
core/tts_client.py
Motor de voz: sintetiza audio con Google Cloud Text-to-Speech.

Prioriza la cuenta de servicio (GOOGLE_APPLICATION_CREDENTIALS_JSON, la
cuenta de servicio de Google Cloud dedicada al motor de voz). Si no esta
configurada, recurre a GOOGLE_TTS_API_KEY como metodo alterno. No usa
ninguna otra variable ni servicio externo.
"""

import base64
import json
import logging
from pathlib import Path

import requests

from config.settings import settings

logger = logging.getLogger("contentbotmxl.tts")

TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
VOZ_NOMBRE = "es-US-Neural2-A"
VOZ_IDIOMA = "es-US"

_credentials = None  # cache de las credenciales de la cuenta de servicio, en memoria


def _obtener_token_cuenta_servicio() -> str | None:
    """Obtiene un access token OAuth2 a partir de GOOGLE_APPLICATION_CREDENTIALS_JSON."""
    global _credentials

    if not settings.GOOGLE_APPLICATION_CREDENTIALS_JSON:
        return None

    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    if _credentials is None:
        try:
            info = json.loads(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS_JSON no contiene un JSON valido. "
                "Debe ser el contenido completo del archivo de la cuenta de servicio, "
                "pegado tal cual como valor de la variable de entorno."
            ) from e
        _credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    if not _credentials.valid:
        _credentials.refresh(Request())

    return _credentials.token


def sintetizar_audio(texto: str, destino: Path) -> Path:
    """
    Sintetiza `texto` a voz en espanol y guarda el mp3 resultante en `destino`.
    Usa la cuenta de servicio si esta disponible; si no, GOOGLE_TTS_API_KEY.
    """
    payload = {
        "input": {"text": texto},
        "voice": {"languageCode": VOZ_IDIOMA, "name": VOZ_NOMBRE},
        "audioConfig": {"audioEncoding": "MP3"},
    }

    token = _obtener_token_cuenta_servicio()
    if token:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(TTS_URL, headers=headers, json=payload, timeout=30)
    elif settings.GOOGLE_TTS_API_KEY:
        resp = requests.post(
            TTS_URL, params={"key": settings.GOOGLE_TTS_API_KEY}, json=payload, timeout=30
        )
    else:
        raise RuntimeError(
            "No hay credenciales de voz configuradas: define GOOGLE_APPLICATION_CREDENTIALS_JSON "
            "o GOOGLE_TTS_API_KEY en las variables de entorno de Railway."
        )

    if resp.status_code >= 400:
        raise RuntimeError(f"Google TTS devolvio un error ({resp.status_code}): {resp.text}")

    audio_b64 = resp.json().get("audioContent")
    if not audio_b64:
        raise RuntimeError(f"Google TTS no devolvio audio: {resp.json()}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(base64.b64decode(audio_b64))
    return destino
