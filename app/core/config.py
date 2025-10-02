from pydantic_settings import BaseSettings
from pydantic import ConfigDict, model_validator
from typing_extensions import Self


################################################################################
# domain-specific configs #
################################################################################


class AuthConfig(BaseSettings):
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class DatabaseConfig(BaseSettings):
    DATABASE_URL: str

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class AWSConfig(BaseSettings):
    AWS_REGION: str = "eu-central-1"
    AWS_ACCESS_KEY: str | None = None
    AWS_SECRET_KEY: str | None = None
    SES_DOMAIN: str | None = None
    S3_BUCKET_NAME: str | None = None
    S3_PUBLIC_BUCKET_NAME: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class IntegrationsConfig(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


################################################################################
# main application config #
################################################################################


class Settings(BaseSettings):
    # info #
    VERSION: str = "0.0.1"
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "UTC"
    LOG_LEVEL: str = "INFO"
    # domains #
    API_DOMAIN: str = "localhost:8000"
    FRONTEND_DOMAIN: str = "localhost:3000"

    # sentry #
    SENTRY_DSN: str | None = None
    # encryption #
    ENCRYPTION_SECRET_KEY: str | None = None
    ENCRYPTION_SALT: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def set_environment_defaults(self) -> Self:
        """Set environment-specific defaults if not overridden by ENV vars."""
        env_defaults = {
            "production": {
                "API_DOMAIN": "api.example.com",
                "FRONTEND_DOMAIN": "frontend.example.com",
            },
            "staging": {
                "API_DOMAIN": "api-staging.example.com",
                "FRONTEND_DOMAIN": "frontend-staging.example.com",
            },
        }

        # Only apply defaults if using default values
        defaults = env_defaults.get(self.ENVIRONMENT.lower(), {})
        for key, value in defaults.items():
            if getattr(self, key) == "localhost:8000" or getattr(self, key) == "localhost:3000":
                setattr(self, key, value)

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
# helper functions #
################################################################################


def get_app_config(config: Settings) -> dict:
    SHOW_DOCS_ENVIRONMENT = ("development", "local")
    app_configs = {
        "title": "FastAPI Boilerplate",
        "version": config.VERSION,
    }
    if config.ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
        app_configs["openapi_url"] = None  # hide docs

    return app_configs


################################################################################
# global config instances #
################################################################################


config = Settings()
app_config = get_app_config(config)
auth_config = AuthConfig()
database_config = DatabaseConfig()
aws_config = AWSConfig()
integrations_config = IntegrationsConfig()
