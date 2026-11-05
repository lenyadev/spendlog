from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import Transaction
from spendlog.schemas.transaction import TransactionCreate, TransactionUpdate


async def get(
    session: AsyncSession, user_id: int, transaction_id: int
) -> Transaction | None:
    stmt = select(Transaction).where(
        Transaction.user_id == user_id, Transaction.id == transaction_id
    )
    return await session.scalar(stmt)


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
