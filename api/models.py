"""SQLAlchemy ORM models for auth, projects, strategies, and runs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy import GUID
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subscription_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    projects: Mapped[list["Project"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), default="EURUSD", nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), default="H1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="projects")
    strategies: Mapped[list["Strategy"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(Strategy.updated_at)",
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="config", nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="strategies")
    runs: Mapped[list["Run"]] = relationship(
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="desc(Run.created_at)",
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    run_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    train_sharpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    val_sharpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    train_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    val_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    train_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    val_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    train_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    val_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    config_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    strategy: Mapped[Strategy] = relationship(back_populates="runs")
