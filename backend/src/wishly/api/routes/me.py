"""Current-user routes: ``GET /me`` (provision-on-first-request) and ``PATCH /me``."""

from __future__ import annotations

from fastapi import APIRouter

from wishly.api import crud
from wishly.api.deps import CurrentUser, DBSession
from wishly.api.errors import not_found
from wishly.api.schemas import UserOut, UserUpdate

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def get_me(principal: CurrentUser, session: DBSession) -> UserOut:
    """Return the current user, creating the row on first authenticated request.

    The Clerk session token is the source of identity (PLAN §10). If this
    ``sub`` has never been seen we insert a ``users`` row from the JWT claims —
    a fallback for a missed/raced Clerk webhook (PLAN §2).
    """
    user = await crud.provision_user(session, principal)
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, principal: CurrentUser, session: DBSession) -> UserOut:
    """Update onboarding preferences (``timezone`` and/or ``send_hour``)."""
    # Ensure the row exists even if ``PATCH /me`` is somehow the first call.
    user = await crud.provision_user(session, principal)
    if user is None:  # pragma: no cover — provision_user always returns a row
        raise not_found("User not found.")

    if body.timezone is not None:
        user.timezone = body.timezone
    if body.send_hour is not None:
        user.send_hour = body.send_hour

    await session.flush()
    # Refresh so server-side ``onupdate`` columns (``updated_at``) are loaded before
    # Pydantic reads attributes — otherwise async SQLAlchemy raises MissingGreenlet.
    await session.refresh(user)
    return UserOut.model_validate(user)
