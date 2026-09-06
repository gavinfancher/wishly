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

import os
import ssl
from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from functools import lru_cache

import certifi
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from wishly.core.settings import settings

# Point OpenSSL at a CA bundle before any connection is made.
#
# The DSN carries PlanetScale's `sslmode=verify-full&sslrootcert=system`, and
# `system` means "OpenSSL's default trust store". psycopg[binary] ships its own
# OpenSSL whose compiled-in store is neither Debian's nor macOS's, so that store
# is empty everywhere and every connection fails `certificate verify failed`.
# asyncpg is unaffected — it verifies through Python's ssl module — which is why
# the API worked while the worker did not.
#
# certifi rather than a platform path: /etc/ssl/certs/ca-certificates.crt is
# Debian-only and /etc/ssl/cert.pem is macOS-only, so either one hardcodes a
# guess about where this is running. This is one line that holds for the
# container, a laptop, and a Lambda.
#
# setdefault, so a deployment that needs a private CA can still say so.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())


def _asyncpg_ssl() -> dict[str, object]:
    """TLS for asyncpg, as an SSLContext rather than a URL parameter.

    asyncpg cannot be told about TLS the way libpq is: it takes no
    ``sslrootcert``, and a bare verify mode sends it looking for
    ``~/.postgresql/root.crt``. Handing it a context built from certifi is the
    only spelling that works, and it keeps the trust store identical to the one
    psycopg uses via SSL_CERT_FILE above.
    """
    mode = settings.database_sslmode
    if mode in (None, "disable", "allow", "prefer"):
        # A local Postgres with no TLS. Forcing a context here would break it.
        return {}
    context = ssl.create_default_context(cafile=certifi.where())
    if mode == "require":
        # libpq's `require` encrypts without verifying. Match it exactly rather
        # than silently strengthening what the DSN asked for.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return the process-wide async engine (asyncpg) for the API."""
    return create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
        echo=False,
        connect_args=_asyncpg_ssl(),
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


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sync session inside a transaction, for the send pipeline and scripts.

    Commits on success, rolls back on exception, always closes.

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
