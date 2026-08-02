import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_BACKGROUNDS = BASE_DIR / "assets" / "backgrounds"
ASSETS_MUSIC = BASE_DIR / "assets" / "music"
OUTPUT_DIR = BASE_DIR / "output"
DATA_PENDIENTES = BASE_DIR / "data" / "textos_pendientes"
DATA_PROCESADOS = BASE_DIR / "data" / "textos_procesados"

# TTS local (Coqui) - modelo español multi-voz, 100% offline tras la primera descarga
TTS_MODEL = os.getenv("TTS_MODEL", "tts_models/es/css10/vits")

# Formato de video por defecto
FORMATO_DEFAULT = os.getenv("FORMATO_VIDEO", "vertical")  # vertical | horizontal
RESOLUCIONES = {
    "vertical": (1080, 1920),
    "horizontal": (1920, 1080),
}

# Subtítulos
SUBTITULO_FONT = os.getenv("SUBTITULO_FONT", "DejaVu-Sans-Bold")
SUBTITULO_TAMANO = int(os.getenv("SUBTITULO_TAMANO", "60"))
SUBTITULO_COLOR = os.getenv("SUBTITULO_COLOR", "white")

for d in [ASSETS_BACKGROUNDS, ASSETS_MUSIC, OUTPUT_DIR, DATA_PENDIENTES, DATA_PROCESADOS]:
    d.mkdir(parents=True, exist_ok=True)
