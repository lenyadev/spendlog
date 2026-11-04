import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from spendlog.db import get_session
from spendlog.main import app
from spendlog.models.base import Base
from spendlog.settings import get_settings


async def register_and_login(client, credentials: dict[str, str]) -> dict[str, str]:
    register = await client.post("/auth/register", json=credentials)
    assert register.status_code == 201

    login = await client.post(
        "/auth/login",
        data={
            "username": credentials["email"],
            "password": credentials["password"],
        },
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def ensure_test_database(url: str) -> None:
    parsed = make_url(url)
    admin_engine = create_async_engine(
        parsed.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": parsed.database},
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    await admin_engine.dispose()


@pytest.fixture(scope="session")
async def test_engine():
    settings = get_settings()
    assert settings.test_database_url, "TEST_DATABASE_URL не задан"
    assert settings.test_database_url != settings.database_url, (
        "TEST_DATABASE_URL совпадает с рабочей БД"
    )
    await ensure_test_database(settings.test_database_url)

    engine = create_async_engine(settings.test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(test_engine):
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        async_session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield async_session
        finally:
            await async_session.close()
            await trans.rollback()


@pytest.fixture
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def user_credentials() -> dict[str, str]:
    return {"email": "user@test.com", "password": "password123"}


@pytest.fixture
def other_user_credentials() -> dict[str, str]:
    return {"email": "other@test.com", "password": "password123"}


@pytest.fixture
async def auth_headers(client, user_credentials) -> dict[str, str]:
    return await register_and_login(client, user_credentials)


@pytest.fixture
async def other_auth_headers(client, other_user_credentials) -> dict[str, str]:
    return await register_and_login(client, other_user_credentials)
