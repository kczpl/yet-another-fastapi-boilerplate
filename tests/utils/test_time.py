from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.core.config import ApiConfig, api_config
from app.utils.time import business_date


def test_business_date_follows_the_business_timezone_after_utc_midnight(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_config, "BUSINESS_TIMEZONE", "Europe/Warsaw")

    assert business_date(datetime(2026, 11, 17, 23, 30, tzinfo=UTC)) == date(2026, 11, 18)
    assert business_date(datetime(2026, 11, 17, 22, 59, tzinfo=UTC)) == date(2026, 11, 17)


def test_unknown_business_timezone_is_rejected():
    with pytest.raises(ValidationError, match="unknown timezone"):
        ApiConfig(BUSINESS_TIMEZONE="Europe/Warsow")
