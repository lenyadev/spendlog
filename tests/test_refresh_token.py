from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import NamedTuple, Protocol
from uuid import UUID, uuid4

import pytest
from httpx import Response

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.models import RefreshToken
from spendlog.routers.auth import REFRESH_COOKIE_KEY
from spendlog.security import create_refresh_token, hash_refresh_token
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
async def login(
    client, created_user, user_credentials
) -> Callable[[], Awaitable[Response]]:
    async def _login() -> Response:
        login = await client.post(
            "/auth/login",
            data={
                "username": user_credentials["email"],
                "password": user_credentials["password"],
            },
        )
        assert login.status_code == 200
        return login

    return _login


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


async def test_refresh_token_generation_is_unique(session, make_refresh_token):
    token = await make_refresh_token()
    refresh_token = await refresh_token_crud.get_by_hash(
        session, token.record.token_hash
    )
    assert refresh_token is not None
    assert refresh_token.id == token.record.id


async def test_refresh_token_hash_differs_from_raw(make_refresh_token):
    token = await make_refresh_token()
    assert token.raw_token != token.record.token_hash


async def test_refresh_token_hash_is_deterministic(make_refresh_token):
    token1 = await make_refresh_token()
    token2 = await make_refresh_token()
    assert token1.record.token_hash != token2.record.token_hash


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


async def test_login_sets_refresh_cookie_with_flags(login):
    user_login = await login()
    cookie = SimpleCookie()
    login_set_cookie_header = user_login.headers.get_list("set-cookie")[0]
    cookie.load(login_set_cookie_header)
    morsel = cookie[REFRESH_COOKIE_KEY]

    assert morsel["httponly"]
    assert morsel["path"] == "/auth"
    assert morsel["samesite"] == get_settings().cookie_samesite
    assert int(morsel["max-age"]) == get_settings().cookie_max_age
    assert morsel.value

    assert "access_token" in user_login.json()


async def test_login_returns_access_token_without_refresh_in_body(
    login,
):
    user_login = await login()
    assert REFRESH_COOKIE_KEY not in user_login.json()
    assert REFRESH_COOKIE_KEY not in user_login.text
    assert user_login.cookies["refresh_token"] not in user_login.text
    assert "access_token" in user_login.json()


async def test_login_stores_hash_not_raw_token(session, login):
    user_login = await login()
    raw_token = user_login.cookies[REFRESH_COOKIE_KEY]
    token = await refresh_token_crud.get_by_hash(session, hash_refresh_token(raw_token))
    raw_token_from_db = await refresh_token_crud.get_by_hash(session, raw_token)
    assert raw_token_from_db is None
    assert token is not None
    assert token.token_hash != raw_token


async def test_login_creates_new_family_each_time(session, login):
    first_login = await login()
    first_token_hash = hash_refresh_token(first_login.cookies[REFRESH_COOKIE_KEY])

    second_login = await login()
    second_token_hash = hash_refresh_token(second_login.cookies[REFRESH_COOKIE_KEY])

    first_refresh_token = await refresh_token_crud.get_by_hash(
        session, first_token_hash
    )
    second_refresh_token = await refresh_token_crud.get_by_hash(
        session, second_token_hash
    )
    assert first_refresh_token is not None
    assert second_refresh_token is not None

    assert first_refresh_token.family_id != second_refresh_token.family_id
