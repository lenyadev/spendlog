from datetime import UTC, datetime, timedelta

import jwt
import pytest

from spendlog.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from spendlog.settings import get_settings


def test_hash_password() -> None:
    assert hash_password("secret") != "secret"


def test_two_hashes_give_different_hashes() -> None:
    first_password = hash_password("secret")
    second_password = hash_password("secret")
    assert first_password != second_password


def test_verify_password() -> None:
    hashed_password = hash_password("secret")
    assert verify_password("secret", hashed_password)


def test_verify_wrong_password() -> None:
    hashed_password = hash_password("secret")
    assert not verify_password("wrong", hashed_password)


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
        {"sub": "1", "exp": future()}, key="other-key-0123456789-0123456789"
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
