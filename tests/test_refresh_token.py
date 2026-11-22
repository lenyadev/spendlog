from http.cookies import SimpleCookie
from uuid import uuid4

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.routers.auth import REFRESH_COOKIE_KEY
from spendlog.security import create_refresh_token, hash_refresh_token
from spendlog.settings import get_settings


async def test_refresh_token_generation_is_unique(
    session, user_credentials, register_user, login_user, make_refresh_token
):
    user = await register_user(user_credentials)
    await login_user(user_credentials)
    token = await make_refresh_token(user.id)
    refresh_token = await refresh_token_crud.get_by_hash(
        session, token.record.token_hash
    )
    assert refresh_token is not None
    assert refresh_token.id == token.record.id


async def test_refresh_token_hash_differs_from_raw(
    user_credentials, register_user, login_user, make_refresh_token
):
    user = await register_user(user_credentials)
    await login_user(user_credentials)
    token = await make_refresh_token(user.id)
    assert token.raw_token != token.record.token_hash


async def test_refresh_token_hash_is_deterministic(
    user_credentials, register_user, login_user, make_refresh_token
):
    user = await register_user(user_credentials)
    await login_user(user_credentials)
    await login_user(user_credentials)
    token1 = await make_refresh_token(user.id)
    token2 = await make_refresh_token(user.id)
    assert token1.record.token_hash != token2.record.token_hash


async def test_get_by_hash_not_found(
    user_credentials, register_user, login_user, session, make_refresh_token
):
    user = await register_user(user_credentials)
    await login_user(user_credentials)
    await make_refresh_token(user.id)
    _, some_hash = create_refresh_token()
    refresh_token = await refresh_token_crud.get_by_hash(session, some_hash)
    assert refresh_token is None


async def test_revoke_token(
    user_credentials, register_user, login_user, session, make_refresh_token
):
    user = await register_user(user_credentials)
    await login_user(user_credentials)
    token = await make_refresh_token(user.id)
    assert token.record.revoked_at is None  # before revoke
    await refresh_token_crud.revoke(session, token.record)
    assert token.record.revoked_at is not None


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


async def test_revoke_family_keeps_existing_revoked_at(
    user_credentials, register_user, session, make_refresh_token
):
    user = await register_user(user_credentials)

    family_a = uuid4()
    token_a1 = await make_refresh_token(user.id, family_id=family_a)
    token_a2 = await make_refresh_token(user.id, family_id=family_a)

    await refresh_token_crud.revoke(session, token_a1.record)
    first_revoked_at = token_a1.record.revoked_at

    await refresh_token_crud.revoke_family(session, family_a)
    await session.refresh(token_a1.record)
    await session.refresh(token_a2.record)
    assert token_a1.record.revoked_at == first_revoked_at
    assert token_a2.record.revoked_at > first_revoked_at


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
    assert REFRESH_COOKIE_KEY not in login_response.text
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
    assert token.token_hash != raw_token


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
