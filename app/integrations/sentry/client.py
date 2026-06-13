import logging
import re

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import api_config

# substring match against lowercased key — covers headers, cookies, body fields,
# and local variable names captured in stack frames.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"authorization|cookie|session|password|passwd|secret|token|api[_-]?key|"
    r"private[_-]?key|jwt|otp|dsn|x-api-key|x-auth-token",
    re.IGNORECASE,
)
_REDACTED = "[Filtered]"


def _scrub_mapping(value):
    if isinstance(value, dict):
        return {k: (_REDACTED if _SENSITIVE_KEY_PATTERN.search(k) else _scrub_mapping(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_mapping(v) for v in value]
    return value


def _scrub_event(event, _hint):
    request = event.get("request")
    if isinstance(request, dict):
        for field in ("headers", "cookies", "data", "query_string", "env"):
            if field in request:
                request[field] = _scrub_mapping(request[field])

    for exc in (event.get("exception", {}) or {}).get("values", []) or []:
        for frame in (exc.get("stacktrace", {}) or {}).get("frames", []) or []:
            if "vars" in frame:
                frame["vars"] = _scrub_mapping(frame["vars"])

    extra = event.get("extra")
    if isinstance(extra, dict):
        event["extra"] = _scrub_mapping(extra)

    return event


def init_sentry() -> None:
    if api_config.ENVIRONMENT not in ("production", "staging"):
        return
    if not api_config.SENTRY_DSN:
        return

    if api_config.is_production:
        error_sample_rate, traces_sample_rate, profiles_sample_rate, max_breadcrumbs = 1.0, 0.1, 0.1, 100
    else:
        error_sample_rate, traces_sample_rate, profiles_sample_rate, max_breadcrumbs = 0.5, 0.05, 0.05, 50

    integrations = [
        StarletteIntegration(transaction_style="endpoint", failed_request_status_codes={*range(500, 600)}),
        FastApiIntegration(transaction_style="endpoint", failed_request_status_codes={*range(500, 600)}),
        SqlalchemyIntegration(),
        CeleryIntegration(monitor_beat_tasks=True, propagate_traces=True),
        # Real exceptions are captured by the framework integrations from the raised
        # exception (better grouping than synthesizing an issue from a log line).
        LoggingIntegration(level=logging.INFO, event_level=None),
    ]
    # pydantic-ai integration is optional — only present when AI extras are installed.
    try:
        from sentry_sdk.integrations.pydantic_ai import PydanticAIIntegration

        # include_prompts also needs send_default_pii=True to record prompt/response
        # text (sends model I/O to Sentry). Keep it off unless you need that.
        integrations.append(PydanticAIIntegration(include_prompts=False))
    except ImportError:
        pass

    sentry_sdk.init(
        dsn=api_config.SENTRY_DSN,
        environment=api_config.ENVIRONMENT,
        release=api_config.SENTRY_RELEASE or f"backend@{api_config.VERSION}",
        sample_rate=error_sample_rate,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        max_breadcrumbs=max_breadcrumbs,
        attach_stacktrace=True,
        # local variables in tracebacks can leak request bodies, tokens, decrypted
        # values; keep them off in shared environments.
        include_local_variables=False,
        include_source_context=True,
        send_default_pii=False,
        max_request_body_size="medium",
        before_send=_scrub_event,
        enable_backpressure_handling=True,
        integrations=integrations,
        ignore_errors=["KeyboardInterrupt", "SystemExit", "MaxRetriesExceeded"],
    )
