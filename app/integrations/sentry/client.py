import logging
import re
from collections.abc import Iterator

import sentry_sdk
from celery.exceptions import MaxRetriesExceededError
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.pydantic_ai import PydanticAIIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import api_config

# Substring match against lowercased keys — covers headers, cookies, body fields,
# and local variable names captured in stack frames.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"authorization|cookie|session|password|passwd|secret|token|api[_-]?key|"
    r"private[_-]?key|jwt|otp|dsn|x-api-key|x-auth-token",
    re.IGNORECASE,
)
_REDACTED = "[Filtered]"
_SERVER_ERRORS = {*range(500, 600)}


def _scrub(value):
    # Recursively replaces values under sensitive keys; other values pass through.
    if isinstance(value, dict):
        return {key: _scrub_field(key, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _scrub_field(key: str, value):
    return _REDACTED if _SENSITIVE_KEY_PATTERN.search(key) else _scrub(value)


def _stack_frames(event) -> Iterator[dict]:
    for exception in event.get("exception", {}).get("values") or []:
        yield from exception.get("stacktrace", {}).get("frames") or []


def _scrub_event(event, _hint):
    for key in ("request", "extra"):
        if key in event:
            event[key] = _scrub(event[key])
    for frame in _stack_frames(event):
        if "vars" in frame:
            frame["vars"] = _scrub(frame["vars"])
    return event


def init_sentry() -> None:
    if not (api_config.is_production or api_config.is_staging):
        return
    if not api_config.SENTRY_DSN:
        return

    production = api_config.is_production
    sentry_sdk.init(
        dsn=api_config.SENTRY_DSN,
        environment=api_config.ENVIRONMENT,
        release=api_config.SENTRY_RELEASE or f"backend@{api_config.VERSION}",
        sample_rate=1.0 if production else 0.5,
        traces_sample_rate=0.1 if production else 0.05,
        profiles_sample_rate=0.1 if production else 0.05,
        max_breadcrumbs=100 if production else 50,
        attach_stacktrace=True,
        # local variables in tracebacks can leak request bodies, tokens, decrypted
        # values; keep them off in shared environments.
        include_local_variables=False,
        include_source_context=True,
        send_default_pii=False,
        max_request_body_size="medium",
        before_send=_scrub_event,
        enable_backpressure_handling=True,
        integrations=[
            StarletteIntegration(transaction_style="endpoint", failed_request_status_codes=_SERVER_ERRORS),
            FastApiIntegration(transaction_style="endpoint", failed_request_status_codes=_SERVER_ERRORS),
            SqlalchemyIntegration(),
            CeleryIntegration(monitor_beat_tasks=True, propagate_traces=True),
            # Real exceptions are captured by the framework integrations from the raised
            # exception (better grouping than synthesizing an issue from a log line).
            LoggingIntegration(level=logging.INFO, event_level=None),
            # include_prompts also needs send_default_pii=True to record prompt/response
            # text (sends model I/O to Sentry). Keep it off unless you need that.
            PydanticAIIntegration(include_prompts=False),
        ],
        # Pass classes, not strings — Sentry matches strings against the exact type
        # name, so a near-miss (e.g. "MaxRetriesExceeded") silently filters nothing.
        ignore_errors=[KeyboardInterrupt, SystemExit, MaxRetriesExceededError],
    )
