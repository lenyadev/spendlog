from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from spendlog.budget import month_bounds

NOON = timedelta(hours=12)


async def add_transaction(
    client,
    headers,
    category_id: int,
    amount: str,
    at: datetime,
    type_: str = "expense",
) -> None:
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
    assert response.status_code == 201


def current_bounds() -> tuple[datetime, datetime]:
    return month_bounds(datetime.now(UTC).date())


async def post_limit(client, headers, month: str, amount: str):
    return await client.post(
        "/limits", json={"month": month, "amount": amount}, headers=headers
    )


async def get_usage(client, headers) -> dict:
    response = await client.get("/limits/current", headers=headers)
    assert response.status_code == 200
    return response.json()


# --- GET /limits/current: расчёт ---


async def test_current_usage_without_limit(
    client,
    auth_headers,
    create_category,
):
    start, _ = current_bounds()
    category = await create_category(auth_headers)
    await add_transaction(client, auth_headers, category["id"], "40.00", start + NOON)

    body = await get_usage(client, auth_headers)

    assert body["month"] == start.date().isoformat()
    assert body["limit"] is None
    assert body["remaining"] is None
    assert body["percent_used"] is None
    assert Decimal(body["spent"]) == Decimal("40.00")


@pytest.mark.parametrize(
    ("limit", "expenses", "spent", "remaining", "percent"),
    [
        pytest.param(
            "1000.00",
            ["100.00", "150.00"],
            "250.00",
            "750.00",
            "25.00",
            id="partially-spent",
        ),
        pytest.param(
            "100.00", ["100.00"], "100.00", "0.00", "100.00", id="exactly-at-limit"
        ),
        pytest.param(
            "100.00", ["150.00"], "150.00", "-50.00", "150.00", id="over-limit"
        ),
        pytest.param("100.00", [], "0.00", "100.00", "0.00", id="no-expenses"),
    ],
)
async def test_current_usage_with_limit(
    client,
    auth_headers,
    create_category,
    limit,
    expenses,
    spent,
    remaining,
    percent,
):
    start, _ = current_bounds()
    category = await create_category(auth_headers)
    created = await post_limit(client, auth_headers, start.date().isoformat(), limit)
    assert created.status_code == 201
    for amount in expenses:
        await add_transaction(
            client, auth_headers, category["id"], amount, start + NOON
        )

    body = await get_usage(client, auth_headers)

    assert body["month"] == start.date().isoformat()
    assert Decimal(body["limit"]) == Decimal(limit)
    assert Decimal(body["spent"]) == Decimal(spent)
    assert Decimal(body["remaining"]) == Decimal(remaining)
    assert Decimal(body["percent_used"]) == Decimal(percent)


# --- GET /limits/current: что именно считается ---


async def test_incomes_are_ignored(client, auth_headers, create_category):
    start, _ = current_bounds()
    category = await create_category(auth_headers)
    await add_transaction(client, auth_headers, category["id"], "100.00", start + NOON)
    await add_transaction(
        client, auth_headers, category["id"], "500.00", start + NOON, type_="income"
    )

    body = await get_usage(client, auth_headers)

    assert Decimal(body["spent"]) == Decimal("100.00")


async def test_neighbor_months_are_ignored(client, auth_headers, create_category):
    start, end = current_bounds()
    prev_start, _ = month_bounds(start.date() - timedelta(days=1))
    category = await create_category(auth_headers)
    await add_transaction(
        client, auth_headers, category["id"], "70.00", prev_start + NOON
    )
    await add_transaction(client, auth_headers, category["id"], "80.00", end + NOON)
    await add_transaction(client, auth_headers, category["id"], "10.00", start + NOON)

    body = await get_usage(client, auth_headers)

    assert Decimal(body["spent"]) == Decimal("10.00")


async def test_month_borders(client, auth_headers, create_category):
    start, end = current_bounds()
    category = await create_category(auth_headers)
    # ровно первый момент месяца: считается
    await add_transaction(client, auth_headers, category["id"], "20.00", start)
    # последний микросекундный момент месяца: считается
    await add_transaction(
        client, auth_headers, category["id"], "5.00", end - timedelta(microseconds=1)
    )
    # ровно первый момент следующего месяца: не считается
    await add_transaction(client, auth_headers, category["id"], "30.00", end)

    body = await get_usage(client, auth_headers)

    assert Decimal(body["spent"]) == Decimal("25.00")


async def test_other_users_expenses_are_not_counted(
    client, auth_headers, other_auth_headers, create_category
):
    start, _ = current_bounds()
    category_a = await create_category(auth_headers)
    category_b = await create_category(other_auth_headers)
    await add_transaction(
        client, auth_headers, category_a["id"], "100.00", start + NOON
    )
    await add_transaction(
        client, other_auth_headers, category_b["id"], "30.00", start + NOON
    )

    body_a = await get_usage(client, auth_headers)
    body_b = await get_usage(client, other_auth_headers)

    assert Decimal(body_a["spent"]) == Decimal("100.00")
    assert Decimal(body_b["spent"]) == Decimal("30.00")


async def test_limit_of_another_month_is_not_used(client, auth_headers):
    start, end = current_bounds()
    prev_start, _ = month_bounds(start.date() - timedelta(days=1))
    for month in (prev_start.date(), end.date()):
        created = await post_limit(client, auth_headers, month.isoformat(), "999.00")
        assert created.status_code == 201

    body = await get_usage(client, auth_headers)

    assert body["limit"] is None
    assert body["remaining"] is None


# --- POST и PUT /limits ---


async def test_create_limit_normalizes_month(client, auth_headers):
    response = await post_limit(client, auth_headers, "2026-11-17", "500.00")

    assert response.status_code == 201
    body = response.json()
    assert body["month"] == "2026-11-01"
    assert Decimal(body["amount"]) == Decimal("500.00")
    assert "id" in body


@pytest.mark.parametrize("second_date", ["2026-11-01", "2026-11-30"])
async def test_duplicate_month_returns_409(client, auth_headers, second_date):
    first = await post_limit(client, auth_headers, "2026-11-17", "500.00")
    second = await post_limit(client, auth_headers, second_date, "700.00")

    assert first.status_code == 201
    assert second.status_code == 409


async def test_put_changes_amount(client, auth_headers):
    start, _ = current_bounds()
    month = start.date().isoformat()
    await post_limit(client, auth_headers, month, "500.00")

    response = await client.put(
        "/limits",
        json={
            "month": (start + timedelta(days=19)).date().isoformat(),
            "amount": "800.00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["month"] == month
    assert Decimal(response.json()["amount"]) == Decimal("800.00")
    usage = await get_usage(client, auth_headers)
    assert Decimal(usage["limit"]) == Decimal("800.00")


async def test_put_missing_month_returns_404(client, auth_headers):
    response = await client.put(
        "/limits",
        json={"month": "2030-01-01", "amount": "100.00"},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"month": "2026-11-01", "amount": "0"}, id="amount-zero"),
        pytest.param({"month": "2026-11-01", "amount": "-1"}, id="amount-negative"),
        pytest.param(
            {"month": "2026-11-01", "amount": "10.123"}, id="amount-three-decimals"
        ),
        pytest.param(
            {"month": "not-a-date", "amount": "100.00"}, id="month-not-a-date"
        ),
        pytest.param(
            {"month": "2026-13-01", "amount": "100.00"}, id="month-impossible"
        ),
        pytest.param({"amount": "100.00"}, id="month-missing"),
    ],
)
async def test_limit_invalid_data(client, auth_headers, method, payload):
    response = await client.request(
        method, "/limits", json=payload, headers=auth_headers
    )

    assert response.status_code == 422


async def test_limits_are_isolated_between_users(
    client, auth_headers, other_auth_headers
):
    start, _ = current_bounds()
    month = start.date().isoformat()
    a = await post_limit(client, auth_headers, month, "500.00")
    assert a.status_code == 201

    # B не может изменить лимит A: у B на этот месяц лимита нет
    put_b = await client.put(
        "/limits", json={"month": month, "amount": "1.00"}, headers=other_auth_headers
    )
    assert put_b.status_code == 404
    assert (await get_usage(client, other_auth_headers))["limit"] is None
    assert Decimal((await get_usage(client, auth_headers))["limit"]) == Decimal(
        "500.00"
    )

    # на тот же месяц у B свой лимит создаётся
    b = await post_limit(client, other_auth_headers, month, "700.00")
    assert b.status_code == 201
    assert Decimal((await get_usage(client, auth_headers))["limit"]) == Decimal(
        "500.00"
    )
    assert Decimal((await get_usage(client, other_auth_headers))["limit"]) == Decimal(
        "700.00"
    )


@pytest.mark.parametrize(
    ("method", "url"),
    [("POST", "/limits"), ("PUT", "/limits"), ("GET", "/limits/current")],
)
async def test_limits_require_auth(client, method, url):
    response = await client.request(
        method, url, json={"month": "2026-11-01", "amount": "100.00"}
    )

    assert response.status_code == 401
