from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Automation Hub"
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    allowed_hosts_raw: str = "localhost,127.0.0.1,testserver,api"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    database_url: str = "sqlite:///./automation_hub.db"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    oauth_encryption_key: str | None = None
    oauth_redirect_base: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    worker_poll_seconds: float = 2.0
    public_base_url: str = ""
    google_pubsub_topic: str | None = None
    google_pubsub_audience: str | None = None
    google_pubsub_service_account: str | None = None
    jwt_secret: str = "CHANGE-ME-IN-ENVIRONMENT-AT-LEAST-32-CHARS"
    access_token_minutes: int = 60 * 12

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts_raw.split(",") if host.strip()]

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
