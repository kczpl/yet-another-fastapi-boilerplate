import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

# from sentry_sdk.integrations.logging import LoggingIntegration
from app.core.config import config


def init_sentry():
    if config.ENVIRONMENT not in ["production", "staging"]:
        return

    if not config.SENTRY_DSN:
        return

    # environment-specific settings
    if config.ENVIRONMENT == "production":
        error_sample_rate = 1.0  # capture all errors
        traces_sample_rate = 0.3  # capture 30% of transactions
        profiles_sample_rate = 0.1  # profile 10% of transactions
        max_breadcrumbs = 100
        attach_stacktrace = True
        include_local_variables = True
    else:
        error_sample_rate = 0.5  # capture 50% of errors
        traces_sample_rate = 0.1  # capture 10% of transactions
        profiles_sample_rate = 0.05  # profile 5% of transactions
        max_breadcrumbs = 50
        attach_stacktrace = True
        include_local_variables = False  # reduce PII risk in staging

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.ENVIRONMENT,
        release=f"backend@{config.VERSION}",
        # error sampling #
        sample_rate=error_sample_rate,
        # transaction/performance sampling #
        traces_sample_rate=traces_sample_rate,
        # profiling (requires traces to be enabled) #
        profiles_sample_rate=profiles_sample_rate,
        # breadcrumbs and context #
        max_breadcrumbs=max_breadcrumbs,
        attach_stacktrace=attach_stacktrace,
        include_local_variables=include_local_variables,
        include_source_context=True,
        # PII handling #
        send_default_pii=False,  # disabled by default for privacy
        # request body capturing #
        max_request_body_size="medium",  # capture medium-sized request bodies
        # performance #
        enable_backpressure_handling=True,  # auto-adjust sampling under load
        enable_db_query_source=True,  # add source location to slow queries
        db_query_source_threshold_ms=100,  # queries slower than 100ms
        # integrations #
        integrations=[
            StarletteIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={*range(500, 600)},  # only 5xx errors
            ),
            SqlalchemyIntegration(),
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={*range(500, 600)},  # only 5xx errors
            ),
            # LoggingIntegration(
            #     level="INFO",  # capture info and above
            #     event_level="ERROR",  # send errors as events
            # ),
        ],
        # filtering #
        ignore_errors=[
            # ignore common non-critical errors
            "KeyboardInterrupt",
            "SystemExit",
            "MaxRetriesExceeded",
        ],
    )
