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


# --- Список: хелперы ---


def iso(day: int, hour: int = 12) -> str:
    return datetime(2026, 11, day, hour, tzinfo=UTC).isoformat()


async def get_page(client, headers, **params) -> dict:
    response = await client.get("/transactions", params=params, headers=headers)
    assert response.status_code == 200
    return response.json()


def ids(page: dict) -> list[int]:
    return [item["id"] for item in page["items"]]


# --- Фильтры ---


async def test_list_without_filters(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    for day in (1, 2, 3):
        await create_transaction(auth_headers, category["id"], date=iso(day))

    page = await get_page(client, auth_headers)

    assert page["total"] == 3
    assert len(page["items"]) == 3
    assert page["limit"] == 50
    assert page["offset"] == 0


async def test_list_empty(client, auth_headers):
    page = await get_page(client, auth_headers)

    assert page["items"] == []
    assert page["total"] == 0


async def test_filter_by_type(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    await create_transaction(auth_headers, category["id"], type="expense")
    await create_transaction(auth_headers, category["id"], type="expense")
    await create_transaction(auth_headers, category["id"], type="income")

    expenses = await get_page(client, auth_headers, type="expense")
    incomes = await get_page(client, auth_headers, type="income")

    assert expenses["total"] == 2
    assert {i["type"] for i in expenses["items"]} == {"expense"}
    assert incomes["total"] == 1
    assert {i["type"] for i in incomes["items"]} == {"income"}


async def test_filter_by_category(
    client, auth_headers, create_category, create_transaction
):
    food = await create_category(auth_headers, "Food")
    taxi = await create_category(auth_headers, "Taxi")
    in_food = await create_transaction(auth_headers, food["id"])
    await create_transaction(auth_headers, taxi["id"])

    page = await get_page(client, auth_headers, category_id=food["id"])

    assert ids(page) == [in_food["id"]]
    assert page["total"] == 1


async def test_filter_by_period_includes_both_borders(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    created = {
        day: await create_transaction(auth_headers, category["id"], date=iso(day))
        for day in (4, 5, 10, 15, 16)
    }

    page = await get_page(client, auth_headers, date_from=iso(5), date_to=iso(15))

    assert set(ids(page)) == {created[5]["id"], created[10]["id"], created[15]["id"]}
    assert page["total"] == 3


async def test_filter_by_date_from_only(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    await create_transaction(auth_headers, category["id"], date=iso(1))
    late = await create_transaction(auth_headers, category["id"], date=iso(20))

    page = await get_page(client, auth_headers, date_from=iso(10))

    assert ids(page) == [late["id"]]


async def test_filters_combined(
    client, auth_headers, create_category, create_transaction
):
    cat_a = await create_category(auth_headers, "A")
    cat_b = await create_category(auth_headers, "B")
    target = await create_transaction(
        auth_headers, cat_a["id"], type="expense", date=iso(10)
    )
    await create_transaction(auth_headers, cat_a["id"], type="income", date=iso(10))
    await create_transaction(auth_headers, cat_b["id"], type="expense", date=iso(10))
    await create_transaction(auth_headers, cat_a["id"], type="expense", date=iso(20))
    await create_transaction(auth_headers, cat_a["id"], type="expense", date=iso(1))

    page = await get_page(
        client,
        auth_headers,
        type="expense",
        category_id=cat_a["id"],
        date_from=iso(5),
        date_to=iso(15),
    )

    assert ids(page) == [target["id"]]
    assert page["total"] == 1


# --- Пагинация ---


@pytest.mark.parametrize(("offset", "expected_len"), [(0, 2), (2, 2), (4, 1), (10, 0)])
async def test_pagination_pages(
    client, auth_headers, create_category, create_transaction, offset, expected_len
):
    category = await create_category(auth_headers)
    for day in range(1, 6):
        await create_transaction(auth_headers, category["id"], date=iso(day))

    page = await get_page(client, auth_headers, limit=2, offset=offset)

    assert len(page["items"]) == expected_len
    assert page["total"] == 5
    assert page["limit"] == 2
    assert page["offset"] == offset


async def test_order_newest_first(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    old = await create_transaction(auth_headers, category["id"], date=iso(3))
    newest = await create_transaction(auth_headers, category["id"], date=iso(10))
    middle = await create_transaction(auth_headers, category["id"], date=iso(7))

    page = await get_page(client, auth_headers)

    assert ids(page) == [newest["id"], middle["id"], old["id"]]


async def test_same_date_bigger_id_first(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    created = [
        await create_transaction(auth_headers, category["id"], date=iso(5))
        for _ in range(3)
    ]

    page = await get_page(client, auth_headers)

    assert ids(page) == sorted((t["id"] for t in created), reverse=True)


async def test_pages_do_not_overlap(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    created = [
        await create_transaction(auth_headers, category["id"], date=iso(5))
        for _ in range(5)
    ]

    seen: list[int] = []
    for offset in (0, 2, 4):
        page = await get_page(client, auth_headers, limit=2, offset=offset)
        seen += ids(page)

    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == {t["id"] for t in created}


async def test_total_respects_filters(
    client, auth_headers, create_category, create_transaction
):
    category = await create_category(auth_headers)
    for _ in range(3):
        await create_transaction(auth_headers, category["id"], type="expense")
    for _ in range(2):
        await create_transaction(auth_headers, category["id"], type="income")

    page = await get_page(client, auth_headers, type="expense", limit=1)

    assert len(page["items"]) == 1
    assert page["total"] == 3


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"limit": 0}, id="limit-zero"),
        pytest.param({"limit": 101}, id="limit-too-big"),
        pytest.param({"offset": -1}, id="negative-offset"),
        pytest.param({"type": "transfer"}, id="unknown-type"),
        pytest.param(
            {"date_from": iso(10), "date_to": iso(5)}, id="from-later-than-to"
        ),
        pytest.param({"date_from": "2026-11-05T12:00:00"}, id="date-without-timezone"),
    ],
)
async def test_list_invalid_params(client, auth_headers, params):
    response = await client.get("/transactions", params=params, headers=auth_headers)

    assert response.status_code == 422


# --- Права доступа ---


async def test_user_sees_only_own_transactions(
    client,
    auth_headers,
    other_auth_headers,
    create_category,
    create_transaction,
):
    category = await create_category(auth_headers)
    other_category = await create_category(other_auth_headers)
    await create_transaction(auth_headers, category["id"])
    await create_transaction(auth_headers, category["id"])
    mine_b = await create_transaction(other_auth_headers, other_category["id"])

    page_a = await get_page(client, auth_headers)
    page_b = await get_page(client, other_auth_headers)

    assert page_a["total"] == 2
    assert page_b["total"] == 1
    assert ids(page_b) == [mine_b["id"]]


async def test_filter_by_foreign_category_returns_empty(
    client,
    auth_headers,
    other_auth_headers,
    create_category,
    create_transaction,
):
    category = await create_category(auth_headers)
    await create_transaction(auth_headers, category["id"])

    page = await get_page(client, other_auth_headers, category_id=category["id"])

    assert page["items"] == []
    assert page["total"] == 0


async def test_list_requires_auth(client):
    response = await client.get("/transactions")

    assert response.status_code == 401
