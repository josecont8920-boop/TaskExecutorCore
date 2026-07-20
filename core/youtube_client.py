"""
core/youtube_client.py
Sube el mp4 ya generado a YouTube, usando OAuth2 con un refresh token de
larga duracion. Se elige refresh token (en vez de una cuenta de servicio)
porque la YouTube Data API v3 no admite cuentas de servicio para subir
videos a un canal personal/de marca: hace falta autorizar explicitamente
la cuenta del canal una vez, y de ahi en adelante Railway puede refrescar
el access token solo, sin volver a abrir un navegador.

Como conseguir el refresh token (UNA sola vez, en tu maquina local, nunca
en Railway):
  1. En Google Cloud Console: habilita "YouTube Data API v3" y crea
     credenciales OAuth2 tipo "Desktop App".
  2. Descarga ese JSON como client_secret_youtube.json en la raiz del repo
     (esta en .gitignore; nunca se sube a GitHub).
  3. Corre: python3 scripts/obtener_refresh_token_youtube.py
     Se abre el navegador, autorizas con la cuenta del canal, y el script
     imprime YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN.
  4. Pega esos 3 valores como variables de entorno en Railway.

Este modulo NO se valida al arrancar el servicio (ver config/settings.py:
validate_youtube()); solo se necesita cuando llega una peticion real a
/webhook/publicar, para no romper la generacion de video si YouTube
todavia no esta configurado.
"""

import logging
from pathlib import Path

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config.settings import settings

logger = logging.getLogger("contentbotmxl.youtube")

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Categoria "Education" en la clasificacion estandar de YouTube.
CATEGORIA_EDUCATIVO = "27"

PRIVACY_STATUS_VALIDOS = {"private", "unlisted", "public"}


def _construir_credenciales() -> Credentials:
    """Arma credenciales OAuth2 a partir del refresh token y las refresca
    de inmediato para detectar problemas de configuracion temprano
    (token revocado, credenciales mal copiadas, etc.) en vez de fallar
    a mitad de la subida."""
    settings.validate_youtube()

    creds = Credentials(
        token=None,
        refresh_token=settings.YOUTUBE_REFRESH_TOKEN,
        token_uri=TOKEN_URI,
        client_id=settings.YOUTUBE_CLIENT_ID,
        client_secret=settings.YOUTUBE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    try:
        creds.refresh(GoogleAuthRequest())
    except Exception as e:
        raise RuntimeError(
            f"No se pudo refrescar el token de YouTube: {e}. "
            "Es probable que YOUTUBE_REFRESH_TOKEN este vencido o revocado; "
            "corre de nuevo scripts/obtener_refresh_token_youtube.py."
        ) from e
    return creds


def subir_video(
    ruta_video: Path,
    titulo: str,
    descripcion: str = "",
    tags: list[str] | None = None,
    privacy_status: str | None = None,
) -> dict:
    """
    Sube `ruta_video` (mp4 ya generado por productor_mxl.py) al canal de
    YouTube autorizado por el refresh token. Devuelve
    {"video_id": ..., "url": ..., "privacy_status": ...}.
    """
    ruta_video = Path(ruta_video)
    if not ruta_video.exists():
        raise FileNotFoundError(f"No se encontro el video a subir: {ruta_video}")

    status_final = (privacy_status or settings.YOUTUBE_PRIVACY_STATUS or "private").strip().lower()
    if status_final not in PRIVACY_STATUS_VALIDOS:
        raise ValueError(
            f"privacy_status invalido: '{status_final}'. Debe ser uno de {sorted(PRIVACY_STATUS_VALIDOS)}."
        )

    creds = _construir_credenciales()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion[:5000],
            "tags": (tags or [])[:500],
            "categoryId": CATEGORIA_EDUCATIVO,
        },
        "status": {
            "privacyStatus": status_final,
            # Contenido infantil ("mxl Aprende"): por defecto se declara
            # como hecho para ninos, requisito legal de YouTube (COPPA).
            # Se puede desactivar con YOUTUBE_MADE_FOR_KIDS=false si algun
            # video puntual no aplica.
            "selfDeclaredMadeForKids": settings.YOUTUBE_MADE_FOR_KIDS,
        },
    }

    media = MediaFileUpload(str(ruta_video), mimetype="video/mp4", chunksize=-1, resumable=True)

    logger.info(
        "Subiendo '%s' a YouTube (privacy=%s, made_for_kids=%s)...",
        titulo, status_final, settings.YOUTUBE_MADE_FOR_KIDS,
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    respuesta = None
    while respuesta is None:
        try:
            estado, respuesta = request.next_chunk()
        except HttpError as e:
            logger.exception("YouTube devolvio un error subiendo '%s'", ruta_video.name)
            raise RuntimeError(f"YouTube API error {e.resp.status}: {e.content}") from e

        if estado is not None:
            logger.info("Progreso de subida a YouTube: %d%%", int(estado.progress() * 100))

    video_id = respuesta["id"]
    url = f"https://youtu.be/{video_id}"
    logger.info("Video publicado en YouTube: %s (privacy=%s)", url, status_final)

    return {"video_id": video_id, "url": url, "privacy_status": status_final}
