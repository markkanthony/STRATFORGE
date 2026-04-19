"""Create or refresh a local development user for StratForge."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.auth import UserManager
from api.database import async_session_maker, create_tables
from api.models import User
from api.schemas import UserCreate


DEFAULT_EMAIL = "demo@example.com"
DEFAULT_PASSWORD = "StratForge123!"
DEFAULT_TIER = "elite"


async def seed_user(email: str, password: str, tier: str) -> User:
    await create_tables()

    async with async_session_maker() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        user = await session.scalar(select(User).where(User.email == email))

        if user is None:
            user = await manager.create(
                UserCreate(email=email, password=password),
                safe=False,
            )
        else:
            user.hashed_password = manager.password_helper.hash(password)

        user.is_active = True
        user.is_verified = True
        user.tier = tier

        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a local StratForge development user.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"Login email. Default: {DEFAULT_EMAIL}")
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"Login password. Default: {DEFAULT_PASSWORD}",
    )
    parser.add_argument("--tier", default=DEFAULT_TIER, help=f"Subscription tier. Default: {DEFAULT_TIER}")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    user = await seed_user(args.email, args.password, args.tier)

    print("=" * 60)
    print("StratForge development user ready")
    print(f"Email: {user.email}")
    print(f"Password: {args.password}")
    print(f"Tier: {user.tier}")
    print("Login: http://localhost:5173/login")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
