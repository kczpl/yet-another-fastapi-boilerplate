from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

################################################################################
# base config #
################################################################################


class Config(BaseSettings):
    VERSION: str = "0.0.1"
    ENVIRONMENT: Literal["development", "local", "staging", "production"] = "development"
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

    # Conservative defaults per process. Tune for the database connection budget.
    POOL_SIZE: int = 5
    POOL_MAX_OVERFLOW: int = 2
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 1800


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
    SHOW_DOCS: bool | None = None
    CORS_ORIGINS: list[str] = []

    @model_validator(mode="after")
    def set_environment_defaults(self) -> Self:
        if self.SHOW_DOCS is None:
            self.SHOW_DOCS = self.is_development
        return self


class CeleryConfig(Config):
    REDIS_URL: str = "redis://localhost:6379/0"
    TASK_TIME_LIMIT: int = Field(default=600, ge=2)
    BROKER_VISIBILITY_TIMEOUT: int = Field(default=3600, gt=0)
    # One task at a time per worker process — scale out by running more worker
    # containers, not by raising per-worker concurrency. Override via env if needed.
    WORKER_CONCURRENCY: int = Field(default=1, gt=0)
    WORKER_MAX_TASKS_PER_CHILD: int = Field(default=1000, gt=0)

    @model_validator(mode="after")
    def validate_visibility_timeout(self) -> Self:
        if self.BROKER_VISIBILITY_TIMEOUT <= self.TASK_TIME_LIMIT:
            raise ValueError("BROKER_VISIBILITY_TIMEOUT must exceed TASK_TIME_LIMIT")
        return self


################################################################################
# global config instances #
################################################################################

api_config = ApiConfig()
celery_config = CeleryConfig()
database_config = DatabaseConfig()  # type: ignore[call-arg]
ai_config = AIConfig()
