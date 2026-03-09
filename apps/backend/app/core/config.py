from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "notion-graph-backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    notion_token: str = Field(..., alias="NOTION_TOKEN")
    notion_root_page_id: str = Field(..., alias="NOTION_ROOT_PAGE_ID")
    notion_use_fixtures: bool = Field(default=False, alias="NOTION_USE_FIXTURES")
    notion_fixture_path: str = Field(default="", alias="NOTION_FIXTURE_PATH")

    database_url: str = Field(default="sqlite:////data/notion_graph.db", alias="DATABASE_URL")
    sync_interval_minutes: int = Field(default=360, alias="SYNC_INTERVAL_MINUTES")
    sync_poll_seconds: int = Field(default=5, alias="SYNC_POLL_SECONDS")

    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")
    notion_webhook_secret: str = Field(default="", alias="NOTION_WEBHOOK_SECRET")

    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_environment: str = Field(default="development", alias="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
