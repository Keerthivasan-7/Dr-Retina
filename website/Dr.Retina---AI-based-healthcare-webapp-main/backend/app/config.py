from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: SecretStr
    supabase_url: str
    supabase_publishable_key: str
    supabase_service_role_key: SecretStr
    app_url: str = "http://localhost:3000"
    storage_bucket: str = "retinal-images"
    ai_service_url: str = ""
    ai_service_key: SecretStr = SecretStr("")
    ai_model_version: str = ""
    max_upload_bytes: int = 25 * 1024 * 1024
    worker_poll_seconds: int = 3
    worker_lease_seconds: int = Field(default=300, ge=300)
    environment: str = "development"


@lru_cache
def settings() -> Settings:
    return Settings()
