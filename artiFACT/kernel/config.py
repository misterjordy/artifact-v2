"""Environment-based configuration loader."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_db"
    REDIS_URL: str = "redis://redis:6379"
    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "artifact-dev"
    SECRET_KEY: str = "change-me-in-production"
    APP_ENV: str = "development"
    CORS_ORIGINS: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
