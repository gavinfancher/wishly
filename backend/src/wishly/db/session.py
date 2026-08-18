"""Engine and session factories.

Two runtimes share one database:

* **FastAPI** uses an *async* engine (``asyncpg``) and yields an
  :class:`~sqlalchemy.ext.asyncio.AsyncSession` per request via :func:`get_session`.
* **The worker** uses a *sync* engine (``psycopg`` v3) and a plain
  :class:`~sqlalchemy.orm.Session`.

Engines are created lazily and cached so that merely importing this module does
not require a configured ``DATABASE_URL`` (keeps imports cheap and test-friendly).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from wishly.core.settings import settings


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return the process-wide async engine (asyncpg) for the API."""
    return create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the async sessionmaker bound to :func:`get_async_engine`."""
    return async_sessionmaker(
        bind=get_async_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


@lru_cache(maxsize=1)
def get_sync_engine() -> Engine:
    """Return the process-wide sync engine (psycopg) for the worker/CLIs."""
    return create_engine(
        settings.sync_database_url,
        pool_pre_ping=True,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_sync_sessionmaker() -> sessionmaker[Session]:
    """Return the sync sessionmaker bound to :func:`get_sync_engine`."""
    return sessionmaker(
        bind=get_sync_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields a request-scoped :class:`AsyncSession`.

    Commits on success, rolls back on exception, and always closes the session.

    Usage::

        @router.get("/me")
        async def me(session: Annotated[AsyncSession, Depends(get_session)]) -> ...:
            ...
    """
    factory = get_async_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def sync_session() -> Generator[Session]:
    """Context-managed sync session for worker tasks and scripts.

    Commits on success, rolls back on exception, always closes.

    Usage::

        with contextlib.closing(...):
            ...

    or as a generator-backed contextmanager::

        from contextlib import contextmanager
        with contextmanager(sync_session)() as session:
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
