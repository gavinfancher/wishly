"""SQLAlchemy declarative base and shared metadata.

All ORM models inherit from :class:`Base`. The naming convention gives every
constraint and index a deterministic name, so the names SQLAlchemy expects match
the ones written by hand in ``infra/sql/schema.sql``.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Stable names for constraints/indexes -> they match infra/sql/schema.sql.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all Wishly ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
