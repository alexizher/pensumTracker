from functools import lru_cache
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_ORIGINS = ("http://localhost:5173", "http://localhost:3000")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    allowed_origins: Annotated[list[str], NoDecode] = []
    portal_connect_timeout: float = 5
    portal_read_timeout: float = 30

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _limpiar_origenes(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, (list, tuple)):
            return [o.strip() for o in value if isinstance(o, str) and o.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
