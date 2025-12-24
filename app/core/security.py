import time
import uuid
from typing import Callable

from fastapi import HTTPException, Request, Response
from guard.middleware import SecurityMiddleware
from guard.models import SecurityConfig
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import config
from app.core.logger import bind_context, clear_context, log

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        clear_context()

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")

        bind_context(request_id=request_id)

        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        log.info(
            "completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=f"{duration:.3f}s",
            client_ip=client_ip,
        )

        response.headers["X-Request-ID"] = request_id
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_REQUEST_SIZE:
                raise HTTPException(status_code=413, detail="Request body too large")

        return await call_next(request)


def get_guard_security_config() -> SecurityConfig:
    return SecurityConfig(
        # Rate limiting
        rate_limit=1000,
        rate_limit_window=60,
        # Auto-ban settings - threshold for auto-banning an IP address
        # auto_ban_threshold=20,
        # auto_ban_duration=3600,
        # HTTPS enforcement
        enforce_https=False,
        # CORS configuration
        enable_cors=True,
        cors_allow_origins=config.CORS_ORIGINS if config.CORS_ORIGINS else ["*"],
        cors_allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        cors_allow_headers=["*"],
        cors_allow_credentials=True,
        cors_expose_headers=["Content-Length", "X-Filename", "X-Request-ID"],
        cors_max_age=86400,
        # Block requests from cloud provider IPs
        block_cloud_providers=set(),
        # User agent filtering
        blocked_user_agents=[],
        # Country blocking
        blocked_countries=[],
        # IP lists
        whitelist=[],
        blacklist=[],
        # Penetration detection
        enable_penetration_detection=True,
        # HTTP Security Headers (API-focused)
        security_headers={
            "enabled": True,
            "hsts": {
                "max_age": 31536000,
                "include_subdomains": True,
                "preload": True,
            },
            "frame_options": "DENY",
            "content_type_options": "nosniff",
            "referrer_policy": "strict-origin-when-cross-origin",
            "cross_origin_resource_policy": "same-origin",
        },
    )


def setup_security_middleware(app) -> None:
    guard_config = get_guard_security_config()
    app.add_middleware(SecurityMiddleware, config=guard_config)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
