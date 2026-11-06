from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.crud import category as category_crud
from spendlog.crud import transaction as transaction_crud
from spendlog.dependencies import CurrentUserDep, SessionDep
from spendlog.models import Transaction
from spendlog.schemas.transaction import (
    TransactionCreate,
    TransactionFilters,
    TransactionPage,
    TransactionRead,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def get_or_404(
    session: AsyncSession, user_id: int, transaction_id: int
) -> Transaction:
    transaction = await transaction_crud.get(
        session=session, user_id=user_id, transaction_id=transaction_id
    )
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )
    return transaction


async def ensure_category(
    session: AsyncSession, user_id: int, category_id: int
) -> None:
    if await category_crud.get(session, user_id, category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")


@router.get("", response_model=TransactionPage)
async def get_transaction_page(
    filters: Annotated[TransactionFilters, Query()],
    session: SessionDep,
    user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TransactionPage:
    transactions = await transaction_crud.list_for_user(
        session, user.id, filters, limit, offset
    )
    total = await transaction_crud.count_for_user(session, user.id, filters)
    return TransactionPage(
        items=[TransactionRead.model_validate(t) for t in transactions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int, session: SessionDep, user: CurrentUserDep
):
    return await get_or_404(session, user.id, transaction_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TransactionRead)
async def create_transaction(
    data: TransactionCreate, session: SessionDep, user: CurrentUserDep
) -> Transaction:
    await ensure_category(session, user.id, data.category_id)
    return await transaction_crud.create(session, user.id, data)


@router.put("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    session: SessionDep,
    user: CurrentUserDep,
) -> Transaction:
    transaction = await get_or_404(session, user.id, transaction_id)
    await ensure_category(session, user.id, data.category_id)
    return await transaction_crud.update(session, transaction, data)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int, session: SessionDep, user: CurrentUserDep
) -> None:
    transaction = await get_or_404(session, user.id, transaction_id)
    await transaction_crud.delete(session, transaction)
