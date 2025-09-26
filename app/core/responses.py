from typing import Union, List
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder


MESSAGES = {
    "magic_link_sent": "api.auth.magic_link_sent",
    "verification_code_sent": "api.auth.verification_code_sent",
    "logged_out": "api.auth.logged_out_successfully",
}


def response(data: Union[BaseModel, List[BaseModel]], status_code: int = 200) -> JSONResponse:
    """wrapper for returning Pydantic models as JSON responses to avoid double validation."""
    return JSONResponse(
        content=jsonable_encoder(data),
        status_code=status_code,
    )


def success_response(message_key: str, status_code: int = 200, **kwargs) -> JSONResponse:
    content = {"message": message_key}
    if kwargs:
        content["data"] = kwargs

    return JSONResponse(content=content, status_code=status_code)
