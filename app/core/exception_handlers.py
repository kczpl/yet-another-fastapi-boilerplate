from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.exceptions import APIException, raise_server_error
from app.core.errors import ERRORS
from app.core.logger import log


async def handle_api_exception(request: Request, exc: APIException) -> JSONResponse:
    # use appropriate log level based on status code
    # 5xx errors go to Sentry, 4xx errors are logged locally only
    if exc.status_code >= 500:
        log.error(
            f"api error: {exc.error_key}",
            path=request.url.path,
            status=exc.status_code,
            exc_info=str(exc),
        )
    else:
        log.warning(
            f"api error: {exc.error_key}",
            path=request.url.path,
            status=exc.status_code,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_key, "data": exc.kwargs},
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []

    for error in exc.errors():
        # create simple field path
        field = ".".join(str(x) for x in error.get("loc", ()))
        error_type = error.get("type", "")

        # map pydantic error types to ERRORS keys
        if error_type == "missing":
            message = ERRORS["required_parameter_missing"]
        elif error_type in ["value_error", "type_error"]:
            message = ERRORS["invalid_request_data"]
        else:
            message = ERRORS["validation_error"]

        details.append({"field": field, "message": message, "type": error_type})

    log.error(f"validation error: {details}", exc_info=str(exc))
    return JSONResponse(
        status_code=422,
        content={
            "error": ERRORS["validation_error"],
            "data": {"details": details},
        },
    )


async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    log.error(f"generic exception: {exc}", exc_info=str(exc), path=request.url.path)
    raise_server_error(ERRORS["server_error"])


def setup_exception_handlers(app):
    app.add_exception_handler(APIException, handle_api_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_generic_exception)
