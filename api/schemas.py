"""Pydantic schemas for auth, CRUD routes, chart payloads, and billing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi_users import schemas as fastapi_users_schemas
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRead(fastapi_users_schemas.BaseUser[uuid.UUID]):
    tier: str = "free"
    created_at: datetime
    subscription_end: Optional[datetime] = None


class UserCreate(fastapi_users_schemas.BaseUserCreate):
    pass


class UserUpdate(fastapi_users_schemas.BaseUserUpdate):
    pass


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbol: Optional[str] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    symbol: str
    timeframe: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    strategy_count: int = 0
    last_run_sharpe: Optional[float] = None
    last_run_date: Optional[datetime] = None


class StrategyCreate(BaseModel):
    name: str
    type: str = "config"
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("config_json", mode="before")
    @classmethod
    def parse_config_json(cls, value: Any) -> dict[str, Any]:
        if value in (None, "", {}):
            return {}
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    config_json: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator("config_json", mode="before")
    @classmethod
    def parse_optional_config_json(cls, value: Any) -> Optional[dict[str, Any]]:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)


class StrategyOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    type: str
    config_json: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RunTriggerRequest(BaseModel):
    window_override: Optional[dict[str, Any]] = None
    symbol_override: Optional[str] = None

    @field_validator("symbol_override")
    @classmethod
    def normalize_symbol_override(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_id: uuid.UUID
    run_number: Optional[int]
    result_path: Optional[str]
    status: str
    error_msg: Optional[str]
    train_sharpe: Optional[float]
    val_sharpe: Optional[float]
    train_return: Optional[float]
    val_return: Optional[float]
    train_drawdown: Optional[float]
    val_drawdown: Optional[float]
    train_trades: Optional[int]
    val_trades: Optional[int]
    config_hash: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class TradeOut(BaseModel):
    trade_idx: int
    side: str
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    sl_price: Optional[float]
    tp_price: Optional[float]
    size: Optional[float]
    pnl: float
    pnl_pct: Optional[float]
    r_multiple: Optional[float]
    bars_held: Optional[float]
    session: Optional[str]
    exit_reason: str


class TradesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    trades: list[TradeOut]


class OhlcvPoint(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class EquityPoint(BaseModel):
    time: int
    value: float


class ChartTrade(BaseModel):
    trade_idx: int
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    sl_price: Optional[float]
    tp_price: Optional[float]
    side: str
    exit_reason: str
    pnl: float
    r_multiple: Optional[float]
    bars_held: Optional[float]
    session: Optional[str]


class ChartDataResponse(BaseModel):
    ohlcv: list[OhlcvPoint]
    trades: list[ChartTrade]
    equity: list[EquityPoint]
    symbol: str
    timeframe: str
    window: str


class MetricsOut(BaseModel):
    train: dict[str, Any]
    validation: dict[str, Any]


class IndicatorMeta(BaseModel):
    name: str
    display_name: str
    category: str
    description: str
    params: list[dict[str, Any]]


class PatternMeta(BaseModel):
    name: str
    display_name: str
    category: str
    description: str
    params: list[dict[str, Any]]


class CheckoutRequest(BaseModel):
    tier: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class BillingStatus(BaseModel):
    tier: str
    subscription_end: Optional[datetime]
    renewal_date: Optional[datetime]
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
