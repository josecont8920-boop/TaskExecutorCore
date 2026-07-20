"""
main.py
Punto de entrada de ContentBotMXL: Servidor 2 (Motor Backend, Railway).

Arquitectura de dos servidores independientes:
  - Servidor 1 (n8n, externo): orquestador principal. Dispara los flujos,
    recibe eventos y llama al webhook de este servicio.
  - Servidor 2 (este servicio): corre aislado. No orquesta nada, no usa
    base de datos. Se conecta directo a este repo de GitHub (via el propio
    despliegue de Railway) para leer los assets y prompt_maestro.txt,
    procesa la peticion con Gemini + edge-tts, y arma el video.

Modos de /webhook/generar:
  - SINCRONO (por defecto, compatible con el flujo anterior): procesa todo
    y devuelve la estructura final en la misma respuesta HTTP. Requiere un
    timeout generoso (2-3 min) en el nodo HTTP Request de n8n.
  - ASINCRONO (si el body trae "callback_url"): responde al instante con
    {"status": "aceptado"} y procesa en segundo plano. Al terminar (o si
    falla), hace un POST a callback_url con el resultado, incluyendo el
    mismo header X-Webhook-Secret para que n8n pueda verificar que la
    notificacion viene realmente de este servicio.
  - "auto_publicar": true (solo tiene efecto en modo asincrono) hace que,
    ademas de renderizar el video, lo suba a YouTube automaticamente antes
    de avisar a n8n. Requiere pasar titulo/descripcion/tags en el body y
    tener configuradas las variables YOUTUBE_*.

Variables de entorno usadas:
  - GEMINI_API_KEY     -> generacion de guion (Gemini)
  - TTS_VOZ            -> (opcional) voz de edge-tts; por defecto es-MX-DaliaNeural
  - N8N_WEBHOOK_SECRET -> autenticacion del webhook desde n8n (y de los callbacks de vuelta)
  - YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
    -> (opcionales) solo necesarias para /webhook/publicar o auto_publicar;
    ver core/youtube_client.py y scripts/obtener_refresh_token_youtube.py
"""

import logging
import os

import requests
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config.settings import settings
import productor_mxl
from core import youtube_client

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("contentbotmxl")

app = FastAPI(title=settings.APP_NAME)

CALLBACK_TIMEOUT_SEG = 15
CALLBACK_MAX_INTENTOS = 3


class GenerarRequest(BaseModel):
    tema: str = Field(..., min_length=3, description="Tema del video que n8n quiere generar")
    num_escenas: int = Field(default=4, ge=2, le=8)

    # --- Modo asincrono (opcional) ---
    callback_url: str | None = Field(
        default=None,
        description="Si se envia, /webhook/generar responde al instante y procesa "
                    "en segundo plano, avisando a esta URL cuando termine.",
    )
    auto_publicar: bool = Field(
        default=False,
        description="Solo aplica si se envia callback_url. Si es true, sube el "
                    "video a YouTube automaticamente al terminar de renderizar.",
    )
    titulo_youtube: str | None = Field(default=None, description="Requerido si auto_publicar=true")
    descripcion_youtube: str = Field(default="")
    tags_youtube: list[str] = Field(default_factory=list)
    privacy_status: str | None = Field(
        default=None,
        description="private | unlisted | public. Se ignora si se envia publicar_en.",
    )
    publicar_en: str | None = Field(
        default=None,
        description="Fecha/hora ISO 8601 con zona horaria (ej. '2026-07-25T15:00:00Z') para "
                    "programar la publicacion en YouTube. Mientras tanto el video queda oculto.",
    )
    privacy_status: str | None = Field(default=None, description="private | unlisted | public")


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
        description="private | unlisted | public. Si se omite usa YOUTUBE_PRIVACY_STATUS. "
                    "Se ignora si se envia publicar_en.",
    )
    publicar_en: str | None = Field(
        default=None,
        description="Fecha/hora ISO 8601 con zona horaria (ej. '2026-07-25T15:00:00Z') en la "
                    "que YouTube debe publicar el video automaticamente. Mientras tanto queda "
                    "oculto (privado).",
    )


def verificar_origen(x_webhook_secret: str | None):
    """Valida que la llamada venga de n8n usando el secreto compartido."""
    if not settings.N8N_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500, detail="N8N_WEBHOOK_SECRET no esta configurado en el servidor"
        )
    if x_webhook_secret != settings.N8N_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Origen no autorizado")


def _notificar_callback(callback_url: str, payload: dict) -> None:
    """
    Avisa a n8n (o a quien haya mandado callback_url) que el trabajo en
    segundo plano termino, con reintentos simples ante fallos de red.
    Incluye el secreto compartido para que el receptor pueda verificar el
    origen de la notificacion.
    """
    headers = {"X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET}

    for intento in range(1, CALLBACK_MAX_INTENTOS + 1):
        try:
            resp = requests.post(callback_url, json=payload, headers=headers, timeout=CALLBACK_TIMEOUT_SEG)
            logger.info("Callback enviado a %s (intento %s). Codigo: %s", callback_url, intento, resp.status_code)
            return
        except requests.RequestException as e:
            logger.warning("Fallo el callback a %s (intento %s/%s): %s",
                            callback_url, intento, CALLBACK_MAX_INTENTOS, e)

    logger.error("No se pudo notificar a %s tras %s intentos.", callback_url, CALLBACK_MAX_INTENTOS)


def _procesar_en_segundo_plano(payload: dict) -> None:
    """
    Tarea de fondo real: genera el video con el motor de produccion existente
    (productor_mxl), opcionalmente lo publica en YouTube, y notifica el
    resultado (exito o error) a callback_url si se proporciono.

    FastAPI/Starlette ejecuta las funciones sincronas de BackgroundTasks en
    un threadpool aparte, asi que esto no bloquea el resto del servidor
    mientras corre moviepy.
    """
    tema = payload["tema"]
    callback_url = payload.get("callback_url")

    try:
        logger.info("[BG] Generando video para tema '%s'...", tema)
        resultado = productor_mxl.generar_video_desde_tema(tema, payload.get("num_escenas", 4))
        resultado_final = {"status": "listo", "tema": tema, **resultado}

        if payload.get("auto_publicar"):
            ruta_video = productor_mxl.OUTPUT_DIR / resultado["archivo"]
            logger.info("[BG] auto_publicar=true, subiendo a YouTube...")
            info_youtube = youtube_client.subir_video(
                ruta_video=ruta_video,
                titulo=payload.get("titulo_youtube") or resultado["titulo"],
                descripcion=payload.get("descripcion_youtube", ""),
                tags=payload.get("tags_youtube", []),
                privacy_status=payload.get("privacy_status"),
                publicar_en=payload.get("publicar_en"),
            )
            resultado_final["youtube"] = info_youtube

        logger.info("[BG] Trabajo completo para tema '%s'.", tema)

    except Exception as e:
        logger.exception("[BG] Fallo procesando tema '%s'", tema)
        resultado_final = {"status": "error", "tema": tema, "mensaje": str(e)}

    if callback_url:
        _notificar_callback(callback_url, resultado_final)


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
    n8n -> POST /webhook/generar
    Header: X-Webhook-Secret: <N8N_WEBHOOK_SECRET>

    Sin "callback_url" en el body: procesa SINCRONO y devuelve el resultado
    en la misma respuesta (comportamiento anterior, sin cambios).

    Con "callback_url": responde al instante {"status": "aceptado"} y hace
    todo el trabajo en segundo plano, avisando a esa URL al terminar.
    """
    verificar_origen(x_webhook_secret)

    if payload.auto_publicar and not payload.callback_url:
        raise HTTPException(
            status_code=400,
            detail="auto_publicar=true requiere callback_url (solo aplica en modo asincrono).",
        )
    if payload.auto_publicar and not payload.titulo_youtube:
        raise HTTPException(status_code=400, detail="auto_publicar=true requiere titulo_youtube.")

    # --- Modo asincrono ---
    if payload.callback_url:
        logger.info("n8n solicito generar (async) para tema: %s -> callback: %s",
                    payload.tema, payload.callback_url)
        background_tasks.add_task(_procesar_en_segundo_plano, payload.model_dump())
        return {
            "status": "aceptado",
            "mensaje": "Procesando en segundo plano. Se notificara a callback_url al terminar.",
            "tema": payload.tema,
        }

    # --- Modo sincrono (comportamiento anterior, intacto) ---
    logger.info("n8n solicito generar (sync) para tema: %s", payload.tema)
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
    que devolvio /webhook/generar (o el callback). Protegido por el mismo secreto.
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

    Paso separado de /webhook/generar a proposito: le da a n8n la libertad
    de revisar (o insertar un paso de aprobacion humana) antes de publicar.
    Requiere YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET y YOUTUBE_REFRESH_TOKEN
    configurados en Railway (ver README y scripts/obtener_refresh_token_youtube.py).
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
            publicar_en=payload.publicar_en,
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
