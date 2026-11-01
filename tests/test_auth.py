import jwt
from sqlalchemy import select

from spendlog.models import User
from spendlog.security import ALGORITHM, verify_password
from spendlog.settings import get_settings

VALID = {"email": "a@test.com", "password": "password123"}


async def test_register_success(client):
    response = await client.post("/auth/register", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "a@test.com"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email(client):
    first = await client.post("/auth/register", json=VALID)
    second = await client.post("/auth/register", json=VALID)

    assert first.status_code == 201
    assert second.status_code == 409


async def test_register_stores_hash(client, session):
    await client.post("/auth/register", json=VALID)

    user = await session.scalar(select(User).where(User.email == "a@test.com"))
    assert user is not None
    assert user.password_hash != VALID["password"]
    assert verify_password(VALID["password"], user.password_hash)


async def test_login_success(client):
    await client.post("/auth/register", json=VALID)
    response = await client.post(
        "/auth/login", data={"username": VALID["email"], "password": VALID["password"]}
    )

    body = response.json()
    assert response.status_code == 200
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_token_decoding(client):
    register = await client.post("/auth/register", json=VALID)
    user_id = register.json()["id"]

    response = await client.post(
        "/auth/login",
        data={"username": VALID["email"], "password": VALID["password"]},
    )
    token = response.json()["access_token"]

    payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    assert payload["sub"] == str(user_id)
    assert "exp" in payload


async def test_login_with_incorrect_password(client):
    await client.post("/auth/register", json=VALID)
    response = await client.post(
        "/auth/login", data={"username": VALID["email"], "password": "012345678"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_login_with_incorrect_username(client):
    await client.post("/auth/register", json=VALID)
    response = await client.post(
        "/auth/login", data={"username": "test@com.com", "password": VALID["password"]}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
