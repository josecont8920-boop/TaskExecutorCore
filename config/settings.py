"""
config/settings.py
Configuracion central de ContentBotMXL (Servidor 2 - Motor Backend en Railway).

Este servicio corre aislado: no usa base de datos externa ni de ningun tipo.
Todo lo que necesita (assets, prompt_maestro.txt) vive versionado en este
mismo repositorio de GitHub, y las unicas variables de entorno que usa son:

  - GEMINI_API_KEY                      -> generacion de guion con Gemini
  - GOOGLE_TTS_API_KEY                  -> voz, metodo API key (Google Cloud TTS)
  - GOOGLE_APPLICATION_CREDENTIALS_JSON -> voz, cuenta de servicio (Google Cloud TTS)
  - N8N_WEBHOOK_SECRET                  -> autenticacion del webhook llamado por n8n
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
PROMPT_MAESTRO_PATH = BASE_DIR / "prompt_maestro.txt"

# --- Carga de variables de entorno (.env local; en Railway se inyectan directo) ---
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    """Configuracion central de la aplicacion."""

    BASE_DIR = BASE_DIR
    ASSETS_DIR = ASSETS_DIR
    DATA_DIR = DATA_DIR
    LOGS_DIR = LOGS_DIR
    PROMPT_MAESTRO_PATH = PROMPT_MAESTRO_PATH

    # --- Unicas variables de IA/voz que este servicio tiene permitido usar ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_TTS_API_KEY = os.getenv("GOOGLE_TTS_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")

    # --- Autenticacion del webhook (Servidor 1 -> Servidor 2) ---
    N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "")

    APP_NAME = "ContentBotMXL"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def ensure_directories(cls):
        """Crea las carpetas necesarias si no existen (data/, logs/). No crea ninguna DB."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        """
        Verifica que el motor tenga TODO lo que necesita para operar de forma
        autonoma: assets del repo, prompt_maestro.txt versionado, y las
        credenciales de IA/voz. Se corre al arrancar el servicio en Railway.
        """
        if not cls.ASSETS_DIR.exists():
            raise FileNotFoundError(f"No se encontro la carpeta assets/ en {cls.ASSETS_DIR}")

        image_count = len(list(cls.ASSETS_DIR.rglob("*.*")))
        if image_count == 0:
            raise FileNotFoundError("La carpeta assets/ existe pero esta vacia.")

        if not cls.PROMPT_MAESTRO_PATH.exists():
            raise FileNotFoundError(
                f"No se encontro prompt_maestro.txt en {cls.PROMPT_MAESTRO_PATH}. "
                "Debe estar versionado en el repo de GitHub (no se lee de ningun otro lado)."
            )

        if not cls.GEMINI_API_KEY:
            raise RuntimeError("Falta GEMINI_API_KEY en las variables de entorno de Railway.")

        if not (cls.GOOGLE_TTS_API_KEY or cls.GOOGLE_APPLICATION_CREDENTIALS_JSON):
            raise RuntimeError(
                "Falta configurar la voz: define GOOGLE_TTS_API_KEY o "
                "GOOGLE_APPLICATION_CREDENTIALS_JSON en Railway."
            )

        if not cls.N8N_WEBHOOK_SECRET:
            raise RuntimeError("Falta N8N_WEBHOOK_SECRET: el webhook no puede quedar sin proteger.")

        return image_count


settings = Settings()
