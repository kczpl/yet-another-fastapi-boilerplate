from fastapi import HTTPException


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
