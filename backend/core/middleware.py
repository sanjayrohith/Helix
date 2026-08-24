"""HTTP middleware: request correlation, timing and rate limiting."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.config import settings
from core.logging_config import get_logger, request_id_var

logger = get_logger("http")

# Paths that should not be logged or rate limited: probes and docs.
QUIET_PATHS = frozenset({"/health", "/metrics", "/docs", "/redoc", "/openapi.json"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the response headers a security scanner checks for first.

    HELIX is a JSON API with no server-rendered HTML, so most of the
    classic web security headers (CSP, X-Frame-Options) are defence in
    depth rather than closing an active hole here - but "this is just an
    API" is exactly the reasoning that leaves an admin endpoint one
    misconfigured reverse proxy away from being framed or content-sniffed.
    Setting them costs nothing and is what a reviewer expects to see.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        # Only meaningful over HTTPS; harmless to set unconditionally since
        # browsers ignore it on a plain HTTP response.
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to every request and log its outcome.

    The id is taken from an inbound X-Request-ID when present, so a trace
    started by a gateway carries through, and is echoed on the response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "%s %s failed after %.1f ms", request.method, request.url.path, duration_ms
            )
            request_id_var.reset(token)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"

        if request.url.path not in QUIET_PATHS:
            level = logger.warning if response.status_code >= 500 else logger.info
            level(
                "%s %s -> %d in %.1f ms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        request_id_var.reset(token)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """A sliding-window limiter for expensive endpoints.

    Only write paths are limited. Provisioning can call an LLM and run a full
    admission pass, so it is worth protecting from an accidental hot loop in a
    client; read endpoints stay unrestricted so dashboards can poll freely.
    """

    def __init__(self, app, limit: int, window_seconds: float) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _should_limit(self, request: Request) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return False
        return request.url.path not in QUIET_PATHS

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.limit <= 0 or not self._should_limit(request):
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(hits[0] + self.window_seconds - now) + 1)
                logger.warning("Rate limit hit by %s on %s", key, request.url.path)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Rate limit exceeded: {self.limit} write requests per "
                            f"{self.window_seconds:.0f}s. Retry in {retry_after}s."
                        ),
                        "code": "rate_limited",
                        # Set here rather than left to the error envelope: this
                        # response never reaches RequestContextMiddleware, since
                        # the limiter sits below it and returns directly.
                        "request_id": request_id_var.get(),
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

        return await call_next(request)


def install_middleware(app) -> None:
    """Attach HELIX's middleware stack to a FastAPI application."""
    if settings.rate_limit_per_minute > 0:
        app.add_middleware(
            RateLimitMiddleware,
            limit=settings.rate_limit_per_minute,
            window_seconds=60.0,
        )
    app.add_middleware(RequestContextMiddleware)
    # Outermost: applies to every response, including one a lower
    # middleware short-circuited (a 429 from the rate limiter, for example).
    app.add_middleware(SecurityHeadersMiddleware)
