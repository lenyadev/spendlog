import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from spendlog.db import get_session
from spendlog.main import app
from spendlog.models.base import Base
from spendlog.settings import get_settings


@pytest.fixture(scope="session")
async def test_engine():
    settings = get_settings()
    assert settings.test_database_url, "TEST_DATABASE_URL не задан"
    assert settings.test_database_url != settings.database_url, (
        "TEST_DATABASE_URL совпадает с рабочей БД"
    )

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
