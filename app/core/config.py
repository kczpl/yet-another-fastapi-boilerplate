import os
import json
import boto3
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    VERSION: str = "0.0.1"
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "UTC"
    LOG_LEVEL: str = "INFO"

    # URL #
    API_DOMAIN: str = "api.example.com"
    FRONTEND_DOMAIN: str = "frontend.example.com"
    # DB #
    DATABASE_URL: str
    # AWS #
    SES_DOMAIN: str | None = None  # non-secret
    S3_BUCKET_NAME: str | None = None  # non-secret
    S3_PUBLIC_BUCKET_NAME: str | None = None  # non-secret
    # for local development #
    AWS_ACCESS_KEY: str | None = None
    AWS_SECRET_KEY: str | None = None
    # JWT #
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    model_config = ConfigDict(env_file="../.env", env_file_encoding="utf-8")


def load_config() -> Settings:
    # environment and secret name are passed as environment variables in task definition
    environment = os.getenv("ENVIRONMENT", "development").lower()
    secret_name = os.getenv("AWS_SECRET_NAME")
    region = os.getenv("AWS_REGION", "eu-central-1")

    if environment in ["production", "staging"]:
        config = _load_from_secrets_manager(secret_name, region, environment)
    else:
        config = _load_from_dotenv(environment)

    config = _add_non_secret_variables(config)
    return config


################################################################################
# Loading environment variables #
################################################################################


def _load_from_secrets_manager(secret_name: str, region: str, environment: str) -> Settings:
    if not secret_name:
        raise ValueError("secret_name is required for production/staging environment")

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])
        secret_data["ENVIRONMENT"] = environment

        config = Settings(**secret_data)

        return config

    except Exception as e:
        raise Exception(f"Failed to load from AWS Secrets Manager: {e}")


def _load_from_dotenv(environment: str) -> Settings:
    load_dotenv()
    config = Settings()
    config.ENVIRONMENT = environment
    return config


################################################################################
# Load non-secret variables #
################################################################################


def _add_non_secret_variables(config: Settings) -> Settings:
    env_configs = {
        "production": {
            "API_DOMAIN": "api.example.com",
        },
        "staging": {
            "API_DOMAIN": "api-staging.example.com",
        },
        "development": {
            "API_DOMAIN": "api-staging.example.com",
            "SES_DOMAIN": "mail.staging.myapp.com",
        },
    }

    values = env_configs.get(config.ENVIRONMENT)
    for key, value in values.items():
        setattr(config, key, value)

    return config


# global config instance
config = load_config()
