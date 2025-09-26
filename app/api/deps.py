from fastapi import Request, Header
from typing import Optional


def get_client_info(request: Request, user_agent: Optional[str] = Header(None, alias="user-agent")):
    ip_address = request.client.host if request.client else None
    return {"ip_address": ip_address, "user_agent": user_agent}
