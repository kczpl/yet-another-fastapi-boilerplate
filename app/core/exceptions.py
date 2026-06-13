from typing import Never

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from app.core.errors import ERRORS
from app.core.logger import log


class APIException(HTTPException):
    def __init__(self, error_key: str, status_code: int = 500, **kwargs):
        self.error_key = error_key
        self.status_code = status_code
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


async def handle_api_exception(request: Request, exc: Exception) -> JSONResponse:
    api_exc = exc if isinstance(exc, APIException) else None
    if api_exc is None:
        raise exc

    if api_exc.status_code >= 500:
        log.error("api_error", error_key=api_exc.error_key, path=request.url.path, status=api_exc.status_code)
    else:
        log.warning("api_error", error_key=api_exc.error_key, path=request.url.path, status=api_exc.status_code)

    return JSONResponse(
        status_code=api_exc.status_code,
        content={"error": api_exc.error_key, "data": api_exc.kwargs},
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    validation_exc = exc if isinstance(exc, RequestValidationError | ValidationError) else None
    if validation_exc is None:
        raise exc

    details = []
    for error in validation_exc.errors():
        field = ".".join(str(x) for x in error.get("loc", ()))
        error_type = error.get("type", "")
        if error_type == "missing":
            message = ERRORS["required_parameter_missing"]
        elif error_type in ("value_error", "type_error"):
            message = ERRORS["invalid_request_data"]
        else:
            message = ERRORS["validation_error"]
        details.append({"field": field, "message": message, "type": error_type})

    log.warning("validation_error", details=details)
    return JSONResponse(
        status_code=422,
        content={"error": ERRORS["validation_error"], "data": {"details": details}},
    )


async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    log.error("generic_exception", exception=f"{type(exc).__name__}: {exc}", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": ERRORS["server_error"], "data": {}},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIException, handle_api_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_generic_exception)
