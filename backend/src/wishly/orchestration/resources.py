"""Dagster resources for the send pipeline (T5.1).

Two resources are exposed to ops:

* :class:`DatabaseResource` — hands out **sync** SQLAlchemy sessions (psycopg)
  from :func:`wishly.db.session.get_sync_sessionmaker`. Dagster runs the send
  job synchronously, so it uses the sync engine rather than the API's async one.
* :class:`ResendResource` — constructs a :class:`wishly.email.resend_client.ResendClient`.

Both are :class:`dagster.ConfigurableResource` subclasses so they can be wired
into :class:`dagster.Definitions` and overridden in tests with fakes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from dagster import ConfigurableResource
from sqlalchemy.orm import Session

from wishly.db.session import get_sync_sessionmaker
from wishly.email.resend_client import ResendClient

# ``ConfigurableResource`` is declared generic in Dagster's typed source, so under
# strict mypy a bare subclass trips ``type-arg``. It takes no real type parameter
# at runtime, so parameterising with ``None`` satisfies the checker harmlessly.
_BaseResource = ConfigurableResource[None]


class DatabaseResource(_BaseResource):
    """Provides transactional sync DB sessions to ops.

    Usage in an op::

        with database.session() as session:
            ...
    """

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a sync session; commit on success, roll back on error, close."""
        factory = get_sync_sessionmaker()
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class ResendResource(_BaseResource):
    """Provides a configured :class:`ResendClient` to ops.

    Reads ``RESEND_API_KEY`` / ``EMAIL_FROM`` from settings via the client's own
    defaults; nothing secret lives on the resource config.
    """

    def get_client(self) -> ResendClient:
        """Return a fresh :class:`ResendClient`."""
        return ResendClient()


__all__ = ["DatabaseResource", "ResendResource"]
