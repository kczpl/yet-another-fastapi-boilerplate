from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

################################################################################
# base config #
################################################################################


class Config(BaseSettings):
    VERSION: str = "0.0.1"
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "UTC"
    LOG_LEVEL: str = "INFO"

    SENTRY_DSN: str | None = None
    SENTRY_RELEASE: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT.lower() == "staging"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in ("development", "local")


################################################################################
# domain-specific configs #
################################################################################


class DatabaseConfig(Config):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    POOL_SIZE: int | None = None
    POOL_MAX_OVERFLOW: int | None = None
    POOL_TIMEOUT: int | None = None
    POOL_RECYCLE: int | None = None

    @model_validator(mode="after")
    def set_environment_defaults(self) -> Self:
        if self.is_production:
            self.POOL_SIZE = self.POOL_SIZE or 20
            self.POOL_MAX_OVERFLOW = self.POOL_MAX_OVERFLOW or 10
            self.POOL_TIMEOUT = self.POOL_TIMEOUT or 30
            self.POOL_RECYCLE = self.POOL_RECYCLE or 3600
        elif self.is_staging:
            self.POOL_SIZE = self.POOL_SIZE or 15
            self.POOL_MAX_OVERFLOW = self.POOL_MAX_OVERFLOW or 5
            self.POOL_TIMEOUT = self.POOL_TIMEOUT or 30
            self.POOL_RECYCLE = self.POOL_RECYCLE or 3600
        else:
            self.POOL_SIZE = self.POOL_SIZE or 5
            self.POOL_MAX_OVERFLOW = self.POOL_MAX_OVERFLOW or 2
            self.POOL_TIMEOUT = self.POOL_TIMEOUT or 30
            self.POOL_RECYCLE = self.POOL_RECYCLE or 1800

        return self


class AWSConfig(Config):
    # Credentials are only needed for AWS Bedrock (AI agents). Leave unset to fall
    # back to the default boto3 credential chain (env / profile / instance role).
    AWS_REGION: str = "eu-central-1"
    AWS_ACCESS_KEY: str | None = None
    AWS_SECRET_KEY: str | None = None


class AIConfig(Config):
    # Bedrock inference-profile ids are account- and region-specific — set the exact
    # ids enabled for your account. Defaults target EU inference profiles.
    BEDROCK_MODEL: str = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
    BEDROCK_MODEL_HAIKU: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    BEDROCK_REGION: str = "eu-central-1"

    AI_MAX_TOKENS: int = 8_192
    AI_REQUEST_LIMIT: int = 10
    AI_REQUEST_TOKEN_LIMIT: int = 200_000


################################################################################
# application configs #
################################################################################


class ApiConfig(Config):
    SHOW_DOCS: bool = True
    API_URL: str | None = None
    FRONTEND_URL: str | None = None
    CORS_ORIGINS: list[str] = []

    @model_validator(mode="after")
    def set_environment_defaults(self) -> Self:
        if self.is_production:
            self.API_URL = self.API_URL or "https://api.example.com"
            self.FRONTEND_URL = self.FRONTEND_URL or "https://app.example.com"
            self.CORS_ORIGINS = self.CORS_ORIGINS or ["https://app.example.com"]
            self.SHOW_DOCS = False
        elif self.is_staging:
            self.API_URL = self.API_URL or "https://api-staging.example.com"
            self.FRONTEND_URL = self.FRONTEND_URL or "https://app-staging.example.com"
            self.CORS_ORIGINS = self.CORS_ORIGINS or ["https://app-staging.example.com"]
        else:
            self.API_URL = self.API_URL or "http://localhost:8000"
            self.FRONTEND_URL = self.FRONTEND_URL or "http://localhost:3000"
            self.CORS_ORIGINS = self.CORS_ORIGINS or [
                "http://localhost:3000",
                "http://localhost:5173",
            ]

        return self


class CeleryConfig(Config):
    TASK_TIME_LIMIT: int = 600
    # One task at a time per worker process — scale out by running more worker
    # containers, not by raising per-worker concurrency. Override via env if needed.
    WORKER_CONCURRENCY: int = 1
    WORKER_MAX_TASKS_PER_CHILD: int = 1000

    @model_validator(mode="after")
    def set_environment_defaults(self) -> Self:
        if self.is_production:
            self.WORKER_MAX_TASKS_PER_CHILD = 500
        return self


################################################################################
# global config instances #
################################################################################

api_config = ApiConfig()
celery_config = CeleryConfig()
database_config = DatabaseConfig()  # type: ignore[call-arg]
aws_config = AWSConfig()
ai_config = AIConfig()
