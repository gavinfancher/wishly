"""Machine-triggered routes: the hourly send, the preview, and a liveness probe.

Everything here is called by infrastructure, never by the SPA. Two callers:

* **An EventBridge scheduled rule** POSTs ``/internal/runs/send-reminders`` every
  hour through the Cloudflare Tunnel (``infra/terraform/schedule.tf``). This is
  what replaced Prefect Cloud's scheduler.
* **The detector Lambda** GETs ``/internal/liveness`` every minute to decide
  whether to fail over to ECS (``infra/lambda/detector/handler.py``).

AUTH IS A SHARED SECRET, NOT A SESSION. Neither caller has a Clerk user, so
``get_current_user`` does not apply; these routes compare a token in the
``X-Wishly-Trigger`` header instead. That means this module must not grow a route
that reads or writes one user's data — the token authenticates a *machine*, and
it authorises nothing in particular.

REJECTIONS ARE 403, NOT 401. EventBridge retries 401, 407, 409, 429 and 5xx, up
to 185 times over 24 hours; it never retries 403. A mistyped token is a
configuration error that will not fix itself, so it should fail once and be
visible, not hammer the tunnel for a day.

WHY THE SEND RETURNS 202. An EventBridge API destination times out after five
seconds and counts it a failure. One Resend call is allowed thirty
(``RESEND_TIMEOUT_SECONDS``), and a run sends as many as are due. So the route
authenticates, hands the work to a background task, and answers immediately.
The trade is that EventBridge always sees success: what actually happened is in
the logs, in ``notification_log``, and in ``GET /notifications``.
"""

from __future__ import annotations

import hmac
import os
import threading
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from wishly.api.errors import unprocessable
from wishly.core.logging import get_logger
from wishly.core.settings import settings
from wishly.orchestration.preview import DEFAULT_DAYS_BEFORE, PreviewError, preview_reminder
from wishly.orchestration.runner import send_reminders

logger = get_logger("wishly.api.internal")

router = APIRouter(prefix="/internal", tags=["internal"])

#: Header the trigger token travels in. Also configured on the EventBridge
#: connection in ``infra/terraform/schedule.tf`` — the two must agree.
TRIGGER_HEADER = "X-Wishly-Trigger"

# One run at a time per process. The claim-before-send protocol in
# `wishly.orchestration.tasks` already makes concurrent runs *safe* — a second
# run finds every occurrence claimed and sends nothing. This exists so the logs
# stay readable when EventBridge delivers a tick twice, and so a slow run cannot
# have a dozen threadpool workers stacked behind it.
#
# A plain Lock, not an RLock: it is acquired on the event loop thread (without
# blocking) and released on the threadpool thread that ran the work, which only
# an unowned lock permits.
_run_lock = threading.Lock()


def require_trigger(
    x_wishly_trigger: Annotated[str | None, Header()] = None,
) -> None:
    """Reject anything that does not present the configured trigger token.

    Constant-time comparison: the token is a fixed secret checked on every tick,
    so an early-exit ``==`` would leak it a byte at a time to anyone who can time
    the endpoint.

    Compared as **bytes**. Starlette decodes header values as latin-1, so a
    request carrying a high byte produces a non-ASCII ``str``, and
    ``compare_digest`` raises ``TypeError`` on those — a 500 and a traceback
    where a 403 belongs.

    An unset ``TRIGGER_TOKEN`` rejects everything rather than allowing
    everything. In production ``Settings`` refuses to start without one; in
    development this is what stops a half-configured API from accepting an
    unauthenticated request to send real email.
    """
    expected = settings.trigger_token
    if not expected or not x_wishly_trigger:
        raise _forbidden()
    if not hmac.compare_digest(x_wishly_trigger.encode("utf-8"), expected.encode("utf-8")):
        raise _forbidden()


def _forbidden() -> HTTPException:
    # Deliberately uninformative: "missing" and "wrong" are the same answer to
    # anyone who is not supposed to be here.
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def host_id() -> str:
    """Which deployment is answering: ``ecs`` or ``vm``.

    ``api.wishly.dev`` is served by whichever cloudflared is connected to the
    tunnel, so a successful probe does not by itself say *where* it landed. After
    a failover the ECS task answers and the VM is still dead; without this the
    detector would read that as recovery.

    Derived, not configured: ECS injects ``ECS_CONTAINER_METADATA_URI_V4`` into
    every task container, so neither ``infra/compose.yaml`` nor the task
    definition needs a new environment variable that could drift out of sync with
    where the process is actually running.
    """
    return "ecs" if os.environ.get("ECS_CONTAINER_METADATA_URI_V4") else "vm"


class LivenessOut(BaseModel):
    """Answer to the detector's probe."""

    status: str
    host: str
    environment: str


class RunAccepted(BaseModel):
    """Acknowledgement that a send run was started (or deliberately was not)."""

    run_id: str
    status: str


class PreviewIn(BaseModel):
    """Parameters for an on-demand preview — the old Prefect deployment's form."""

    user_email: str | None = None
    event_id: str | None = None
    days_before: int = Field(default=DEFAULT_DAYS_BEFORE, ge=0, le=365)
    to: str | None = None
    send: bool = False


@router.get(
    "/liveness",
    response_model=LivenessOut,
    dependencies=[Depends(require_trigger)],
)
async def liveness() -> LivenessOut:
    """Is this process serving, and which deployment is it?

    **Deliberately does not touch the database.** ``/ready`` exists for that. The
    detector scales ECS up when this stops answering, and if PlanetScale were
    down both the VM and ECS would fail an equivalent check — turning a database
    outage into a pointless Fargate launch that cannot fix it either.

    Token-guarded like the rest of ``/internal``, rather than open like
    ``/health``: ``host`` says which deployment is live, which is not something
    the public internet needs to know. Rejecting with 403 does not blind the
    watchdog — the detector treats a 403 as *unknown* and leaves its counter
    alone, precisely so a token problem can never be mistaken for an outage.
    """
    return LivenessOut(status="ok", host=host_id(), environment=settings.environment)


def _run_and_release(run_id: str) -> None:
    """Background body: run the send, always release the lock, never raise.

    Raising here would only reach Starlette's background-task handler long after
    the 202 went out, so the traceback has to be logged where someone will see it
    next to the run id.
    """
    try:
        tally = send_reminders()
        logger.info("run %s finished: %s", run_id, tally)
    except Exception:
        logger.exception("run %s crashed", run_id)
    finally:
        _run_lock.release()


@router.post(
    "/runs/send-reminders",
    response_model=RunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trigger)],
)
async def trigger_send(background: BackgroundTasks) -> RunAccepted:
    """Start the hourly send and return immediately.

    Always 202, including when a run is already in flight — a duplicate tick is
    a normal thing for an at-least-once scheduler to do, not an error, and
    answering 5xx would make EventBridge retry it 185 times.
    """
    run_id = uuid.uuid4().hex[:12]

    # Non-blocking: this runs on the event loop thread and must not park it.
    if not _run_lock.acquire(blocking=False):
        logger.info("run %s not started: a send is already in flight", run_id)
        return RunAccepted(run_id=run_id, status="already_running")

    logger.info("run %s accepted", run_id)
    # `_run_and_release` is sync, so Starlette runs it in the threadpool rather
    # than on the event loop — which is what the sync psycopg session and the
    # blocking Resend client need.
    background.add_task(_run_and_release, run_id)
    return RunAccepted(run_id=run_id, status="accepted")


@router.post("/runs/preview", dependencies=[Depends(require_trigger)])
async def trigger_preview(body: PreviewIn) -> dict[str, Any]:
    """Render (and optionally send) one reminder on demand.

    Runs inline rather than in the background: a human is waiting for the
    rendered subject line, and no API-destination timeout applies to a curl.
    """
    try:
        return dict(
            preview_reminder(
                user_email=body.user_email,
                event_id=body.event_id,
                days_before=body.days_before,
                to=body.to,
                send=body.send,
            )
        )
    except PreviewError as exc:
        # The message names the ambiguity (no users, several users, no events),
        # which is the entire diagnostic for whoever triggered this.
        raise unprocessable(str(exc)) from exc


__all__ = ["TRIGGER_HEADER", "host_id", "require_trigger", "router"]
