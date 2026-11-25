import secrets

from spendlog.routers.auth import REFRESH_COOKIE_KEY, REFRESH_COOKIE_PATH
from tests.helpers import get_refresh_token_record, parse_set_cookie, raw_token_from


async def test_logout_valid_refresh_returns_204(client, session, logged_in):
    raw_token = raw_token_from(logged_in)
    logout_response = await client.post("/auth/logout")

    cookie = parse_set_cookie(logout_response)
    refresh_token = await get_refresh_token_record(session, raw_token)
    assert refresh_token is not None
    await session.refresh(refresh_token)

    assert refresh_token.revoked_at is not None
    assert logout_response.status_code == 204
    assert cookie.value == ""
    assert cookie["max-age"] == "0"


async def test_logout_without_cookie_returns_204(client, session, logged_in):
    client.cookies.clear()
    assert not client.cookies
    logout_response = await client.post("/auth/logout")

    refresh_token = await get_refresh_token_record(session, raw_token_from(logged_in))
    assert refresh_token is not None

    assert refresh_token.revoked_at is None
    assert logout_response.status_code == 204
    assert "set-cookie" not in logout_response.headers


async def test_logout_unknown_token_returns_204_and_clears_cookie(
    client, session, logged_in
):
    client.cookies.clear()
    client.cookies.set(
        REFRESH_COOKIE_KEY, secrets.token_urlsafe(32), path=REFRESH_COOKIE_PATH
    )
    logout_response = await client.post("/auth/logout")

    refresh_token = await get_refresh_token_record(session, raw_token_from(logged_in))
    assert refresh_token is not None

    cookie = parse_set_cookie(logout_response)

    assert refresh_token.revoked_at is None
    assert logout_response.status_code == 204
    assert cookie.value == ""
    assert cookie["max-age"] == "0"


async def test_refresh_after_logout_returns_401(client, logged_in):
    raw_token = raw_token_from(logged_in)
    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 204

    refresh_response = await client.post(
        "/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE_KEY}={raw_token}"}
    )
    assert raw_token in refresh_response.request.headers["cookie"]
    assert refresh_response.status_code == 401
    assert "access_token" not in refresh_response.json()


async def test_logout_revokes_rotated_chain(client, session, logged_in):
    old_raw = raw_token_from(logged_in)
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200

    new_raw = raw_token_from(refresh_response)

    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 204

    old_refresh_record = await get_refresh_token_record(session, old_raw)
    new_refresh_record = await get_refresh_token_record(session, new_raw)
    assert old_refresh_record is not None
    assert new_refresh_record is not None

    await session.refresh(old_refresh_record)
    await session.refresh(new_refresh_record)

    assert old_refresh_record.revoked_at is not None
    assert new_refresh_record.revoked_at is not None


async def test_logout_already_revoked_token_returns_204(client, session, logged_in):
    raw_token = raw_token_from(logged_in)
    first_logout = await client.post("/auth/logout")

    first_refresh_record = await get_refresh_token_record(session, raw_token)
    assert first_refresh_record is not None
    first_revoked_at = first_refresh_record.revoked_at
    assert first_refresh_record.revoked_at is not None

    second_logout = await client.post(
        "/auth/logout", headers={"Cookie": f"{REFRESH_COOKIE_KEY}={raw_token}"}
    )
    await session.refresh(first_refresh_record)
    assert first_refresh_record.revoked_at == first_revoked_at
    cookie = parse_set_cookie(second_logout)
    assert first_logout.status_code == 204
    assert second_logout.status_code == 204
    assert raw_token in second_logout.request.headers["cookie"]
    assert cookie.value == ""
    assert cookie["max-age"] == "0"


async def test_logout_does_not_revoke_other_user_tokens(
    session, client, other_client, user_credentials, other_user_credentials
):
    user_a = await client.post(
        "/auth/register", json=user_credentials.as_register_json()
    )
    assert user_a.status_code == 201
    login_a_response = await client.post(
        "/auth/login", data=user_credentials.as_login_form()
    )
    assert login_a_response.status_code == 200

    user_b = await other_client.post(
        "/auth/register", json=other_user_credentials.as_register_json()
    )
    assert user_b.status_code == 201
    login_b_response = await other_client.post(
        "/auth/login", data=other_user_credentials.as_login_form()
    )
    assert login_b_response.status_code == 200

    raw_a = raw_token_from(login_a_response)
    raw_b = raw_token_from(login_b_response)

    logout_a_response = await client.post("/auth/logout")
    assert logout_a_response.status_code == 204

    refresh_b_response = await other_client.post("/auth/refresh")
    assert refresh_b_response.status_code == 200
    assert "access_token" in refresh_b_response.json()

    refresh_b_record = await get_refresh_token_record(session, raw_b)
    refresh_a_record = await get_refresh_token_record(session, raw_a)
    assert refresh_a_record is not None
    assert refresh_b_record is not None
    await session.refresh(refresh_b_record)
    await session.refresh(refresh_a_record)
    assert refresh_b_record.revoked_at is None
    assert refresh_a_record.family_id != refresh_b_record.family_id
