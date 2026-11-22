from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from loguru import logger
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.db import get_session
from spendlog.main import app
from spendlog.models import RefreshToken
from spendlog.models.base import Base
from spendlog.security import create_refresh_token
from spendlog.settings import get_settings

SAMPLE_DATE = "2026-11-05T12:00:00+00:00"


@dataclass(frozen=True)
class CreatedRefreshToken:
    record: RefreshToken
    raw_token: str


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


@dataclass(frozen=True)
class UserCredentials:
    email: str
    password: str

    def as_register_json(self) -> dict[str, str]:
        return {"email": self.email, "password": self.password}

    def as_login_form(self) -> dict[str, str]:
        return {"username": self.email, "password": self.password}


class RefreshTokenFactory(Protocol):
    async def __call__(
        self,
        user_id: int,
        expires_at: datetime | None = None,
        family_id: UUID | None = None,
    ) -> CreatedRefreshToken: ...


class RegisterUserFactory(Protocol):
    async def __call__(self, user_credentials: UserCredentials) -> CreatedUser: ...


class LoginUserFactory(Protocol):
    async def __call__(self, user_credentials: UserCredentials) -> Response: ...


class TransactionPayloadFactory(Protocol):
    def __call__(
        self,
        category_id: int,
        **overrides: Any,
    ) -> dict[str, str]: ...


# ------- Helper function -------
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


# ------- End of helper function -------


# ------- Database, session, client fixtures -------
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


# ------- End -------


@pytest.fixture
def user_credentials() -> UserCredentials:
    return UserCredentials(email="user@test.com", password="password123")


@pytest.fixture
def other_user_credentials() -> UserCredentials:
    return UserCredentials(email="other@test.com", password="password123")


@pytest.fixture
def logs() -> Generator:
    records: list = []
    handler_id = logger.add(records.append, level="DEBUG")
    yield records
    logger.remove(handler_id)


@pytest.fixture
def register_user(client: AsyncClient) -> RegisterUserFactory:
    async def _register_user(user_credentials: UserCredentials) -> CreatedUser:
        register = await client.post(
            "/auth/register",
            json={
                "email": user_credentials.email,
                "password": user_credentials.password,
            },
        )
        assert register.status_code == 201
        register_json = register.json()
        return CreatedUser(id=register_json["id"], email=register_json["email"])

    return _register_user


@pytest.fixture
def login_user(client: AsyncClient) -> LoginUserFactory:
    async def _login_user(user_credentials: UserCredentials) -> Response:
        login_response = await client.post(
            "/auth/login",
            data={
                "username": user_credentials.email,
                "password": user_credentials.password,
            },
        )
        assert login_response.status_code == 200
        return login_response

    return _login_user


async def _build_auth_headers(
    register_user: RegisterUserFactory,
    login_user: LoginUserFactory,
    credentials: UserCredentials,
) -> dict[str, str]:
    await register_user(credentials)
    login_response = await login_user(credentials)
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.fixture
async def auth_headers(
    register_user: RegisterUserFactory,
    login_user: LoginUserFactory,
    user_credentials: UserCredentials,
) -> dict[str, str]:
    return await _build_auth_headers(register_user, login_user, user_credentials)


@pytest.fixture
async def other_auth_headers(
    register_user: RegisterUserFactory,
    login_user: LoginUserFactory,
    other_user_credentials: UserCredentials,
) -> dict[str, str]:
    return await _build_auth_headers(register_user, login_user, other_user_credentials)


@pytest.fixture
def make_refresh_token(session: AsyncSession) -> RefreshTokenFactory:
    async def _make_refresh_token(
        user_id: int,
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

        token_db_record = await refresh_token_crud.create(
            session=session,
            user_id=user_id,
            expires_at=expires_at,
            family_id=family_id,
            token_hash=token_hash,
        )
        return CreatedRefreshToken(record=token_db_record, raw_token=raw_token)

    return _make_refresh_token


@pytest.fixture
def make_transaction_payload() -> TransactionPayloadFactory:
    def _make_transaction_payload(
        category_id: int,
        **overrides,
    ) -> dict:
        payload = {
            "type": "expense",
            "amount": "10.50",
            "date": SAMPLE_DATE,
            "category_id": category_id,
            "comment": "lunch",
        }
        return payload | overrides

    return _make_transaction_payload


@pytest.fixture
def create_category(client: AsyncClient):
    async def _create_category(headers: dict[str, str], name: str = "Food") -> dict:
        response = await client.post(
            "/categories", json={"name": name}, headers=headers
        )
        assert response.status_code == 201
        return response.json()

    return _create_category


@pytest.fixture
def create_transaction(
    client: AsyncClient, make_transaction_payload: TransactionPayloadFactory
):
    async def _create_transaction(
        headers: dict[str, str],
        category_id: int,
        amount: str | None = None,
        date: str | None = None,
        **overrides,
    ) -> dict:
        if amount is not None:
            overrides["amount"] = amount
        if date is not None:
            overrides["date"] = date
        response = await client.post(
            "/transactions",
            json=make_transaction_payload(category_id, **overrides),
            headers=headers,
        )
        assert response.status_code == 201
        return response.json()

    return _create_transaction
