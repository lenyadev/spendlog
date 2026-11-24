from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from pytest import MonkeyPatch

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.routers.auth import REFRESH_COOKIE_KEY, REFRESH_COOKIE_PATH
from spendlog.security import create_refresh_token, hash_refresh_token


async def test_refresh_returns_new_pair(
    session, user_credentials, register_user, login_user, client
):
    await register_user(user_credentials)
    login_response = await login_user(user_credentials)
    old_raw_token = login_response.cookies[REFRESH_COOKIE_KEY]
    refresh_response = await client.post("/auth/refresh")
    new_raw_token = refresh_response.cookies[REFRESH_COOKIE_KEY]

    assert refresh_response.status_code == 200

    old_refresh_token_from_db = await refresh_token_crud.get_by_hash(
        session, hash_refresh_token(old_raw_token)
    )
    new_refresh_token_from_db = await refresh_token_crud.get_by_hash(
        session, hash_refresh_token(new_raw_token)
    )

    assert old_refresh_token_from_db is not None
    assert new_refresh_token_from_db is not None

    await session.refresh(old_refresh_token_from_db)

    assert old_refresh_token_from_db.used_at is not None
    assert old_raw_token != new_raw_token

    assert new_refresh_token_from_db.used_at is None
    assert old_refresh_token_from_db.family_id == new_refresh_token_from_db.family_id
    assert refresh_response.json()["access_token"]


async def test_refresh_commits_transaction(
    monkeypatch: MonkeyPatch,
    session,
    client,
    user_credentials,
    register_user,
    login_user,
):
    await register_user(user_credentials)
    await login_user(user_credentials)
    mock = AsyncMock(wraps=session.commit)
    monkeypatch.setattr(session, "commit", mock)
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    mock.assert_awaited_once()


async def test_refresh_without_cookie_returns_401(client):
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Refresh token is invalid"


async def test_refresh_unknown_token_returns_401(client):
    unknown_token, _ = create_refresh_token()
    client.cookies.set(REFRESH_COOKIE_KEY, unknown_token, path=REFRESH_COOKIE_PATH)
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Refresh token is invalid"


async def test_refresh_expired_token_returns_401(
    client, register_user, user_credentials, make_refresh_token
):
    user = await register_user(user_credentials)
    expired_at = datetime.now(tz=UTC) - timedelta(days=42)
    expired_token = await make_refresh_token(user.id, expires_at=expired_at)
    client.cookies.set(
        REFRESH_COOKIE_KEY, expired_token.raw_token, path=REFRESH_COOKIE_PATH
    )
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Refresh token is invalid"


async def test_refresh_used_token_returns_401(
    client, user_credentials, register_user, login_user
):
    await register_user(user_credentials)
    login_response = await login_user(user_credentials)

    old_raw_token = login_response.cookies[REFRESH_COOKIE_KEY]
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200

    client.cookies.delete(REFRESH_COOKIE_KEY)
    client.cookies.set(REFRESH_COOKIE_KEY, old_raw_token, path=REFRESH_COOKIE_PATH)
    reuse_response = await client.post("/auth/refresh")

    assert reuse_response.status_code == 401
    assert reuse_response.json()["detail"] == "Refresh token is invalid"


async def test_refresh_access_token_works(
    client, user_credentials, register_user, login_user
):
    await register_user(user_credentials)
    await login_user(user_credentials)

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]

    access_token = refresh_response.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == user_credentials.email


async def test_refresh_reuse_revokes_whole_family(
    session, client, user_credentials, register_user, login_user
):
    await register_user(user_credentials)
    login_response = await login_user(user_credentials)
    old_raw_token = login_response.cookies[REFRESH_COOKIE_KEY]

    first_refresh_response = await client.post("/auth/refresh")
    assert first_refresh_response.status_code == 200
    new_raw_token = first_refresh_response.cookies[REFRESH_COOKIE_KEY]

    client.cookies.delete(REFRESH_COOKIE_KEY, path=REFRESH_COOKIE_PATH)

    client.cookies.set(REFRESH_COOKIE_KEY, old_raw_token, path=REFRESH_COOKIE_PATH)
    second_refresh_response = await client.post("/auth/refresh")
    assert second_refresh_response.status_code == 401

    new_token_record = await refresh_token_crud.get_by_hash(
        session, hash_refresh_token(new_raw_token)
    )
    assert new_token_record is not None
    await session.refresh(new_token_record)
    assert new_token_record.revoked_at is not None

    client.cookies.delete(REFRESH_COOKIE_KEY, path=REFRESH_COOKIE_PATH)
    client.cookies.set(REFRESH_COOKIE_KEY, new_raw_token, path=REFRESH_COOKIE_PATH)

    third_refresh_response = await client.post("/auth/refresh")
    assert third_refresh_response.status_code == 401


# test_refresh_reuse_does_not_touch_other_families
