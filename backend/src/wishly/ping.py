"""GET /internal/ping — the AWS watchdog Lambda calls this every minute.

Unlike /healthz, this answers "is Wishly actually working?": the database
answers and the scheduler is still ticking. Any non-200 counts as down, and
five minutes of down sends a push notification (infra/terraform/watchdog.tf).

It's public (through api.<domain>), so it's guarded twice:
  - a shared ping key, `Authorization: Bearer <WISHLY_PING_TOKEN>`;
  - a per-client rate limit, checked first, so the key can't be brute-forced.
"""

from datetime import UTC, datetime

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request

from wishly.auth import require_ping_token

# The watchdog sends one request a minute; this leaves room for a manual curl.
PINGS_PER_MINUTE = 10


def rate_limit(request: Request) -> None:
    # Behind the Cloudflare Tunnel every request arrives from cloudflared, so the
    # real client is in CF-Connecting-IP, which Cloudflare sets and overwrites.
    client = request.headers.get("cf-connecting-ip") or (
        request.client.host if request.client else "unknown"
    )
    if not request.app.state.ping_limiter.allow(client):
        raise HTTPException(status_code=429, detail="slow down", headers={"Retry-After": "60"})


# Dependencies run in order: the rate limit applies before the key is checked.
router = APIRouter(dependencies=[Depends(rate_limit), Depends(require_ping_token)])


@router.get("/internal/ping")
def ping(request: Request) -> dict[str, str | None]:
    try:
        with request.app.state.pool.connection(timeout=2) as conn:
            conn.execute("select 1")
    except psycopg.Error as exc:  # also covers the pool's PoolTimeout
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    scheduler = request.app.state.scheduler
    if scheduler is not None and scheduler.stalled(datetime.now(UTC)):
        raise HTTPException(status_code=503, detail="scheduler stalled")

    last = scheduler.last_tick_at if scheduler else None
    return {
        "status": "ok",
        "version": request.app.state.settings.version,
        "last_send_run": last.isoformat(timespec="seconds") if last else None,
    }
