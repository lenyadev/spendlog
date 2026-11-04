from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import Category


async def list_for_user(session: AsyncSession, user_id: int) -> list[Category]:
    stmt = select(Category).where(Category.user_id == user_id).order_by(Category.name)
    result = await session.scalars(stmt)
    return list(result.all())


async def get(session: AsyncSession, user_id: int, category_id: int) -> Category | None:
    stmt = select(Category).where(
        Category.user_id == user_id, Category.id == category_id
    )
    return await session.scalar(stmt)


async def create(session: AsyncSession, user_id: int, name: str) -> Category:
    category = Category(name=name, user_id=user_id)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update(session: AsyncSession, category: Category, name: str) -> Category:
    category.name = name
    await session.commit()
    await session.refresh(category)
    return category


async def delete(session: AsyncSession, category: Category) -> None:
    await session.delete(category)
    await session.commit()
