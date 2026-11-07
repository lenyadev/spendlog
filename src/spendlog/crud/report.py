from datetime import timedelta

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import Category, Transaction
from spendlog.schemas.report import ReportFilters


async def totals_by_category(
    session: AsyncSession, user_id: int, filters: ReportFilters
) -> list[Row]:
    total_col = func.sum(Transaction.amount).label("total")
    conditions = [Transaction.user_id == user_id]
    if filters.type is not None:
        conditions.append(Transaction.type == filters.type)
    if filters.date_from is not None:
        conditions.append(Transaction.date >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(Transaction.date < filters.date_to + timedelta(days=1))

    stmt = (
        select(Category.id, Category.name, total_col)
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(*conditions)
        .group_by(Category.id, Category.name)
        .order_by(total_col.desc(), Category.name)
    )
    result = await session.execute(stmt)
    return list(result.all())
