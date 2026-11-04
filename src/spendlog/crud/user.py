from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def create(session: AsyncSession, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
