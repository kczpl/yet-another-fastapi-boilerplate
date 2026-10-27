import pytest
from pydantic import ValidationError

from app.core.config import ApiConfig, CeleryConfig, DatabaseConfig


def test_explicit_empty_cors_is_respected():
    assert ApiConfig(CORS_ORIGINS=[]).CORS_ORIGINS == []


def test_explicit_pool_and_worker_settings_are_respected():
    database = DatabaseConfig(DATABASE_URL="postgresql://unused", POOL_MAX_OVERFLOW=0)
    worker = CeleryConfig(ENVIRONMENT="production", WORKER_MAX_TASKS_PER_CHILD=42)
    assert database.POOL_MAX_OVERFLOW == 0
    assert worker.WORKER_MAX_TASKS_PER_CHILD == 42


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        ApiConfig.model_validate({"ENVIRONMENT": "prodution"})


def test_docs_are_disabled_by_default_in_production():
    assert ApiConfig(ENVIRONMENT="production", SHOW_DOCS=None).SHOW_DOCS is False


@pytest.mark.parametrize("timeout", [599, 600])
def test_visibility_timeout_must_exceed_task_limit(timeout: int):
    with pytest.raises(ValidationError, match="BROKER_VISIBILITY_TIMEOUT must exceed"):
        CeleryConfig(TASK_TIME_LIMIT=600, BROKER_VISIBILITY_TIMEOUT=timeout)


def test_blocked_ips_accept_addresses_and_networks():
    config = ApiConfig.model_validate({"BLOCKED_IPS": ["203.0.113.7", "198.51.100.0/24", "2001:db8::/32"]})
    assert [str(network) for network in config.BLOCKED_IPS] == ["203.0.113.7/32", "198.51.100.0/24", "2001:db8::/32"]


def test_negative_rate_limit_is_rejected():
    with pytest.raises(ValidationError, match="RATE_LIMIT_PER_MINUTE"):
        ApiConfig.model_validate({"RATE_LIMIT_PER_MINUTE": -1})
