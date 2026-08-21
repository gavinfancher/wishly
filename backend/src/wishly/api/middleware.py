"""Request-scoped logging middleware (PLAN T8.2).

Every request gets an id, and every response logs one structured line with the
method, path, status, and duration. The id is echoed back as ``X-Request-ID`` so
a user-reported problem can be traced to an exact log line, and it is attached to
the context so domain logs emitted while handling the request carry it too.

An inbound ``X-Request-ID`` is honoured (so a proxy or client can correlate) but
validated: it is untrusted input, and an unbounded header would otherwise be
written verbatim into the logs.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from wishly.core.logging import get_logger

logger = get_logger("wishly.api.request")

#: Current request id, readable by any code handling the request.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Conservative: ids appear verbatim in logs, so refuse anything exotic.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")

# Paths that would otherwise flood the logs — the container healthcheck hits
# /health every 15s, which is noise, not signal.
_QUIET_PATHS = frozenset({"/health", "/ready"})


def current_request_id() -> str | None:
    """The id of the request being handled, if any."""
    return request_id_ctx.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign a request id, time the request, and log the outcome."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inbound = request.headers.get("x-request-id", "")
        request_id = inbound if _SAFE_ID.match(inbound) else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Log before re-raising: the exception handler turns this into a 500
            # response, and without this line the failure has no request context.
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        if request.url.path not in _QUIET_PATHS:
            # 5xx is a defect; 4xx is usually the client's problem but still worth
            # seeing, so it is logged a level up from the ordinary case.
            level = (
                logger.error
                if response.status_code >= 500
                else logger.warning
                if response.status_code >= 400
                else logger.info
            )
            level(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response
