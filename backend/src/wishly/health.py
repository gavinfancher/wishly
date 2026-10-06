"""Ops endpoints. Unauthenticated, outside /v1, never part of the public API."""

import psycopg
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz(request: Request) -> dict[str, str]:
    """Liveness: the process is up and can answer HTTP.

    Deliberately checks nothing else. If this touched the database, a database
    outage would make the watchdog think the VM is dead and fail over to ECS,
    where the database is just as down.
    """
    return {"status": "ok", "version": request.app.state.settings.version}


@router.get("/readyz")
def readyz(request: Request) -> dict[str, str]:
    """Readiness: we can do real work, i.e. the database answers.

    503 tells a load balancer "don't send me traffic yet" without implying
    the process should be restarted.
    """
    try:
        # timeout: give up waiting for a pooled connection after 2s rather
        # than hanging the probe.
        with request.app.state.pool.connection(timeout=2) as conn:
            conn.execute("select 1")
    except psycopg.Error as exc:  # also covers the pool's PoolTimeout
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
