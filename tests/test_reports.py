from datetime import UTC, datetime
from decimal import Decimal

import pytest

UTC = UTC


async def _create_category(client, headers, name="Food"):
    response = await client.post("/categories", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_transaction(
    client, headers, category_id, amount, at, type_="expense"
):
    response = await client.post(
        "/transactions",
        json={
            "type": type_,
            "amount": amount,
            "date": at.isoformat(),
            "category_id": category_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _get_report(client, headers, **params):
    return await client.get("/reports/categories", params=params, headers=headers)


async def test_empty_period(client, auth_headers):
    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert Decimal(body["total"]) == Decimal("0")


async def test_multiple_categories_ordered(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    rent = await _create_category(client, auth_headers, "Rent")
    fun = await _create_category(client, auth_headers, "Fun")
    await _create_transaction(
        client, auth_headers, food, "100.00", datetime(2024, 11, 5, 12, tzinfo=UTC)
    )
    await _create_transaction(
        client, auth_headers, food, "50.00", datetime(2024, 11, 6, 12, tzinfo=UTC)
    )
    await _create_transaction(
        client, auth_headers, rent, "500.00", datetime(2024, 11, 7, 12, tzinfo=UTC)
    )
    await _create_transaction(
        client, auth_headers, fun, "30.00", datetime(2024, 11, 8, 12, tzinfo=UTC)
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    ids = [item["category_id"] for item in body["items"]]
    assert ids == [rent, food, fun]
    totals = {item["category_id"]: Decimal(item["total"]) for item in body["items"]}
    assert totals[food] == Decimal("150.00")
    assert totals[rent] == Decimal("500.00")
    assert totals[fun] == Decimal("30.00")
    assert Decimal(body["total"]) == Decimal("680.00")


async def test_default_both_types(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    salary = await _create_category(client, auth_headers, "Salary")
    await _create_transaction(
        client,
        auth_headers,
        food,
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC),
        type_="expense",
    )
    await _create_transaction(
        client,
        auth_headers,
        salary,
        "3000.00",
        datetime(2024, 11, 5, tzinfo=UTC),
        type_="income",
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    assert Decimal(body["total"]) == Decimal("3100.00")
    totals = {item["category_id"]: Decimal(item["total"]) for item in body["items"]}
    assert totals == {food: Decimal("100.00"), salary: Decimal("3000.00")}


async def test_explicit_expense_only(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    salary = await _create_category(client, auth_headers, "Salary")
    await _create_transaction(
        client,
        auth_headers,
        food,
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC),
        type_="expense",
    )
    await _create_transaction(
        client,
        auth_headers,
        salary,
        "3000.00",
        datetime(2024, 11, 5, tzinfo=UTC),
        type_="income",
    )

    response = await _get_report(
        client,
        auth_headers,
        date_from="2024-11-01",
        date_to="2024-11-30",
        type="expense",
    )
    body = response.json()
    assert Decimal(body["total"]) == Decimal("100.00")
    assert [item["category_id"] for item in body["items"]] == [food]


async def test_income_only(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    salary = await _create_category(client, auth_headers, "Salary")
    await _create_transaction(
        client,
        auth_headers,
        food,
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC),
        type_="expense",
    )
    await _create_transaction(
        client,
        auth_headers,
        salary,
        "3000.00",
        datetime(2024, 11, 5, tzinfo=UTC),
        type_="income",
    )

    response = await _get_report(
        client,
        auth_headers,
        date_from="2024-11-01",
        date_to="2024-11-30",
        type="income",
    )
    body = response.json()
    assert Decimal(body["total"]) == Decimal("3000.00")
    assert len(body["items"]) == 1
    assert body["items"][0]["category_id"] == salary


async def test_period_boundaries(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    await _create_transaction(
        client,
        auth_headers,
        food,
        "10.00",
        datetime(2024, 11, 4, 23, 59, 59, tzinfo=UTC),
    )
    await _create_transaction(
        client, auth_headers, food, "20.00", datetime(2024, 11, 5, 0, 0, 0, tzinfo=UTC)
    )
    await _create_transaction(
        client, auth_headers, food, "30.00", datetime(2024, 11, 7, 12, 0, 0, tzinfo=UTC)
    )
    await _create_transaction(
        client,
        auth_headers,
        food,
        "40.00",
        datetime(2024, 11, 10, 23, 59, 59, tzinfo=UTC),
    )
    await _create_transaction(
        client, auth_headers, food, "50.00", datetime(2024, 11, 11, 0, 0, 0, tzinfo=UTC)
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-05", date_to="2024-11-10"
    )
    body = response.json()
    assert Decimal(body["total"]) == Decimal("90.00")


async def test_empty_category_excluded(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    unused = await _create_category(client, auth_headers, "Unused")
    await _create_transaction(
        client, auth_headers, food, "100.00", datetime(2024, 11, 5, tzinfo=UTC)
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    ids = [item["category_id"] for item in body["items"]]
    assert unused not in ids
    assert food in ids


async def test_other_user_isolated(client, auth_headers, other_auth_headers):
    my_cat = await _create_category(client, auth_headers, "Mine")
    other_cat = await _create_category(client, other_auth_headers, "Theirs")
    await _create_transaction(
        client, auth_headers, my_cat, "100.00", datetime(2024, 11, 5, tzinfo=UTC)
    )
    await _create_transaction(
        client,
        other_auth_headers,
        other_cat,
        "999.00",
        datetime(2024, 11, 5, tzinfo=UTC),
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    ids = [item["category_id"] for item in body["items"]]
    assert ids == [my_cat]
    assert Decimal(body["total"]) == Decimal("100.00")


async def test_matches_transactions_list(client, auth_headers):
    food = await _create_category(client, auth_headers, "Food")
    rent = await _create_category(client, auth_headers, "Rent")
    await _create_transaction(
        client, auth_headers, food, "100.00", datetime(2024, 11, 5, tzinfo=UTC)
    )
    await _create_transaction(
        client, auth_headers, food, "50.00", datetime(2024, 11, 6, tzinfo=UTC)
    )
    await _create_transaction(
        client, auth_headers, rent, "500.00", datetime(2024, 11, 7, tzinfo=UTC)
    )

    tx_response = await client.get(
        "/transactions",
        params={
            "limit": 100,
            "type": "expense",
            "date_from": "2024-11-01T00:00:00Z",
            "date_to": "2024-11-30T23:59:59Z",
        },
        headers=auth_headers,
    )
    assert tx_response.status_code == 200, tx_response.text
    tx_by_cat: dict[int, Decimal] = {}
    for tx in tx_response.json()["items"]:
        cid = tx["category_id"]
        tx_by_cat[cid] = tx_by_cat.get(cid, Decimal("0")) + Decimal(tx["amount"])

    report_response = await _get_report(
        client,
        auth_headers,
        date_from="2024-11-01",
        date_to="2024-11-30",
        type="expense",
    )
    report_by_cat = {
        item["category_id"]: Decimal(item["total"])
        for item in report_response.json()["items"]
    }
    assert report_by_cat == tx_by_cat


@pytest.mark.parametrize(
    "params",
    [
        {"date_from": "2024-11-10", "date_to": "2024-11-05"},
        {"date_from": "2024-11-01", "date_to": "2024-11-30", "type": "transfer"},
        {"date_from": "not-a-date", "date_to": "2024-11-30"},
    ],
)
async def test_invalid_params(client, auth_headers, params):
    response = await _get_report(client, auth_headers, **params)
    assert response.status_code == 422


async def test_unauthorized(client):
    response = await client.get(
        "/reports/categories",
        params={"date_from": "2024-11-01", "date_to": "2024-11-30"},
    )
    assert response.status_code == 401
