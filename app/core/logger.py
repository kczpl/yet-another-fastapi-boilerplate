import logging

import structlog
from structlog.dev import ConsoleRenderer

from .config import config as settings


def setup_logging(log_level: str | None = None, json_logs: bool = False):
    if log_level is None:
        log_level = settings.LOG_LEVEL

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        # production: JSON output
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()
    else:
        # development: colorized console output (don't add format_exc_info)
        renderer = ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ]
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level.upper())

    # quiet noisy loggers
    for name in ("httpx", "boto3", "botocore", "twilio", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return structlog.get_logger()


log = structlog.get_logger()

bind_context = structlog.contextvars.bind_contextvars
clear_context = structlog.contextvars.clear_contextvars
unbind_context = structlog.contextvars.unbind_contextvars
