from sqlalchemy import select

from spendlog.models import User
from spendlog.security import verify_password

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
