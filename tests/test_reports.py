from datetime import UTC, datetime
from decimal import Decimal

import pytest


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


async def test_multiple_categories_ordered(
    auth_headers, create_category, create_transaction, client
):
    food = await create_category(auth_headers, "Food")
    rent = await create_category(auth_headers, "Rent")
    fun = await create_category(auth_headers, "Fun")
    await create_transaction(
        auth_headers,
        food["id"],
        "100.00",
        datetime(2024, 11, 5, 12, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        food["id"],
        "50.00",
        datetime(2024, 11, 6, 12, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        rent["id"],
        "500.00",
        datetime(2024, 11, 7, 12, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        fun["id"],
        "30.00",
        datetime(2024, 11, 8, 12, tzinfo=UTC).isoformat(),
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    ids = sorted(item["category_id"] for item in body["items"])
    assert ids == [food["id"], rent["id"], fun["id"]]
    totals = {item["category_id"]: Decimal(item["total"]) for item in body["items"]}
    assert totals[food["id"]] == Decimal("150.00")
    assert totals[rent["id"]] == Decimal("500.00")
    assert totals[fun["id"]] == Decimal("30.00")
    assert Decimal(body["total"]) == Decimal("680.00")


async def test_default_both_types(
    auth_headers, create_category, create_transaction, client
):
    food = await create_category(auth_headers, "Food")
    salary = await create_category(auth_headers, "Salary")
    await create_transaction(
        auth_headers,
        food["id"],
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
        type="expense",
    )
    await create_transaction(
        auth_headers,
        salary["id"],
        "3000.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
        type="income",
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    assert Decimal(body["total"]) == Decimal("3100.00")
    totals = {item["category_id"]: Decimal(item["total"]) for item in body["items"]}
    assert totals == {food["id"]: Decimal("100.00"), salary["id"]: Decimal("3000.00")}


async def test_explicit_expense_only(
    auth_headers, create_category, create_transaction, client
):
    food = await create_category(auth_headers, "Food")
    salary = await create_category(auth_headers, "Salary")
    await create_transaction(
        auth_headers,
        food["id"],
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
        type="expense",
    )
    await create_transaction(
        auth_headers,
        salary["id"],
        "3000.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
        type="income",
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
    assert [item["category_id"] for item in body["items"]] == [food["id"]]


async def test_income_only(auth_headers, create_category, create_transaction, client):
    food = await create_category(auth_headers, "Food")
    salary = await create_category(auth_headers, "Salary")
    await create_transaction(
        auth_headers,
        food["id"],
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
        type="expense",
    )
    await create_transaction(
        auth_headers,
        salary["id"],
        "3000.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
        type="income",
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
    assert body["items"][0]["category_id"] == salary["id"]


async def test_period_boundaries(
    auth_headers, create_category, create_transaction, client
):
    food = await create_category(auth_headers, "Food")
    await create_transaction(
        auth_headers,
        food["id"],
        "10.00",
        datetime(2024, 11, 4, 23, 59, 59, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        food["id"],
        "20.00",
        datetime(2024, 11, 5, 0, 0, 0, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        food["id"],
        "30.00",
        datetime(2024, 11, 7, 12, 0, 0, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        food["id"],
        "40.00",
        datetime(2024, 11, 10, 23, 59, 59, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        food["id"],
        "50.00",
        datetime(2024, 11, 11, 0, 0, 0, tzinfo=UTC).isoformat(),
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-05", date_to="2024-11-10"
    )
    body = response.json()
    assert Decimal(body["total"]) == Decimal("90.00")


async def test_empty_category_excluded(
    auth_headers, create_category, create_transaction, client
):
    food = await create_category(auth_headers, "Food")
    unused = await create_category(auth_headers, "Unused")
    await create_transaction(
        auth_headers,
        food["id"],
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    ids = [item["category_id"] for item in body["items"]]
    assert unused["id"] not in ids
    assert food["id"] in ids


async def test_other_user_isolated(
    auth_headers, other_auth_headers, create_category, create_transaction, client
):
    my_cat = await create_category(auth_headers, "Mine")
    other_cat = await create_category(other_auth_headers, "Theirs")
    await create_transaction(
        auth_headers,
        my_cat["id"],
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        other_auth_headers,
        other_cat["id"],
        "999.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
    )

    response = await _get_report(
        client, auth_headers, date_from="2024-11-01", date_to="2024-11-30"
    )
    body = response.json()
    ids = [item["category_id"] for item in body["items"]]
    assert ids == [my_cat["id"]]
    assert Decimal(body["total"]) == Decimal("100.00")


async def test_matches_transactions_list(
    auth_headers, create_category, create_transaction, client
):
    food = await create_category(auth_headers, "Food")
    rent = await create_category(auth_headers, "Rent")
    await create_transaction(
        auth_headers,
        food["id"],
        "100.00",
        datetime(2024, 11, 5, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        food["id"],
        "50.00",
        datetime(2024, 11, 6, tzinfo=UTC).isoformat(),
    )
    await create_transaction(
        auth_headers,
        rent["id"],
        "500.00",
        datetime(2024, 11, 7, tzinfo=UTC).isoformat(),
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
