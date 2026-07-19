#!/usr/bin/env python3
"""
productor_mxl.py
Fabrica de Videos MXL - ensamblador automatico de video vertical (1080x1920)
para el canal mxl Aprende. Usa config/settings.py y core/asset_manager.py
que ya existen en el proyecto.

Uso:
    python3 productor_mxl.py                    -> procesa TODOS los guiones pendientes
    python3 productor_mxl.py ruta/al/guion.json  -> procesa un guion especifico
"""

import sys
import json
import random
import logging
import traceback
from pathlib import Path
from datetime import datetime

from gtts import gTTS
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, afx
)

from config.settings import settings
from core.asset_manager import asset_manager

# ---------- Configuracion ----------
VIDEO_W, VIDEO_H = 1080, 1920
FPS = 30
ZOOM_FACTOR = 1.15
AUDIO_PADDING = 0.4
MUSIC_VOLUME = 0.12

BASE_DIR = settings.BASE_DIR
GUIONES_DIR = BASE_DIR / "data" / "guiones"
PENDIENTES_DIR = GUIONES_DIR / "pendientes"
PROCESADOS_DIR = GUIONES_DIR / "procesados"
FALLIDOS_DIR = GUIONES_DIR / "fallidos"
OUTPUT_DIR = BASE_DIR / "output"
MUSICA_DIR = BASE_DIR / "assets" / "musica"
TMP_AUDIO_DIR = BASE_DIR / "data" / "tmp_audio"

for d in (PENDIENTES_DIR, PROCESADOS_DIR, FALLIDOS_DIR, OUTPUT_DIR, TMP_AUDIO_DIR):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(settings.LOGS_DIR / "productor_mxl.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("productor_mxl")


# ---------- Utilidades ----------

def generar_audio_escena(texto: str, idx: int, run_id: str) -> Path:
    audio_path = TMP_AUDIO_DIR / f"{run_id}_escena_{idx:02d}.mp3"
    tts = gTTS(text=texto, lang="es", tld="com.mx", slow=False)
    tts.save(str(audio_path))
    return audio_path


def efecto_ken_burns(clip: ImageClip, duracion: float, zoom_in: bool = True):
    def zoom_func(t):
        progreso = t / duracion
        if zoom_in:
            return 1 + (ZOOM_FACTOR - 1) * progreso
        return ZOOM_FACTOR - (ZOOM_FACTOR - 1) * progreso
    return clip.resize(zoom_func)


def imagen_a_clip_vertical(ruta_imagen: Path, duracion: float) -> ImageClip:
    clip = ImageClip(str(ruta_imagen)).set_duration(duracion)
    w, h = clip.size
    escala = max(VIDEO_W / w, VIDEO_H / h)
    clip = clip.resize(escala)
    clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=VIDEO_W, height=VIDEO_H)
    clip = efecto_ken_burns(clip, duracion, zoom_in=random.choice([True, False]))
    return clip.set_position("center")


def elegir_musica_fondo():
    if not MUSICA_DIR.exists():
        return None
    pistas = [p for p in MUSICA_DIR.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".ogg")]
    return random.choice(pistas) if pistas else None


# ---------- Nucleo del ensamblaje ----------

def construir_video(guion: dict, run_id: str) -> Path:
    escenas = guion.get("escenas", [])
    if not escenas:
        raise ValueError("El guion no contiene 'escenas'.")

    titulo = guion.get("titulo", f"video_{run_id}")
    clips_video = []
    audios_temporales = []

    for idx, escena in enumerate(escenas, start=1):
        texto = escena.get("texto", "").strip()
        emocion = escena.get("emocion", "").strip()

        if not texto:
            logger.warning("Escena %s sin texto, se omite.", idx)
            continue

        audio_path = generar_audio_escena(texto, idx, run_id)
        audios_temporales.append(audio_path)
        audio_clip = AudioFileClip(str(audio_path))
        duracion_escena = audio_clip.duration + AUDIO_PADDING

        try:
            ruta_imagen = asset_manager.get_random_asset(category=emocion or None)
        except ValueError:
            logger.warning("Emocion '%s' no encontrada, se usa imagen aleatoria.", emocion)
            ruta_imagen = asset_manager.get_random_asset()

        clip_img = imagen_a_clip_vertical(ruta_imagen, duracion_escena)
        clip_img = clip_img.set_audio(audio_clip)
        clips_video.append(clip_img)

    if not clips_video:
        raise ValueError("Ninguna escena pudo procesarse; el guion quedo vacio.")

    video_final = concatenate_videoclips(clips_video, method="compose")

    pista_musica = elegir_musica_fondo()
    if pista_musica:
        musica = AudioFileClip(str(pista_musica)).fx(afx.audio_loop, duration=video_final.duration)
        musica = musica.fx(afx.volumex, MUSIC_VOLUME)
        video_final = video_final.set_audio(CompositeAudioClip([video_final.audio, musica]))
    else:
        logger.info("No se encontro musica en %s; el video sale solo con voz.", MUSICA_DIR)

    nombre_archivo = f"{titulo.replace(' ', '_').lower()}_{run_id}.mp4"
    salida = OUTPUT_DIR / nombre_archivo

    video_final.write_videofile(
        str(salida), fps=FPS, codec="libx264", audio_codec="aac",
        threads=4, preset="medium", logger=None,
    )

    for clip in clips_video:
        clip.close()
    video_final.close()
    for audio_path in audios_temporales:
        audio_path.unlink(missing_ok=True)

    return salida


# ---------- Orquestador de lote ----------

def procesar_guion_individual(ruta_guion: Path) -> bool:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info("=== Procesando guion: %s (run_id=%s) ===", ruta_guion.name, run_id)

    try:
        with open(ruta_guion, "r", encoding="utf-8") as f:
            guion = json.load(f)

        salida = construir_video(guion, run_id)
        logger.info("VIDEO OK: %s", salida)

        ruta_guion.rename(PROCESADOS_DIR / ruta_guion.name)
        return True

    except Exception as e:
        logger.error("FALLO en guion '%s': %s", ruta_guion.name, e)
        logger.debug(traceback.format_exc())
        try:
            ruta_guion.rename(FALLIDOS_DIR / ruta_guion.name)
        except Exception:
            pass
        return False


def procesar_lote():
    guiones = sorted(PENDIENTES_DIR.glob("*.json"))
    if not guiones:
        logger.info("No hay guiones pendientes en %s", PENDIENTES_DIR)
        return

    exitosos = fallidos = 0
    for ruta_guion in guiones:
        if procesar_guion_individual(ruta_guion):
            exitosos += 1
        else:
            fallidos += 1

    logger.info("=== Lote terminado: %s OK, %s fallidos ===", exitosos, fallidos)


if __name__ == "__main__":
    settings.ensure_directories()
    settings.validate()

    if len(sys.argv) > 1:
        ruta = Path(sys.argv[1])
        if not ruta.exists():
            logger.error("El guion no existe: %s", ruta)
            sys.exit(1)
        procesar_guion_individual(ruta)
    else:
        procesar_lote()
