import asyncio
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from spendlog.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password_async,
    verify_password_async,
)
from spendlog.settings import get_settings


async def test_hash_password() -> None:
    assert await hash_password_async("secret") != "secret"


async def test_two_hashes_give_different_hashes() -> None:
    first_password = await hash_password_async("secret")
    second_password = await hash_password_async("secret")
    assert first_password != second_password


async def test_verify_password() -> None:
    hashed_password = await hash_password_async("secret")
    assert await verify_password_async("secret", hashed_password)


async def test_verify_wrong_password() -> None:
    hashed_password = await hash_password_async("secret")
    assert not await verify_password_async("wrong", hashed_password)


async def _ticker(ticks: list[int], interval: float = 0.005) -> None:
    """Фоновая корутина: инкрементит счётчик раз в `interval` секунд."""
    while True:
        ticks[0] += 1
        await asyncio.sleep(interval)


@pytest.mark.asyncio
async def test_hash_password_async_returns_argon2_hash():
    hashed = await hash_password_async("hunter2")
    assert isinstance(hashed, str)
    assert hashed.startswith("$argon2")  # argon2-хэш начинается с $argon2...
    assert hashed != "hunter2"


@pytest.mark.asyncio
async def test_hash_password_async_uses_unique_salt():
    h1 = await hash_password_async("hunter2")
    h2 = await hash_password_async("hunter2")
    assert h1 != h2  # argon2 солит каждый хэш


@pytest.mark.asyncio
async def test_verify_password_async_ok():
    hashed = await hash_password_async("hunter2")
    assert await verify_password_async("hunter2", hashed) is True


@pytest.mark.asyncio
async def test_verify_password_async_wrong_password():
    hashed = await hash_password_async("hunter2")
    assert await verify_password_async("wrong", hashed) is False


@pytest.mark.asyncio
async def test_hash_password_async_does_not_block_event_loop():
    """
    Пока argon2 считает хэш в пуле потоков, event loop должен продолжать
    крутить другие задачи. Если хэширование заблокирует цикл — тикер
    не успеет сделать ни одного тика и assert провалится.
    """
    ticks = [0]
    ticker = asyncio.create_task(_ticker(ticks))

    # Даём тикеру запуститься и набрать стартовое значение
    await asyncio.sleep(0.02)
    ticks_before = ticks[0]

    hashed = await hash_password_async("hunter2")
    assert hashed.startswith("$argon2")

    ticker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await ticker

    # Ключевая проверка: во время хэширования тикер продолжал работу
    assert ticks[0] > ticks_before, (
        f"event loop был заблокирован: {ticks_before} - {ticks[0]}"
    )


@pytest.mark.asyncio
async def test_verify_password_async_does_not_block_event_loop():
    hashed = await hash_password_async("hunter2")
    ticks = [0]
    ticker = asyncio.create_task(_ticker(ticks))

    await asyncio.sleep(0.02)
    ticks_before = ticks[0]

    assert await verify_password_async("hunter2", hashed) is True

    ticker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await ticker

    assert ticks[0] > ticks_before


def test_create_access_token() -> None:
    token = create_access_token(1)
    payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    assert payload["sub"] == "1"
    assert "exp" in payload


def make_token(
    payload: dict, key: str | None = None, algorithm: str = ALGORITHM
) -> str:
    return jwt.encode(payload, key or get_settings().secret_key, algorithm=algorithm)


def future() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=5)


def test_decode_access_token_roundtrip() -> None:
    assert decode_access_token(create_access_token(1)) == 1


def test_decode_garbage_token() -> None:
    assert decode_access_token("garbage") is None


def test_decode_expired_token() -> None:
    token = make_token({"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)})
    assert decode_access_token(token) is None


def test_decode_token_signed_with_other_key() -> None:
    token = make_token(
        {"sub": "1", "exp": future()}, key="other-key-0123456789-0123456789!"
    )
    assert decode_access_token(token) is None


def test_decode_token_without_sub() -> None:
    assert decode_access_token(make_token({"exp": future()})) is None


def test_decode_token_without_exp() -> None:
    assert decode_access_token(make_token({"sub": "1"})) is None


@pytest.mark.parametrize("sub", ["abc", ""])
def test_decode_token_with_non_numeric_sub(sub: str) -> None:
    assert decode_access_token(make_token({"sub": sub, "exp": future()})) is None


def test_decode_unsigned_token_alg_none() -> None:
    token = jwt.encode({"sub": "1", "exp": future()}, key=None, algorithm="none")
    assert decode_access_token(token) is None
