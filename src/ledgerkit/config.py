from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEDGERKIT_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///ledgerkit.db"
    user_token: str | None = None
    agent_token: str | None = None


def get_settings() -> Settings:
    return Settings()
