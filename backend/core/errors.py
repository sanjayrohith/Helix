"""Centralised error handling.

FastAPI's default behaviour for an uncaught exception is to return a bare 500
with no body in production, but several deployment configurations (uvicorn
`--reload`, a debug-mode ASGI wrapper, a misconfigured proxy) can surface the
traceback to the client. This module makes the safe behaviour explicit and
uniform instead of depending on how the process happens to be launched: every
error - handled or not - comes back as the same JSON shape, is logged with
the request's correlation id, and never includes exception internals.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.logging_config import get_logger, request_id_var

logger = get_logger("errors")


def _error_body(detail: str, code: str, request_id: str | None) -> dict:
    return {"detail": detail, "code": code, "request_id": request_id}


def install_error_handlers(app: FastAPI) -> None:
    """Register exception handlers that give every error a uniform shape."""

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's raw errors are useful for API consumers, so they are kept,
        # just wrapped in the same envelope as every other error. The 'ctx' key
        # can hold a raw exception object (e.g. the ValueError from a custom
        # field_validator) which is not JSON-serialisable, so it is excluded -
        # exactly what FastAPI's own default handler does, and the reason a
        # naive `exc.errors()` here would 500 instead of 422.
        request_id = request_id_var.get()
        return JSONResponse(
            status_code=422,  # numeric: the named constant was renamed between Starlette versions
            content={
                "detail": jsonable_encoder(exc.errors(), exclude={"ctx"}),
                "code": "validation_error",
                "request_id": request_id,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Covers both fastapi.HTTPException and Starlette's own (e.g. 404 on
        # an unmatched route), so every deliberate error response is uniform.
        request_id = request_id_var.get()
        code = _code_for_status(exc.status_code)
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(str(exc.detail), code, request_id),
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # The only handler that can leak internals if written carelessly, so
        # it does the least: log the full exception server-side with the
        # request id for correlation, and tell the client nothing beyond
        # that id and a generic message.
        request_id = request_id_var.get() or str(uuid.uuid4())
        logger.exception(
            "Unhandled exception on %s %s [%s]",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "An unexpected error occurred. Reference this request id if you report it.",
                "internal_error",
                request_id,
            ),
        )


def _code_for_status(status_code: int) -> str:
    """A stable, machine-readable code for a common HTTP status."""
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        412: "precondition_failed",
        413: "payload_too_large",
        422: "validation_error",
        429: "rate_limited",
        502: "upstream_error",
        503: "unavailable",
    }.get(status_code, "error")


__all__ = ["install_error_handlers", "HTTPException"]
