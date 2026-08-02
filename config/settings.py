from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Literal

class Settings(BaseSettings):
    APP_NAME: str = "AutoFlow Tiendas"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    PROFILES_STORAGE_PATH: str = "data/profiles"
    VCC_API_KEY: Optional[str] = Field(None, env="VCC_API_KEY")
    VCC_API_URL: str = "https://api.stripe.com/v1"
    VCC_DEFAULT_BUDGET: float = 25.0
    BALANCE_MIN_AMOUNT: float = 1.0
    BALANCE_MAX_AMOUNT: float = 50.0
    BALANCE_DEFAULT_CURRENCY: Literal["USD", "EUR", "GBP"] = "USD"
    BALANCE_DISTRIBUTION: Literal["uniform", "normal", "exponential"] = "normal"
    BALANCE_EXPIRATION_SECONDS: int = 3600
    BATCH_MAX_RETRIES: int = 3
    BATCH_RETRY_DELAY_SECONDS: int = 5
    VALIDATION_MODE: Literal["real", "simulate"] = "simulate"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
