"""Application settings, loaded from environment variables / a local .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "ai_soc_assistant"
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    bcrypt_rounds: int = 12  # tests lower this to 4 for speed
    environment: str = "development"  # set to "production" when deployed
    registration_invite_code: str = ""  # if set, self-registration requires this code
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_admin_password: str = "Admin@12345"
    seed_analyst_password: str = "Analyst@12345"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
