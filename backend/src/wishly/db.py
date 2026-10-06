"""Database connections.

Opening a Postgres connection costs a TCP + TLS handshake and authentication —
tens of milliseconds to PlanetScale. A pool opens a few once and lends them out.
"""

from collections.abc import Iterator

from fastapi import Request
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from wishly.settings import Settings


def create_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool(
        settings.database_url.get_secret_value(),
        min_size=1,
        max_size=settings.db_pool_size,
        # autocommit: every statement commits on its own. Our writes are all
        # single statements, so there's no transaction state to reason about.
        # dict_row: rows come back as {"column": value} dicts.
        kwargs={"autocommit": True, "row_factory": dict_row},
        # Building the pool doesn't connect; the app's startup opens it.
        open=False,
    )


def get_conn(request: Request) -> Iterator[Connection]:
    """FastAPI dependency: borrow a connection for one request, then return it."""
    with request.app.state.pool.connection() as conn:
        yield conn
