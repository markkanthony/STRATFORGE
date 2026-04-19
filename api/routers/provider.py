"""Provider metadata routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import current_active_user
from api.models import User
from core.data_feed import list_available_symbols


router = APIRouter(prefix="/api/provider", tags=["provider"])


@router.get("/symbols", response_model=list[str])
async def list_symbols(_: User = Depends(current_active_user)) -> list[str]:
    return list_available_symbols()
