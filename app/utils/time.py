from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import api_config


def utc_now() -> datetime:
    return datetime.now(UTC)


def business_date(moment: datetime) -> date:
    # A UTC date is the wrong day near midnight for a business outside UTC.
    return moment.astimezone(ZoneInfo(api_config.BUSINESS_TIMEZONE)).date()


def business_today() -> date:
    # Use this, not date.today(): servers run in UTC, and ruff DTZ rejects a naive date.
    return business_date(utc_now())
