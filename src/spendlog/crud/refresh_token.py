from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.models import RefreshToken


async def create(
    session: AsyncSession,
    user_id: int,
    expires_at: datetime,
    family_id: UUID,
    token_hash: str,
) -> RefreshToken:
    refresh_token = RefreshToken(
        user_id=user_id,
        expires_at=expires_at,
        family_id=family_id,
        token_hash=token_hash,
    )
    session.add(refresh_token)
    await session.flush()
    return refresh_token


async def get_by_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    return await session.scalar(stmt)


async def revoke(session: AsyncSession, refresh_token: RefreshToken) -> None:
    refresh_token.revoked_at = datetime.now(tz=UTC)
    await session.flush()


async def revoke_family(session: AsyncSession, family_id: UUID) -> None:
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values({"revoked_at": datetime.now(tz=UTC)})
    )
    await session.execute(stmt)
