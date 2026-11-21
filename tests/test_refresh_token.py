from datetime import UTC, datetime, timedelta
from typing import NamedTuple, Protocol
from uuid import UUID, uuid4

import pytest

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.models import RefreshToken
from spendlog.security import create_refresh_token
from spendlog.settings import get_settings


class CreatedRefreshToken(NamedTuple):
    record: RefreshToken
    raw_token: str


class CreatedUser(NamedTuple):
    id: int
    email: str


class RefreshTokenFactory(Protocol):
    async def __call__(
        self,
        user_id: int | None = None,
        expires_at: datetime | None = None,
        family_id: UUID | None = None,
    ) -> CreatedRefreshToken: ...


@pytest.fixture
async def created_user(client, user_credentials) -> CreatedUser:
    register = await client.post("/auth/register", json=user_credentials)
    assert register.status_code == 201
    register_json = register.json()
    return CreatedUser(id=register_json["id"], email=register_json["email"])


@pytest.fixture
async def make_refresh_token(session, created_user: CreatedUser) -> RefreshTokenFactory:
    async def _make_refresh_token(
        user_id: int | None = None,
        expires_at: datetime | None = None,
        family_id: UUID | None = None,
    ) -> CreatedRefreshToken:
        settings = get_settings()
        raw_token, token_hash = create_refresh_token()
        if expires_at is None:
            expires_at = datetime.now(tz=UTC) + timedelta(
                days=settings.refresh_token_expire_days
            )
        if family_id is None:
            family_id = uuid4()
        if user_id is None:
            user_id = created_user.id

        token_db_record = await refresh_token_crud.create(
            session=session,
            user_id=user_id,
            expires_at=expires_at,
            family_id=family_id,
            token_hash=token_hash,
        )
        return CreatedRefreshToken(record=token_db_record, raw_token=raw_token)

    return _make_refresh_token


async def test_get_by_hash(session, make_refresh_token):
    token = await make_refresh_token()
    refresh_token = await refresh_token_crud.get_by_hash(
        session, token.record.token_hash
    )
    assert refresh_token is not None
    assert refresh_token.id == token.record.id


async def test_get_by_hash_not_found(session, make_refresh_token):
    await make_refresh_token()
    _, some_hash = create_refresh_token()
    refresh_token = await refresh_token_crud.get_by_hash(session, some_hash)
    assert refresh_token is None


async def test_revoke_token(session, make_refresh_token):
    token = await make_refresh_token()
    assert token.record.revoked_at is None  # before revoke
    await refresh_token_crud.revoke(session, token.record)
    assert token.record.revoked_at is not None


async def test_revoke_family_does_not_touch_other_family(session, make_refresh_token):
    family_a = uuid4()
    token_a1 = await make_refresh_token(family_id=family_a)
    token_a2 = await make_refresh_token(family_id=family_a)
    token_b = await make_refresh_token()
    await refresh_token_crud.revoke_family(session, family_a)
    await session.refresh(token_a1.record)
    await session.refresh(token_a2.record)
    await session.refresh(token_b.record)
    assert token_a1.record.revoked_at is not None
    assert token_a2.record.revoked_at is not None
    assert token_b.record.revoked_at is None


async def test_revoke_family_keeps_existing_revoked_at(session, make_refresh_token):
    family_a = uuid4()
    token_a1 = await make_refresh_token(family_id=family_a)
    token_a2 = await make_refresh_token(family_id=family_a)

    await refresh_token_crud.revoke(session, token_a1.record)
    first_revoked_at = token_a1.record.revoked_at

    await refresh_token_crud.revoke_family(session, family_a)
    await session.refresh(token_a1.record)
    await session.refresh(token_a2.record)
    assert token_a1.record.revoked_at == first_revoked_at
    assert token_a2.record.revoked_at > first_revoked_at
