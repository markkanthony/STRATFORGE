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
        existing = {
            row[1]
            for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in columns.items():
            if column_name in existing:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )


async def create_tables() -> None:
    async with engine.begin() as conn:
        from api import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_sqlite_dev_schema)
