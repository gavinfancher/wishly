from datetime import UTC, datetime, timedelta

import psycopg
from psycopg_pool import ConnectionPool

from tests.conftest import make_settings
from tests.test_run import SEND_TIME, add_mom_reminder
from wishly.db import create_pool
from wishly.scheduler import STALL_AFTER, Scheduler, next_tick


def test_next_tick_is_the_next_quarter_hour() -> None:
    at = lambda h, m, s=0: datetime(2026, 10, 5, h, m, s, tzinfo=UTC)  # noqa: E731

    assert next_tick(at(12, 59, 59)) == at(13, 0)
    assert next_tick(at(13, 0)) == at(13, 15)  # strictly after
    assert next_tick(at(13, 7, 30)) == at(13, 15)
    assert next_tick(at(23, 50)) == datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


def test_tick_sends_whats_due(db: psycopg.Connection) -> None:
    add_mom_reminder(db)
    emails = []
    with create_pool(make_settings()) as pool:
        scheduler = Scheduler(pool, lambda **e: emails.append(e), clock=lambda: SEND_TIME)
        scheduler.tick()

    assert len(emails) == 1
    assert scheduler.last_tick_at == SEND_TIME


def test_a_failing_tick_is_logged_not_raised() -> None:
    # Nothing listens on port 1: every connection fails.
    pool = ConnectionPool("postgresql://nobody@127.0.0.1:1/nothing", open=False, timeout=0.5)
    scheduler = Scheduler(pool, send_email=lambda **e: None, clock=lambda: SEND_TIME)
    pool.open(wait=False)
    try:
        scheduler.tick()
    finally:
        pool.close()

    assert scheduler.last_tick_at is None


def test_stalled_when_ticks_stop_succeeding() -> None:
    pool = ConnectionPool("postgresql://unused", open=False)
    scheduler = Scheduler(pool, send_email=lambda **e: None, clock=lambda: SEND_TIME)
    scheduler.start()
    try:
        assert not scheduler.stalled(SEND_TIME + STALL_AFTER)
        assert scheduler.stalled(SEND_TIME + STALL_AFTER + timedelta(seconds=1))
    finally:
        scheduler.stop()

    assert scheduler.stalled(SEND_TIME)  # thread stopped
