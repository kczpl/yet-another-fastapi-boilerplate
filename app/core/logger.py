import logging

import structlog
from structlog.dev import ConsoleRenderer

from app.core.config import api_config as settings


def setup_logging(log_level: str | None = None, colors: bool | None = None, app: str = "api"):
    if log_level is None:
        log_level = settings.LOG_LEVEL
    if colors is None:
        colors = settings.is_development

    def _add_app(_logger, _name, event_dict):
        event_dict.setdefault("app", app)
        return event_dict

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _add_app,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if colors:
        renderer = ConsoleRenderer(colors=True)
    else:
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level.upper())

    # quiet noisy third-party loggers
    for name in ("httpx", "boto3", "botocore", "urllib3", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn re-applies its own dictConfig on boot — strip its handlers and force
    # propagation so its logs flow through our root handler in our format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    return structlog.get_logger()


log = structlog.get_logger()

bind_context = structlog.contextvars.bind_contextvars
clear_context = structlog.contextvars.clear_contextvars
unbind_context = structlog.contextvars.unbind_contextvars
