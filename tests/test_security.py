from spendlog.security import hash_password, verify_password


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
