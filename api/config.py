"""Application settings loaded from `.env`."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StratForge API"
    app_version: str = "1.0.0"

    secret_key: str = "dev_secret_change_me"
    jwt_lifetime_seconds: int = 60 * 60 * 12
    database_url: str = "sqlite+aiosqlite:///./stratforge.db"

    frontend_url: str = "http://localhost:5173"
    config_template_path: str = "config.yaml"
    results_dir: str = "results"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_elite: str = ""
    stripe_api_version: str = "2026-02-25.clover"

    free_max_projects: int = 1
    free_max_strategies: int = 2
    free_max_runs_per_month: int = 5
    pro_max_projects: int = 10
    pro_max_strategies: int = 20
    pro_max_runs_per_month: int = 100


settings = Settings()
