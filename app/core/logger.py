from typing import Any
import structlog
from structlog.types import EventDict
from .config import config as settings


def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
    """
    Uvicorn logs the message a second time in the extra `color_message`, but we don't
    need it. This processor drops the key from the event dict if it exists.
    """
    event_dict.pop("color_message", None)
    return event_dict


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": structlog.stdlib.ProcessorFormatter,
            "foreign_pre_chain": [
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.stdlib.ExtraAdder(),
                drop_color_message_key,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
            ],
            "processors": [
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        },
        "access": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
        "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
        "httpx": {"level": "WARNING", "handlers": ["default"], "propagate": False},
        "boto3": {"level": "WARNING", "handlers": ["default"], "propagate": False},
        "botocore": {"level": "WARNING", "handlers": ["default"], "propagate": False},
        "twilio": {"level": "WARNING", "handlers": ["default"], "propagate": False},
    },
    "root": {"level": "INFO", "handlers": ["default"], "propagate": False},
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
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ExtraAdder(),
            drop_color_message_key,
            structlog.processors.TimeStamper(fmt="iso"),
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

    # suppress SWIG deprecation warnings from native dependencies
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="<frozen importlib._bootstrap>")

    logging_config = LOGGING_CONFIG.copy()
    logging_config["root"]["level"] = log_level.upper()
    logging.config.dictConfig(logging_config)

    return structlog.get_logger(__name__)


class FastAPIStructLogger:
    """simplified structlog wrapper with contextvars support"""

    def __init__(self):
        self.logger = structlog.stdlib.get_logger()

    def bind(self, **new_values: Any):
        """bind values to contextvars for automatic inclusion in all log entries"""
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


# # convenience functions
# def get_logger() -> FastAPIStructLogger:
#     """get a FastAPIStructLogger instance with contextvars support"""
#     return FastAPIStructLogger()


def clear_context():
    """clear all contextvars - useful for testing"""
    structlog.contextvars.clear_contextvars()


def bind_context(**kwargs):
    """bind values to contextvars"""
    structlog.contextvars.bind_contextvars(**kwargs)


log = FastAPIStructLogger()
