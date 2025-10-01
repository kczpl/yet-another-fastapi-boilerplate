from fastapi import HTTPException, FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from app.core.errors import ERRORS
from app.core.logger import log


class APIException(HTTPException):
    def __init__(
        self,
        error_key: str,
        status_code: int = 500,
        **kwargs,
    ):
        self.error_key = error_key
        self.status_code = status_code
        self.kwargs = kwargs
        super().__init__(status_code=status_code, detail=error_key)


def raise_not_found(error_key: str, **kwargs) -> APIException:
    raise APIException(error_key, 404, **kwargs)


def raise_bad_request(error_key: str, **kwargs) -> APIException:
    raise APIException(error_key, 400, **kwargs)


def raise_unauthorized(error_key: str, **kwargs) -> APIException:
    raise APIException(error_key, 401, **kwargs)


def raise_forbidden(error_key: str, **kwargs) -> APIException:
    raise APIException(error_key, 403, **kwargs)


def raise_conflict(error_key: str, **kwargs) -> APIException:
    raise APIException(error_key, 409, **kwargs)


def raise_validation_error(error_key: str, **kwargs) -> APIException:
    raise APIException(error_key, 422, **kwargs)


def raise_server_error(error_key: str = "general.internal_error", **kwargs) -> APIException:
    raise APIException(error_key, 500, **kwargs)


async def handle_api_exception(request: Request, exc: APIException) -> JSONResponse:
    log.error(f"api error: {exc.error_key}", path=request.url.path, status=exc.status_code, exc_info=str(exc))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_key, "data": exc.kwargs},
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []

    for error in exc.errors():
        field = ".".join(str(x) for x in error.get("loc", ()))
        error_type = error.get("type", "")

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


def setup_exception_handlers(app: FastAPI):
    app.add_exception_handler(APIException, handle_api_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_generic_exception)
