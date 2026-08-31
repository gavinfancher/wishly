"""Tests for the ``/events`` routes.

These exist because they did not. ``PATCH /events/{id}`` returned a 500 on every
call in production — Pydantic read the server-managed ``updated_at`` off an
expired attribute, which async SQLAlchemy cannot lazy-load, so the request died
with ``MissingGreenlet``. The identical bug on ``PATCH /me`` was fixed long ago,
because ``PATCH /me`` had a test and this did not.

The round-trip assertions below are the point: every mutation reads its own
response body, which is what forces the ORM object through serialisation and
catches an expired attribute.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient

from tests.api.conftest import auth_headers


def _payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Mom's Bday",
        "event_type": "birthday",
        "event_month": 5,
        "event_day": 28,
        "event_year": 1971,
        "message": "mahjong",
        "is_active": True,
    }
    body.update(overrides)
    return body


async def _create(client: AsyncClient, token: str, **overrides: Any) -> dict[str, Any]:
    resp = await client.post("/events", headers=auth_headers(token), json=_payload(**overrides))
    assert resp.status_code == 201, resp.text
    created: dict[str, Any] = resp.json()
    return created


# --- POST /events ----------------------------------------------------------- #
async def test_create_event_returns_the_serialised_event(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token(sub="user_ev1", email="ev1@example.com")
    body = await _create(client, token)

    assert body["title"] == "Mom's Bday"
    assert (body["event_month"], body["event_day"], body["event_year"]) == (5, 28, 1971)
    # Server-managed columns must come back populated, not expired.
    assert body["created_at"]
    assert body["updated_at"]


# --- PATCH /events/{id} ----------------------------------------------------- #
async def test_update_event_does_not_500_on_serialisation(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    """Regression: this returned 500 MissingGreenlet for every successful edit.

    `updated_at` has a server-side onupdate, so the flush expires it. Refreshing
    only `reminders` left it expired, and serialising the response then tried to
    lazy-load it outside a greenlet.
    """
    token = make_token(sub="user_ev2", email="ev2@example.com")
    created = await _create(client, token)

    resp = await client.patch(
        f"/events/{created['id']}",
        headers=auth_headers(token),
        json={"title": "Mum's Birthday", "message": "mahjong + cake"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Mum's Birthday"
    assert body["message"] == "mahjong + cake"
    assert body["updated_at"]


async def test_update_event_accepts_a_partial_body(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token(sub="user_ev3", email="ev3@example.com")
    created = await _create(client, token)

    resp = await client.patch(
        f"/events/{created['id']}", headers=auth_headers(token), json={"is_active": False}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_active"] is False
    # Untouched fields survive.
    assert body["title"] == "Mom's Bday"
    assert body["event_year"] == 1971


async def test_update_event_rejects_an_impossible_calendar_day(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    """A partial update must be validated against the *resulting* date."""
    token = make_token(sub="user_ev4", email="ev4@example.com")
    created = await _create(client, token, event_month=1, event_day=31)

    # January 31 -> February keeps day 31, which is not a real date.
    resp = await client.patch(
        f"/events/{created['id']}", headers=auth_headers(token), json={"event_month": 2}
    )
    assert resp.status_code == 422, resp.text


async def test_feb_29_is_allowed(client: AsyncClient, make_token: Callable[..., str]) -> None:
    """Feb 29 is a real occasion; the sender observes it on Feb 28 in non-leap years."""
    token = make_token(sub="user_ev5", email="ev5@example.com")
    body = await _create(client, token, event_month=2, event_day=29)
    assert (body["event_month"], body["event_day"]) == (2, 29)


# --- Ownership -------------------------------------------------------------- #
async def test_another_users_event_is_indistinguishable_from_a_missing_one(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    owner = make_token(sub="user_owner", email="owner@example.com")
    other = make_token(sub="user_other", email="other@example.com")
    created = await _create(client, owner)

    for method, kwargs in (
        ("get", {}),
        ("patch", {"json": {"title": "hijacked"}}),
        ("delete", {}),
    ):
        resp = await getattr(client, method)(
            f"/events/{created['id']}", headers=auth_headers(other), **kwargs
        )
        assert resp.status_code == 404, f"{method}: {resp.text}"


# --- Year bounds, matching the frontend's 0001-9999 ------------------------- #
async def test_year_bounds(client: AsyncClient, make_token: Callable[..., str]) -> None:
    token = make_token(sub="user_ev6", email="ev6@example.com")

    for year in (1, 9999):
        resp = await client.post(
            "/events", headers=auth_headers(token), json=_payload(event_year=year)
        )
        assert resp.status_code == 201, f"{year}: {resp.text}"

    for year in (0, 10000, -1):
        resp = await client.post(
            "/events", headers=auth_headers(token), json=_payload(event_year=year)
        )
        assert resp.status_code == 422, f"{year} should be rejected: {resp.text}"


# --- DELETE ----------------------------------------------------------------- #
async def test_delete_event(client: AsyncClient, make_token: Callable[..., str]) -> None:
    token = make_token(sub="user_ev7", email="ev7@example.com")
    created = await _create(client, token)

    resp = await client.delete(f"/events/{created['id']}", headers=auth_headers(token))
    assert resp.status_code == 204, resp.text

    resp = await client.get(f"/events/{created['id']}", headers=auth_headers(token))
    assert resp.status_code == 404
