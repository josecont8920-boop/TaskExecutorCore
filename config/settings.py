import os

class Settings:
    VCC_API_KEY: str = os.getenv("VCC_API_KEY", "")
    PROFILES_STORAGE_PATH: str = "data/profiles"
    BATCH_MAX_RETRIES: int = 3
    BATCH_RETRY_DELAY_SECONDS: int = 2
    VCC_DEFAULT_BUDGET: float = 50.0

settings = Settings()
