from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.crud import category as category_crud
from spendlog.dependencies import CurrentUserDep, SessionDep
from spendlog.models import Category
from spendlog.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


async def get_or_404(session: AsyncSession, user_id: int, category_id: int) -> Category:
    category = await category_crud.get(
        session=session, user_id=user_id, category_id=category_id
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )
    return category


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: int, session: SessionDep, user: CurrentUserDep
) -> Category:
    return await get_or_404(session, user.id, category_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CategoryRead)
async def create_category(
    data: CategoryCreate, session: SessionDep, user: CurrentUserDep
) -> Category:
    try:
        return await category_crud.create(
            session=session, user_id=user.id, name=data.name
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Category already exists"
        ) from None


@router.get("", response_model=list[CategoryRead])
async def get_all_categories(
    session: SessionDep, user: CurrentUserDep
) -> list[Category]:
    return await category_crud.list_for_user(session=session, user_id=user.id)


@router.put("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: int, data: CategoryUpdate, session: SessionDep, user: CurrentUserDep
) -> Category:
    category = await get_or_404(session, user.id, category_id)
    try:
        return await category_crud.update(
            session=session, category=category, name=data.name
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Category already exists"
        ) from None


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    session: SessionDep,
    user: CurrentUserDep,
) -> None:
    category = await get_or_404(session, user.id, category_id)
    try:
        await category_crud.delete(session=session, category=category)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Category has transactions and cannot be deleted",
        ) from None
