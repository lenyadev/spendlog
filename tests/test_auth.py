from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from spendlog.models import User
from spendlog.security import ALGORITHM, verify_password
from spendlog.settings import get_settings


async def test_register_success(client, user_credentials):
    response = await client.post(
        "/auth/register", json=user_credentials.as_register_json()
    )
    body = response.json()

    assert response.status_code == 201
    assert body["email"] == user_credentials.email
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email(client, user_credentials):
    first = await client.post(
        "/auth/register", json=user_credentials.as_register_json()
    )
    second = await client.post(
        "/auth/register", json=user_credentials.as_register_json()
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_register_stores_hash(client, session, user_credentials):
    await client.post("/auth/register", json=user_credentials.as_register_json())

    user = await session.scalar(
        select(User).where(User.email == user_credentials.email)
    )
    assert user is not None
    assert user.password_hash != user_credentials.password
    assert verify_password(user_credentials.password, user.password_hash)


async def test_login_success(user_credentials, register_user, login_user):
    await register_user(user_credentials)

    login_response = await login_user(user_credentials)
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()
    assert login_response.json()["token_type"] == "bearer"


async def test_login_token_contains_user_id_and_exp(
    user_credentials, register_user, login_user
):
    user = await register_user(user_credentials)
    login_response = await login_user(user_credentials)
    payload = jwt.decode(
        login_response.json()["access_token"],
        get_settings().secret_key,
        algorithms=[ALGORITHM],
    )

    assert payload["sub"] == str(user.id)
    assert "exp" in payload


async def test_login_with_incorrect_password(client, user_credentials):
    await client.post("/auth/register", json=user_credentials.as_register_json())
    response = await client.post(
        "/auth/login",
        data={"username": user_credentials.email, "password": "012345678"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_login_with_incorrect_username(client, register_user, user_credentials):
    await register_user(user_credentials)
    response = await client.post(
        "/auth/login",
        data={"username": "test@com.com", "password": user_credentials.password},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_me_success(client, user_credentials, auth_headers):
    response = await client.get("/auth/me", headers=auth_headers)
    body = response.json()

    assert response.status_code == 200
    assert body["email"] == user_credentials.email
    assert "id" in body
    assert "password_hash" not in body


async def test_me_without_header(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


async def test_me_with_garbage_token(client):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_me_with_expired_token(
    client, user_credentials, register_user, login_user
):
    user = await register_user(user_credentials)
    await login_user(user_credentials)

    token = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        get_settings().secret_key,
        algorithm=ALGORITHM,
    )
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_me_after_user_deleted(client, auth_headers, session, user_credentials):
    user = await session.scalar(
        select(User).where(User.email == user_credentials.email)
    )
    assert user is not None
    await session.delete(user)
    await session.flush()

    response = await client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
