"""
main.py
Punto de entrada del servicio ContentBotMXL en Railway.
Expone endpoints HTTP que n8n puede llamar para disparar
el motor real de video/voz: productor_mxl.py (gTTS + moviepy).
"""

import logging
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel

from config.settings import settings
import productor_mxl

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("contentbotmxl")

app = FastAPI(title=settings.APP_NAME)

N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "")


class GenerarRequest(BaseModel):
    guion: str | None = None  # nombre de archivo especifico en data/guiones/pendientes/, o None para todo el lote


def verificar_origen(x_webhook_secret: str | None):
    """Valida que la llamada venga de n8n usando un secreto compartido."""
    if N8N_WEBHOOK_SECRET and x_webhook_secret != N8N_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Origen no autorizado")


@app.get("/health")
def health():
    """Railway usa esto para healthchecks; n8n tambien puede usarlo para probar conexion."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.post("/webhook/generar")
def generar(
    payload: GenerarRequest,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
):
    """
    Endpoint que n8n llama para disparar la generacion de video/voz.
    n8n -> POST /webhook/generar { "guion": "01_rojo.json" }   (o {} para procesar todo el lote)

    La generacion de video puede tardar minutos (TTS + render), asi que se corre
    en background y este endpoint responde de inmediato para no bloquear a n8n.
    """
    verificar_origen(x_webhook_secret)

    if payload.guion:
        ruta = productor_mxl.PENDIENTES_DIR / payload.guion
        if not ruta.exists():
            raise HTTPException(status_code=404, detail=f"No existe el guion: {payload.guion}")
        logger.info("n8n solicito procesar guion individual: %s", payload.guion)
        background_tasks.add_task(productor_mxl.procesar_guion_individual, ruta)
    else:
        logger.info("n8n solicito procesar el lote completo de guiones pendientes")
        background_tasks.add_task(productor_mxl.procesar_lote)

    return {"status": "encolado", "guion": payload.guion or "lote completo"}


if __name__ == "__main__":
    import uvicorn

    settings.ensure_directories()
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
