from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config. Upstream URLs are reserved for later plans (consume layer)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    classifier_url: str = "http://127.0.0.1:5001"
    sk_url: str = "http://127.0.0.1:5002"
    slip_url: str = "http://127.0.0.1:5003"
    mutasi_url: str = "http://127.0.0.1:5004"
    match_url: str = "http://127.0.0.1:5005"
    npw_url: str = "http://127.0.0.1:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
