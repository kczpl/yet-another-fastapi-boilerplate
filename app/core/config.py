from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

################################################################################
# domain-specific configs #
################################################################################


class DatabaseConfig(BaseSettings):
    DATABASE_URL: str = Field(...)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class AWSConfig(BaseSettings):
    AWS_REGION: str = "eu-central-1"
    AWS_ACCESS_KEY: str | None = None
    AWS_SECRET_KEY: str | None = None

    EMAIL_DOMAIN: str | None = None
    S3_BUCKET_NAME: str | None = None
    S3_PUBLIC_BUCKET_NAME: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class IntegrationsConfig(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


################################################################################
# main application config #
################################################################################


class Config(BaseSettings):
    VERSION: str = "0.0.1"
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "UTC"
    LOG_LEVEL: str = "INFO"
    SHOW_DOCS: bool = True

    API_DOMAIN: str = "localhost:8000"
    FRONTEND_DOMAIN: str = "localhost:3000"

    SENTRY_DSN: str | None = None

    CORS_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def set_environment_defaults(self) -> Self:
        if self.is_production:
            self.SHOW_DOCS = False

        if not self.CORS_ORIGINS:
            if self.is_production:
                self.CORS_ORIGINS = ["https://frontend.example.com", "https://app.example.com"]
            elif self.is_staging:
                self.CORS_ORIGINS = ["https://frontend-staging.example.com"]
            else:
                self.CORS_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]

        return self

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
# global config instances #
################################################################################


config = Config()
database_config = DatabaseConfig()
aws_config = AWSConfig()
integrations_config = IntegrationsConfig()
