"""
main.py
Punto de entrada de ContentBotMXL: Servidor 2 (Motor Backend, Railway).

Arquitectura de dos servidores independientes:
  - Servidor 1 (n8n, externo): orquestador principal. Dispara los flujos,
    recibe eventos y llama al webhook de este servicio.
  - Servidor 2 (este servicio): corre aislado. No orquesta nada, no llama
    a n8n, no usa base de datos. Se conecta directo a este repo de GitHub
    (via el propio despliegue de Railway) para leer los assets y
    prompt_maestro.txt, procesa la peticion con Gemini + edge-tts,
    y devuelve la estructura final del video en la misma respuesta HTTP.

Variables de entorno usadas:
  - GEMINI_API_KEY     -> generacion de guion (Gemini)
  - TTS_VOZ            -> (opcional) voz de edge-tts; por defecto es-MX-DaliaNeural
  - N8N_WEBHOOK_SECRET -> autenticacion del webhook desde n8n
  - YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
    -> (opcionales) solo necesarias para /webhook/publicar; ver
    core/youtube_client.py y scripts/obtener_refresh_token_youtube.py
"""

import logging
import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config.settings import settings
import productor_mxl
from core import youtube_client

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("contentbotmxl")

app = FastAPI(title=settings.APP_NAME)


class GenerarRequest(BaseModel):
    tema: str = Field(..., min_length=3, description="Tema del video que n8n quiere generar")
    num_escenas: int = Field(default=4, ge=2, le=8)


class PublicarRequest(BaseModel):
    nombre_archivo: str = Field(
        ..., min_length=3,
        description="Nombre del mp4 en output/, tal cual lo devolvio 'archivo' en /webhook/generar",
    )
    titulo: str = Field(..., min_length=3, description="Titulo del video en YouTube")
    descripcion: str = Field(default="", description="Descripcion del video en YouTube")
    tags: list[str] = Field(default_factory=list, description="Tags/etiquetas del video")
    privacy_status: str | None = Field(
        default=None,
        description="private | unlisted | public. Si se omite usa YOUTUBE_PRIVACY_STATUS.",
    )


def verificar_origen(x_webhook_secret: str | None):
    """Valida que la llamada venga de n8n usando el secreto compartido."""
    if not settings.N8N_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500, detail="N8N_WEBHOOK_SECRET no esta configurado en el servidor"
        )
    if x_webhook_secret != settings.N8N_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Origen no autorizado")


@app.get("/health")
def health():
    """Railway usa esto para healthchecks; n8n tambien puede usarlo para probar conexion."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.post("/webhook/generar")
def generar(
    payload: GenerarRequest,
    x_webhook_secret: str | None = Header(default=None),
):
    """
    n8n -> POST /webhook/generar
    Header: X-Webhook-Secret: <N8N_WEBHOOK_SECRET>
    Body:   {"tema": "Los colores primarios", "num_escenas": 4}

    Procesa todo de forma SINCRONA (Gemini -> voz -> render) y devuelve
    la estructura final del video en la misma respuesta. Configura un
    timeout generoso (2-3 min) en el nodo HTTP Request de n8n.
    """
    verificar_origen(x_webhook_secret)

    logger.info("n8n solicito generar video para tema: %s", payload.tema)
    try:
        resultado = productor_mxl.generar_video_desde_tema(payload.tema, payload.num_escenas)
    except Exception as e:
        logger.exception("Fallo generando video para tema '%s'", payload.tema)
        raise HTTPException(status_code=500, detail=str(e))

    return resultado


@app.get("/output/{nombre_archivo}")
def descargar_video(nombre_archivo: str, x_webhook_secret: str | None = Header(default=None)):
    """
    Permite a n8n descargar el mp4 generado, usando el campo "archivo"
    que devolvio /webhook/generar. Protegido por el mismo secreto.
    """
    verificar_origen(x_webhook_secret)

    ruta = (productor_mxl.OUTPUT_DIR / nombre_archivo).resolve()
    if productor_mxl.OUTPUT_DIR.resolve() not in ruta.parents or not ruta.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    return FileResponse(str(ruta), media_type="video/mp4", filename=nombre_archivo)


@app.post("/webhook/publicar")
def publicar(
    payload: PublicarRequest,
    x_webhook_secret: str | None = Header(default=None),
):
    """
    n8n -> POST /webhook/publicar
    Header: X-Webhook-Secret: <N8N_WEBHOOK_SECRET>
    Body:   {"nombre_archivo": "los_colores_...mp4", "titulo": "...",
             "descripcion": "...", "tags": ["..."], "privacy_status": "private"}

    Paso separado de /webhook/generar a proposito: asi le da a n8n la
    libertad de revisar (o insertar un paso de aprobacion humana) antes de
    publicar, o de encadenar ambos nodos HTTP Request uno tras otro si
    quiere el flujo 100% automatico. Requiere YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET y YOUTUBE_REFRESH_TOKEN configurados en Railway
    (ver README y scripts/obtener_refresh_token_youtube.py).
    """
    verificar_origen(x_webhook_secret)

    ruta = (productor_mxl.OUTPUT_DIR / payload.nombre_archivo).resolve()
    if productor_mxl.OUTPUT_DIR.resolve() not in ruta.parents or not ruta.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en output/")

    logger.info("n8n solicito publicar en YouTube: %s", payload.nombre_archivo)
    try:
        resultado = youtube_client.subir_video(
            ruta_video=ruta,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            tags=payload.tags,
            privacy_status=payload.privacy_status,
        )
    except Exception as e:
        logger.exception("Fallo publicando '%s' en YouTube", payload.nombre_archivo)
        raise HTTPException(status_code=500, detail=str(e))

    return resultado


if __name__ == "__main__":
    import uvicorn

    settings.ensure_directories()
    settings.validate()
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
