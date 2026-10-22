"""The daily send, run inside the API process. No external scheduler.

A background thread wakes at every quarter hour (:00, :15, :30, :45 UTC, which
are also quarter hours Eastern) and sends whatever is due. Reminders become due
at 9:00 Eastern (see schedule.py), so the 9:00 tick sends them; later ticks the
same day retry failed sends and catch up after a restart. The `sends` table
makes those repeats harmless, even if two pods overlap during a rollout.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from psycopg_pool import ConnectionPool

from wishly.run import send_due_reminders

log = logging.getLogger(__name__)

TICK = timedelta(minutes=15)


def next_tick(now: datetime) -> datetime:
    """The next quarter hour strictly after `now`."""
    floored = now.replace(minute=now.minute - now.minute % 15, second=0, microsecond=0)
    return floored + TICK


def utcnow() -> datetime:
    return datetime.now(UTC)


class Scheduler:
    def __init__(
        self,
        pool: ConnectionPool,
        send_email: Callable,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.pool = pool
        self.send_email = send_email
        self.clock = clock
        # The last tick that finished without an error. None until the first.
        self.last_tick_at: datetime | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="scheduler", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _loop(self) -> None:
        while True:
            now = self.clock()
            # wait() returns True when stop() is called: shut down promptly
            # instead of sleeping out the rest of the quarter hour.
            if self._stop.wait((next_tick(now) - now).total_seconds()):
                return
            self.tick()

    def tick(self) -> None:
        now = self.clock()
        try:
            with self.pool.connection() as conn:
                result = send_due_reminders(conn, self.send_email, now=now)
        except Exception:
            # Database down, most likely. Log it and try again next tick; the
            # thread must survive anything a single run throws.
            log.exception("scheduled send failed")
            return
        self.last_tick_at = now
        log.info("scheduled send: %s", result)
