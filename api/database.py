"""Async SQLAlchemy engine, session factory, and FastAPI Users adapter."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.config import settings


engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base."""


SQLITE_DEV_MIGRATIONS: dict[str, dict[str, str]] = {
    "users": {
        "subscription_status": "VARCHAR(50)",
    },
}

_ALLOWED_MIGRATION_TABLES = frozenset(SQLITE_DEV_MIGRATIONS.keys())
_ALLOWED_COLUMN_TYPES = frozenset({"VARCHAR(50)", "VARCHAR(255)", "INTEGER", "TEXT", "BOOLEAN", "FLOAT"})
import re as _re
_SAFE_IDENTIFIER = _re.compile(r'^[a-z][a-z0-9_]*$')


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    from api.models import User

    yield SQLAlchemyUserDatabase(session, User)


def _sync_sqlite_dev_schema(conn: Any) -> None:
    if conn.dialect.name != "sqlite":
        return

    for table_name, columns in SQLITE_DEV_MIGRATIONS.items():
        if table_name not in _ALLOWED_MIGRATION_TABLES or not _SAFE_IDENTIFIER.match(table_name):
            raise ValueError(f"Disallowed table name in dev migration: {table_name!r}")
        existing = {
            row[1]
            for row in conn.exec_driver_sql("SELECT * FROM pragma_table_info(?)", [table_name]).fetchall()
        }
        for column_name, column_type in columns.items():
            if not _SAFE_IDENTIFIER.match(column_name):
                raise ValueError(f"Disallowed column name in dev migration: {column_name!r}")
            if column_type not in _ALLOWED_COLUMN_TYPES:
                raise ValueError(f"Disallowed column type in dev migration: {column_type!r}")
            if column_name in existing:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"  # nosec: validated above
            )


async def create_tables() -> None:
    async with engine.begin() as conn:
        from api import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_dev_schema)
