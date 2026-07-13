"""
config/settings.py
Configuracion central de ContentBotMXL.
Define rutas del proyecto y carga variables sensibles (tokens/API keys)
desde un archivo .env que NUNCA debe subirse a git.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Rutas base del proyecto ---
BASE_DIR = Path(__file__).resolve().parent.parent  # raiz de ContentBotMXL

ASSETS_DIR = BASE_DIR / "assets"
CORE_DIR = BASE_DIR / "core"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DB_PATH = DATA_DIR / "app_state.db"

# --- Carga de variables de entorno (.env) ---
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    """Configuracion central de la aplicacion."""

    BASE_DIR = BASE_DIR
    ASSETS_DIR = ASSETS_DIR
    DATA_DIR = DATA_DIR
    LOGS_DIR = LOGS_DIR
    DB_PATH = DB_PATH

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

    APP_NAME = "ContentBotMXL"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def ensure_directories(cls):
        """Crea las carpetas necesarias si no existen (data/, logs/)."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        """Verifica que assets/ exista y no este vacia."""
        if not cls.ASSETS_DIR.exists():
            raise FileNotFoundError(f"No se encontro la carpeta assets/ en {cls.ASSETS_DIR}")
        image_count = len(list(cls.ASSETS_DIR.rglob("*.*")))
        if image_count == 0:
            raise FileNotFoundError("La carpeta assets/ existe pero esta vacia.")
        return image_count


settings = Settings()
