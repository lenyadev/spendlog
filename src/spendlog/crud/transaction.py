from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import Transaction
from spendlog.schemas.transaction import (
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)


def build_conditions(
    user_id: int, filters: TransactionFilters
) -> list[ColumnElement[bool]]:
    conditions = [Transaction.user_id == user_id]
    if filters.type is not None:
        conditions.append(Transaction.type == filters.type)
    if filters.category_id is not None:
        conditions.append(Transaction.category_id == filters.category_id)
    if filters.date_from is not None:
        conditions.append(Transaction.date >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(Transaction.date <= filters.date_to)
    return conditions


async def get(
    session: AsyncSession, user_id: int, transaction_id: int
) -> Transaction | None:
    stmt = select(Transaction).where(
        Transaction.user_id == user_id, Transaction.id == transaction_id
    )
    return await session.scalar(stmt)


async def list_for_user(
    session: AsyncSession,
    user_id: int,
    filters: TransactionFilters,
    limit: int,
    offset: int,
) -> list[Transaction]:
    conditions = build_conditions(user_id, filters)
    stmt = (
        select(Transaction)
        .where(*conditions)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def count_for_user(
    session: AsyncSession, user_id: int, filters: TransactionFilters
) -> int:
    conditions = build_conditions(user_id, filters)
    stmt = select(func.count()).select_from(Transaction).where(*conditions)
    result = await session.scalar(stmt)
    return result or 0


async def create(
    session: AsyncSession, user_id: int, data: TransactionCreate
) -> Transaction:
    transaction = Transaction(user_id=user_id, **data.model_dump())
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def update(
    session: AsyncSession, transaction: Transaction, data: TransactionUpdate
) -> Transaction:
    for key, value in data.model_dump().items():
        setattr(transaction, key, value)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def delete(session: AsyncSession, transaction: Transaction) -> None:
    await session.delete(transaction)
    await session.commit()
