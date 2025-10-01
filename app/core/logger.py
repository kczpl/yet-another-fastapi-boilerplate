from typing import Any
import uuid
import structlog
from structlog.types import EventDict
from .config import config as settings


def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
    event_dict.pop("color_message", None)
    return event_dict


def generate_request_id() -> str:
    return uuid.uuid4().hex[:8]


def add_request_id(_, __, event_dict: EventDict) -> EventDict:
    try:
        from asgi_correlation_id.context import correlation_id

        request_id = correlation_id.get()
        if request_id:
            event_dict["request_id"] = request_id
    except (ImportError, LookupError):
        pass
    return event_dict


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processors": [
                add_request_id,
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        },
    },
    "handlers": {
        "console": {
            "formatter": "json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn.error": {"handlers": ["console"], "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "propagate": False},
        "httpx": {"level": "WARNING"},
        "boto3": {"level": "WARNING"},
        "botocore": {"level": "WARNING"},
        "twilio": {"level": "WARNING"},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}


def setup_logging(log_level: str = None):
    """configure structured logging with contextvars and traditional format"""

    if log_level is None:
        log_level = settings.LOG_LEVEL

    # configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_id,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ExtraAdder(),
            drop_color_message_key,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # configure standard logging with our config
    import logging.config
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning, module="<frozen importlib._bootstrap>")

    logging_config = LOGGING_CONFIG.copy()
    logging_config["root"]["level"] = log_level.upper()
    logging.config.dictConfig(logging_config)

    return structlog.get_logger(__name__)


class FastAPIStructLogger:
    def __init__(self):
        self.logger = structlog.stdlib.get_logger()

    def bind(self, **new_values: Any):
        structlog.contextvars.bind_contextvars(**new_values)

    @staticmethod
    def unbind(*keys: str):
        """remove keys from contextvars"""
        structlog.contextvars.unbind_contextvars(*keys)

    def debug(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.debug(event, *args, **kw)

    def info(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.info(event, *args, **kw)

    def warning(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.warning(event, *args, **kw)

    warn = warning

    def error(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.error(event, *args, **kw)

    def critical(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.critical(event, *args, **kw)

    def exception(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.exception(event, *args, **kw)


def clear_context():
    """clear all contextvars - useful for testing"""
    structlog.contextvars.clear_contextvars()


def bind_context(**kwargs):
    """bind values to contextvars"""
    structlog.contextvars.bind_contextvars(**kwargs)


log = FastAPIStructLogger()
