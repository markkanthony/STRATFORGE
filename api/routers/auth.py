"""Authentication routes using FastAPI Users."""

from fastapi import APIRouter, Depends

from api.auth import auth_backend, current_active_user, fastapi_users
from api.models import User
from api.schemas import UserCreate, UserRead


router = APIRouter()

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)


@router.get("/auth/me", response_model=UserRead, tags=["auth"])
async def read_current_user(user: User = Depends(current_active_user)) -> User:
    return user
