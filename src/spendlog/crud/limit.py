from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import MonthlyLimit


async def get_by_month(
    session: AsyncSession, user_id: int, month: date
) -> MonthlyLimit | None:
    stmt = select(MonthlyLimit).where(
        MonthlyLimit.user_id == user_id, MonthlyLimit.month == month
    )
    return await session.scalar(stmt)


async def create(
    session: AsyncSession, user_id: int, month: date, amount: Decimal
) -> MonthlyLimit:
    limit = MonthlyLimit(user_id=user_id, month=month, amount=amount)
    session.add(limit)
    await session.commit()
    await session.refresh(limit)
    return limit


async def update(
    session: AsyncSession, monthly_limit: MonthlyLimit, amount: Decimal
) -> MonthlyLimit:
    monthly_limit.amount = amount
    await session.commit()
    await session.refresh(monthly_limit)
    return monthly_limit
