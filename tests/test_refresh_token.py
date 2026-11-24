from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from uuid import uuid4

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.crud import user as user_crud
from spendlog.models import RefreshToken
from spendlog.routers.auth import REFRESH_COOKIE_KEY
from spendlog.security import (
    create_refresh_token,
    hash_refresh_token,
)
from spendlog.settings import get_settings


def build_refresh_token(used_at: datetime | None = None, revoked_at: datetime | None = None, expires_at: datetime | None = None) -> RefreshToken:
    if expires_at is None:
        expires_at = datetime.now(tz=UTC) + get_settings().refresh_token_ttl
    return RefreshToken(user_id=1, token_hash="hash", used_at=used_at, revoked_at=revoked_at, expires_at=expires_at, family_id=uuid4())

async def test_refresh_token_hash_differs_from_raw(
    user_credentials, register_user, make_refresh_token
):
    user = await register_user(user_credentials)
    token = await make_refresh_token(user.id)
    assert token.raw_token != token.record.token_hash


async def test_refresh_token_hash_is_not_deterministic(
    user_credentials, register_user, make_refresh_token
):
    user = await register_user(user_credentials)
    token1 = await make_refresh_token(user.id)
    token2 = await make_refresh_token(user.id)
    assert token1.record.token_hash != token2.record.token_hash


async def test_get_by_hash_not_found(
    user_credentials, register_user, session, make_refresh_token
):
    user = await register_user(user_credentials)
    await make_refresh_token(user.id)
    _, some_hash = create_refresh_token()
    refresh_token = await refresh_token_crud.get_by_hash(session, some_hash)
    assert refresh_token is None


async def test_revoke_family_does_not_touch_other_family(
    user_credentials, register_user, session, make_refresh_token
):
    user = await register_user(user_credentials)
    family_a = uuid4()
    token_a1 = await make_refresh_token(user.id, family_id=family_a)
    token_a2 = await make_refresh_token(user.id, family_id=family_a)
    token_b = await make_refresh_token(user.id)
    await refresh_token_crud.revoke_family(session, family_a)
    await session.refresh(token_a1.record)
    await session.refresh(token_a2.record)
    await session.refresh(token_b.record)
    assert token_a1.record.revoked_at is not None
    assert token_a2.record.revoked_at is not None
    assert token_b.record.revoked_at is None


async def test_login_sets_refresh_cookie_with_flags(
    user_credentials, register_user, login_user
):
    await register_user(user_credentials)
    login_response = await login_user(user_credentials)
    # Parsing cookie
    cookie = SimpleCookie()
    login_set_cookie_header = login_response.headers.get_list("set-cookie")[0]
    cookie.load(login_set_cookie_header)
    morsel = cookie[REFRESH_COOKIE_KEY]

    assert morsel["httponly"]
    assert morsel["path"] == "/auth"
    assert morsel["samesite"] == get_settings().cookie_samesite
    assert int(morsel["max-age"]) == get_settings().cookie_max_age
    assert morsel.value

    assert "access_token" in login_response.json()


async def test_login_returns_access_token_without_refresh_in_body(
    user_credentials, register_user, login_user
):
    await register_user(user_credentials)
    login_response = await login_user(user_credentials)
    assert REFRESH_COOKIE_KEY not in login_response.json()
    assert login_response.cookies["refresh_token"] not in login_response.text
    assert "access_token" in login_response.json()


async def test_login_stores_hash_not_raw_token(
    user_credentials, register_user, login_user, session
):
    await register_user(user_credentials)
    login_response = await login_user(user_credentials)
    raw_token = login_response.cookies[REFRESH_COOKIE_KEY]
    token = await refresh_token_crud.get_by_hash(session, hash_refresh_token(raw_token))
    raw_token_from_db = await refresh_token_crud.get_by_hash(session, raw_token)
    assert raw_token_from_db is None
    assert token is not None


async def test_login_creates_new_family_each_time(
    user_credentials, register_user, login_user, session
):
    await register_user(user_credentials)
    first_login_response = await login_user(user_credentials)
    first_token_hash = hash_refresh_token(
        first_login_response.cookies[REFRESH_COOKIE_KEY]
    )

    second_login_response = await login_user(user_credentials)
    second_token_hash = hash_refresh_token(
        second_login_response.cookies[REFRESH_COOKIE_KEY]
    )

    first_refresh_token = await refresh_token_crud.get_by_hash(
        session, first_token_hash
    )
    second_refresh_token = await refresh_token_crud.get_by_hash(
        session, second_token_hash
    )
    assert first_refresh_token is not None
    assert second_refresh_token is not None

    assert first_refresh_token.family_id != second_refresh_token.family_id


async def test_get_refresh_token_by_hash_returns_record(
    session, user_credentials, make_refresh_token
):
    user = await user_crud.create(
        session, user_credentials.email, user_credentials.password
    )
    refresh_token = await make_refresh_token(user_id=user.id)
    refresh_token_from_db = await refresh_token_crud.get_by_hash(
        session, hash_refresh_token(refresh_token.raw_token)
    )
    assert refresh_token_from_db is not None
    assert refresh_token_from_db.user_id == user.id
    assert refresh_token_from_db.token_hash == refresh_token.record.token_hash
    assert refresh_token.record.id == refresh_token_from_db.id


async def test_rotate_marks_old_token_used(
    session, user_credentials, make_refresh_token
):
    user = await user_crud.create(
        session, user_credentials.email, user_credentials.password
    )
    old_refresh_token = await make_refresh_token(user_id=user.id)
    new_expires_at = datetime.now(tz=UTC) + timedelta(days=42)
    _, new_token_hash = create_refresh_token()
    await refresh_token_crud.rotate(
        session, old_refresh_token.record, new_expires_at, new_token_hash
    )
    assert old_refresh_token.record.used_at is not None


async def test_rotate_keeps_family_id(session, user_credentials, make_refresh_token):
    user = await user_crud.create(
        session, user_credentials.email, user_credentials.password
    )
    old_refresh_token = await make_refresh_token(user_id=user.id)
    new_expires_at = datetime.now(tz=UTC) + timedelta(days=42)
    _, new_token_hash = create_refresh_token()
    new_refresh_token = await refresh_token_crud.rotate(
        session, old_refresh_token.record, new_expires_at, new_token_hash
    )
    assert new_refresh_token.used_at is None
    assert new_refresh_token.revoked_at is None
    assert old_refresh_token.record.family_id == new_refresh_token.family_id
    assert new_refresh_token.token_hash != old_refresh_token.record.token_hash


async def test_is_valid_active_token_returns_true():
    refresh_token = build_refresh_token()
    assert refresh_token_crud.is_valid(refresh_token)

async def test_is_valid_used_token_returns_false():
    refresh_token = build_refresh_token(used_at=datetime.now(tz=UTC))
    assert not refresh_token_crud.is_valid(refresh_token)

async def test_is_valid_revoked_token_returns_false():
    refresh_token = build_refresh_token(revoked_at=datetime.now(tz=UTC))
    assert not refresh_token_crud.is_valid(refresh_token)
    
async def test_is_valid_expired_token_returns_false():
    refresh_token = build_refresh_token(expires_at=datetime.now(tz=UTC) - timedelta(seconds=2))
    assert not refresh_token_crud.is_valid(refresh_token)
    