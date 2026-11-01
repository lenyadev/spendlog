import jwt

from spendlog.security import (
    ALGORITHM,
    create_access_token,
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
