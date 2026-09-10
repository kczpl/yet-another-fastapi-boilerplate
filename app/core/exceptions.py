from collections.abc import Mapping
from typing import Never, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.errors import ERRORS
from app.core.logger import log


class APIException(HTTPException):
    def __init__(self, error_key: str, status_code: int = 500, **kwargs):
        if error_key not in ERRORS:
            raise ValueError(f"unregistered error key {error_key!r} — add it to ERRORS in app/core/errors.py")
        self.error_key = error_key
        self.kwargs = kwargs
        super().__init__(status_code=status_code, detail=error_key)


def raise_not_found(error_key: str, **kwargs) -> Never:
    raise APIException(error_key, 404, **kwargs)


def raise_bad_request(error_key: str, **kwargs) -> Never:
    raise APIException(error_key, 400, **kwargs)


def raise_unauthorized(error_key: str, **kwargs) -> Never:
    raise APIException(error_key, 401, **kwargs)


def raise_forbidden(error_key: str, **kwargs) -> Never:
    raise APIException(error_key, 403, **kwargs)


def raise_conflict(error_key: str, **kwargs) -> Never:
    raise APIException(error_key, 409, **kwargs)


def raise_validation_error(error_key: str, **kwargs) -> Never:
    raise APIException(error_key, 422, **kwargs)


def raise_server_error(error_key: str = "server_error", **kwargs) -> Never:
    raise APIException(error_key, 500, **kwargs)


# Errors raised by the framework itself (unknown route, wrong method, ...) are
# mapped onto the same envelope so clients never see Starlette's {"detail": ...}.
_HTTP_STATUS_ERRORS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    422: "validation_error",
}
_VALIDATION_MESSAGES = {
    "missing": ERRORS["required_parameter_missing"],
    "value_error": ERRORS["invalid_request_data"],
}


def _error_response(
    status_code: int, error_key: str, data: dict, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    # Wire format carries the i18n key (like MESSAGES); the short key stays in logs.
    return JSONResponse(status_code=status_code, content={"error": ERRORS[error_key], "data": data}, headers=headers)


# Starlette dispatches by registered exception type; casts narrow its generic signature.


async def handle_api_exception(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(APIException, exc)
    logger = log.error if exc.status_code >= 500 else log.warning
    logger("api_error", error_key=exc.error_key, path=request.url.path, status=exc.status_code)
    return _error_response(exc.status_code, exc.error_key, exc.kwargs)


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(HTTPException, exc)
    fallback = "server_error" if exc.status_code >= 500 else "bad_request"
    error_key = _HTTP_STATUS_ERRORS.get(exc.status_code, fallback)
    log.warning("http_error", detail=exc.detail, path=request.url.path, status=exc.status_code)
    return _error_response(exc.status_code, error_key, {"detail": exc.detail}, headers=exc.headers)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": _VALIDATION_MESSAGES.get(error["type"], ERRORS["validation_error"]),
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    log.warning("validation_error", path=request.url.path, details=details)
    return _error_response(422, "validation_error", {"details": details})


async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", exc_info=exc, path=request.url.path)
    return _error_response(500, "server_error", {})


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIException, handle_api_exception)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_generic_exception)
