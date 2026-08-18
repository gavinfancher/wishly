"""Transactional sync sessions for the send pipeline.

The API runs on the async engine; the send pipeline runs synchronously, so it
uses the sync (psycopg) sessionmaker instead. Commits on success, rolls back on
error, always closes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from wishly.db.session import get_sync_sessionmaker


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a sync session inside a transaction.

    Usage::

        with session_scope() as session:
            ...
    """
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


__all__ = ["session_scope"]
