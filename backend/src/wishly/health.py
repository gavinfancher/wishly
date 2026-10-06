"""Ops endpoints. Unauthenticated, outside /v1, never part of the public API."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz(request: Request) -> dict[str, str]:
    """Liveness: the process is up and can answer HTTP.

    Deliberately checks nothing else. If this touched the database, a database
    outage would make the watchdog think the VM is dead and fail over to ECS,
    where the database is just as down.
    """
    return {"status": "ok", "version": request.app.state.settings.version}
