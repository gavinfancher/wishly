"""Small helpers for raising consistent HTTP errors across the API."""

from __future__ import annotations

from fastapi import HTTPException, status


def unauthorized(detail: str = "Not authenticated.") -> HTTPException:
    """A 401 with the ``WWW-Authenticate: Bearer`` header browsers expect."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def not_found(detail: str = "Not found.") -> HTTPException:
    """A 404. Used for cross-user access so resources are indistinguishable."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str = "Bad request.") -> HTTPException:
    """A 400 (e.g. webhook signature verification failure)."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def conflict(detail: str = "Conflict.") -> HTTPException:
    """A 409 (e.g. duplicate ``days_before`` within an event)."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def unprocessable(detail: str = "Unprocessable entity.") -> HTTPException:
    """A 422 for semantically invalid input (matches Pydantic's body errors)."""
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
