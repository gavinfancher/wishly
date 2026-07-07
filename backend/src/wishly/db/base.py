"""SQLAlchemy declarative base and shared metadata.

All ORM models inherit from :class:`Base`. A deterministic naming convention for
constraints/indexes is configured so that Alembic autogenerate produces stable,
predictable migration names (and downgrades can drop them by name).
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Stable names for constraints/indexes -> reproducible Alembic migrations.
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
