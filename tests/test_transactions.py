from datetime import UTC, datetime
from decimal import Decimal

import pytest

DATE = "2026-11-05T12:00:00+00:00"


def make_payload(category_id: int, **overrides) -> dict:
    payload = {
        "type": "expense",
        "amount": "10.50",
        "date": DATE,
        "category_id": category_id,
        "comment": "lunch",
    }
    return payload | overrides


@pytest.fixture
def create_transaction(client):
    async def _create(headers: dict[str, str], category_id: int, **overrides) -> dict:
        response = await client.post(
            "/transactions",
            json=make_payload(category_id, **overrides),
            headers=headers,
        )
        assert response.status_code == 201
        return response.json()

    return _create


# --- CRUD ---


@pytest.mark.parametrize("type_", ["expense", "income"])
async def test_create_transaction(
    auth_headers, type_, create_category, create_transaction
):
    category = await create_category(auth_headers)

    body = await create_transaction(auth_headers, category["id"], type=type_)

    assert body["type"] == type_
    assert Decimal(body["amount"]) == Decimal("10.50")
    assert datetime.fromisoformat(body["date"]) == datetime(2026, 11, 5, 12, tzinfo=UTC)
    assert body["category_id"] == category["id"]
    assert body["comment"] == "lunch"
    assert "id" in body
    assert "user_id" not in body


async def test_create_transaction_without_comment(
    client, auth_headers, create_category
):
    category = await create_category(auth_headers)
    payload = make_payload(category["id"])
    del payload["comment"]

    response = await client.post("/transactions", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["comment"] is None


async def test_get_update_delete_transaction(
    client, auth_headers, create_category, create_transaction
):
    food = await create_category(auth_headers, "Food")
    salary = await create_category(auth_headers, "Salary")
    transaction = await create_transaction(auth_headers, food["id"])
    url = f"/transactions/{transaction['id']}"

    get = await client.get(url, headers=auth_headers)
    assert get.status_code == 200
    assert get.json()["id"] == transaction["id"]

    put = await client.put(
        url,
        json=make_payload(
            salary["id"], type="income", amount="2000.00", comment="updated"
        ),
        headers=auth_headers,
    )
    assert put.status_code == 200
    body = put.json()
    assert body["category_id"] == salary["id"]
    assert body["type"] == "income"
    assert Decimal(body["amount"]) == Decimal("2000.00")
    assert body["comment"] == "updated"

    delete = await client.delete(url, headers=auth_headers)
    assert delete.status_code == 204

    after = await client.get(url, headers=auth_headers)
    assert after.status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"amount": 0}, id="amount-zero"),
        pytest.param({"amount": -5}, id="amount-negative"),
        pytest.param({"amount": "10.123"}, id="amount-three-decimals"),
        pytest.param({"date": "2026-11-05T12:00:00"}, id="date-without-timezone"),
        pytest.param({"type": "transfer"}, id="unknown-type"),
        pytest.param({"comment": "a" * 256}, id="comment-too-long"),
    ],
)
async def test_create_transaction_invalid_data(
    client, auth_headers, create_category, overrides
):
    category = await create_category(auth_headers)

    response = await client.post(
        "/transactions",
        json=make_payload(category["id"], **overrides),
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("POST", "/transactions"),
        ("GET", "/transactions/1"),
        ("PUT", "/transactions/1"),
        ("DELETE", "/transactions/1"),
    ],
)
async def test_transactions_require_auth(client, method, url):
    response = await client.request(method, url, json=make_payload(1))
    assert response.status_code == 401


# --- Права доступа ---


async def test_other_user_cannot_access_foreign_transaction(
    client, auth_headers, other_auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    transaction = await create_transaction(auth_headers, category["id"])
    other_category = await create_category(other_auth_headers)
    url = f"/transactions/{transaction['id']}"

    get = await client.get(url, headers=other_auth_headers)
    put = await client.put(
        url,
        json=make_payload(other_category["id"], amount="999.00"),
        headers=other_auth_headers,
    )
    delete = await client.delete(url, headers=other_auth_headers)

    assert get.status_code == 404
    assert put.status_code == 404
    assert delete.status_code == 404

    own = await client.get(url, headers=auth_headers)
    assert own.status_code == 200
    assert own.json() == transaction


async def test_cannot_create_transaction_in_foreign_category(
    client, auth_headers, other_auth_headers, create_category
):
    category = await create_category(auth_headers)

    response = await client.post(
        "/transactions",
        json=make_payload(category["id"]),
        headers=other_auth_headers,
    )

    assert response.status_code == 404


async def test_cannot_move_transaction_to_foreign_category(
    client, auth_headers, other_auth_headers, create_category, create_transaction
):
    own_category = await create_category(auth_headers, "Food")
    foreign_category = await create_category(other_auth_headers, "Other")
    transaction = await create_transaction(auth_headers, own_category["id"])

    response = await client.put(
        f"/transactions/{transaction['id']}",
        json=make_payload(foreign_category["id"]),
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_missing_category_looks_like_foreign_one(
    client, auth_headers, other_auth_headers, create_category
):
    foreign = await create_category(auth_headers)

    foreign_response = await client.post(
        "/transactions",
        json=make_payload(foreign["id"]),
        headers=other_auth_headers,
    )
    missing_response = await client.post(
        "/transactions",
        json=make_payload(999999),
        headers=other_auth_headers,
    )

    assert foreign_response.status_code == 404
    assert missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json()


async def test_category_can_be_deleted_after_its_transaction(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    transaction = await create_transaction(auth_headers, category["id"])

    blocked = await client.delete(f"/categories/{category['id']}", headers=auth_headers)
    assert blocked.status_code == 409

    await client.delete(f"/transactions/{transaction['id']}", headers=auth_headers)

    deleted = await client.delete(f"/categories/{category['id']}", headers=auth_headers)
    assert deleted.status_code == 204
