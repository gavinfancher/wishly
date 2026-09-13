"""The machine-triggered routes: auth, the 202 contract, and the liveness probe.

These cover the seams the EventBridge rule and the detector Lambda depend on.
The send itself is stubbed — `test_due.py` and `test_preview.py` already exercise
the pipeline; what matters here is that the route authenticates, answers fast,
and refuses to run two sends at once.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from wishly.api.routes import internal
from wishly.core.settings import settings

TOKEN = "trg_" + uuid.uuid4().hex


@pytest.fixture(autouse=True)
def _token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a trigger token for the duration of each test."""
    monkeypatch.setattr(settings, "trigger_token", TOKEN)


@pytest.fixture(autouse=True)
def _lock_released() -> Iterator[None]:
    """Fail loudly rather than leaking a held lock into the next test."""
    yield
    if internal._run_lock.locked():  # pragma: no cover - only on a real bug
        internal._run_lock.release()
        pytest.fail("the run lock was still held after the test")


def headers(token: str | bytes = TOKEN) -> dict[str, Any]:
    return {internal.TRIGGER_HEADER: token}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class TestTriggerAuth:
    """The shared-secret guard on /internal/runs/*."""

    @pytest.mark.parametrize(
        "sent",
        [None, "", "wrong-token", TOKEN + "x", TOKEN[:-1], b"t\xf6k\xe9n-high-bytes"],
        ids=["missing", "empty", "wrong", "too-long", "truncated", "non-ascii"],
    )
    async def test_rejects_anything_but_the_exact_token(
        self, client: AsyncClient, sent: str | bytes | None
    ) -> None:
        # The non-ascii case is passed as raw bytes because httpx refuses to
        # encode a non-ascii header *string* — but a non-ascii header is trivial
        # to put on the wire, and Starlette hands it over latin-1-decoded. On
        # such a str hmac.compare_digest raises TypeError: a 500 and a traceback
        # where a 403 belongs. Hence the .encode() in require_trigger.
        hdrs = {} if sent is None else headers(sent)
        response = await client.post("/internal/runs/send-reminders", headers=hdrs)
        assert response.status_code == 403

    async def test_rejection_is_403_not_401(self, client: AsyncClient) -> None:
        """EventBridge retries 401 up to 185 times; it never retries 403.

        A mistyped token is a configuration error that will not fix itself, so
        the wrong status code here turns one bad apply into a day of traffic.
        """
        response = await client.post("/internal/runs/send-reminders")
        assert response.status_code == 403
        assert "WWW-Authenticate" not in response.headers

    async def test_unset_token_rejects_rather_than_admits(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No configured token must fail closed.

        The failure mode this prevents: a half-configured deployment where the
        secret never arrived, and /internal is open to anyone who can reach the
        tunnel and would like some email sent.
        """
        monkeypatch.setattr(settings, "trigger_token", None)
        response = await client.post("/internal/runs/send-reminders", headers=headers())
        assert response.status_code == 403

    async def test_preview_is_guarded_too(self, client: AsyncClient) -> None:
        response = await client.post("/internal/runs/preview", json={})
        assert response.status_code == 403


# --------------------------------------------------------------------------- #
# The hourly trigger
# --------------------------------------------------------------------------- #
class TestTriggerSend:
    async def test_accepts_and_runs_the_send(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[int] = []
        monkeypatch.setattr(
            internal,
            "send_reminders",
            lambda: (calls.append(1), {"sent": 1, "skipped": 0, "duplicate": 0, "failed": 0})[1],
        )

        response = await client.post("/internal/runs/send-reminders", headers=headers())

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["run_id"]
        # Starlette runs background tasks before the ASGI response completes, so
        # by the time the client returns the send has already happened.
        assert calls == [1]

    async def test_a_crashing_run_still_released_the_lock(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A background exception must not wedge every subsequent tick.

        Nothing is watching a background task's return value, so an unreleased
        lock here would silently stop reminders until the container restarted.
        """

        def boom() -> dict[str, int]:
            raise RuntimeError("resend exploded")

        monkeypatch.setattr(internal, "send_reminders", boom)

        response = await client.post("/internal/runs/send-reminders", headers=headers())

        assert response.status_code == 202
        assert not internal._run_lock.locked()

    async def test_concurrent_tick_is_202_not_an_error(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A duplicate delivery is normal for an at-least-once scheduler.

        Answering 5xx would make EventBridge retry it for 24 hours.
        """
        calls: list[int] = []
        monkeypatch.setattr(internal, "send_reminders", lambda: calls.append(1))

        internal._run_lock.acquire()
        try:
            response = await client.post("/internal/runs/send-reminders", headers=headers())
        finally:
            internal._run_lock.release()

        assert response.status_code == 202
        assert response.json()["status"] == "already_running"
        assert calls == []  # the second tick did not start a second send


# --------------------------------------------------------------------------- #
# Liveness (the detector Lambda's probe)
# --------------------------------------------------------------------------- #
class TestLiveness:
    async def test_names_the_host(self, client: AsyncClient) -> None:
        response = await client.get("/internal/liveness", headers=headers())
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "host": "vm", "environment": "dev"}

    async def test_is_token_guarded(self, client: AsyncClient) -> None:
        """403 rather than open: `host` says which deployment is live.

        The detector reads a 403 as *unknown* and leaves its counter alone, so
        guarding this cannot cause a spurious failover.
        """
        assert (await client.get("/internal/liveness")).status_code == 403

    async def test_reports_ecs_inside_a_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The detector distinguishes 'the VM recovered' from 'ECS answered'.

        Both serve the same tunnel hostname, so without this a failover would
        look like a recovery one minute later.
        """
        monkeypatch.setenv("ECS_CONTAINER_METADATA_URI_V4", "http://169.254.170.2/v4/abc")
        assert internal.host_id() == "ecs"
        monkeypatch.delenv("ECS_CONTAINER_METADATA_URI_V4")
        assert internal.host_id() == "vm"

    async def test_does_not_touch_the_database(
        self, app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PlanetScale outage must not read as 'this host is down'.

        Failing over to ECS cannot fix a database both deployments share, so a
        DB check here would spend money to change nothing.
        """

        def explode(*_: Any, **__: Any) -> None:
            raise AssertionError("liveness must not open a database connection")

        monkeypatch.setattr("wishly.db.session.get_async_engine", explode)
        monkeypatch.setattr("wishly.db.session.get_sync_engine", explode)

        assert (await client.get("/internal/liveness", headers=headers())).status_code == 200
