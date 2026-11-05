from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from spendlog.models import Transaction, User
from spendlog.models.transaction import TransactionType

# --- CRUD ---


async def test_list_categories_sorted_by_name(client, auth_headers, create_category):
    await create_category(auth_headers, "Transport")
    await create_category(auth_headers, "Food")

    response = await client.get("/categories", headers=auth_headers)

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Food", "Transport"]


async def test_get_update_delete_category(client, auth_headers, create_category):
    category = await create_category(auth_headers, "Food")
    url = f"/categories/{category['id']}"

    get = await client.get(url, headers=auth_headers)
    assert get.status_code == 200
    assert get.json()["name"] == "Food"

    put = await client.put(url, json={"name": "Groceries"}, headers=auth_headers)
    assert put.status_code == 200
    assert put.json()["name"] == "Groceries"

    delete = await client.delete(url, headers=auth_headers)
    assert delete.status_code == 204

    after = await client.get(url, headers=auth_headers)
    assert after.status_code == 404


@pytest.mark.parametrize("name", ["", "   ", "a" * 101])
async def test_create_category_invalid_name(client, auth_headers, name):
    response = await client.post(
        "/categories", json={"name": name}, headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/categories"),
        ("POST", "/categories"),
        ("GET", "/categories/1"),
        ("PUT", "/categories/1"),
        ("DELETE", "/categories/1"),
    ],
)
async def test_categories_require_auth(client, method, url):
    response = await client.request(method, url, json={"name": "Food"})
    assert response.status_code == 401


# --- Изоляция пользователей ---


async def test_user_does_not_see_other_users_categories(
    client, auth_headers, other_auth_headers, create_category
):
    await create_category(auth_headers, "Food")

    response = await client.get("/categories", headers=other_auth_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_other_user_gets_404_on_foreign_category(
    client, auth_headers, other_auth_headers, create_category
):
    category = await create_category(auth_headers, "Food")
    url = f"/categories/{category['id']}"

    get = await client.get(url, headers=other_auth_headers)
    put = await client.put(url, json={"name": "Hacked"}, headers=other_auth_headers)
    delete = await client.delete(url, headers=other_auth_headers)

    assert get.status_code == 404
    assert put.status_code == 404
    assert delete.status_code == 404

    own = await client.get(url, headers=auth_headers)
    assert own.status_code == 200
    assert own.json()["name"] == "Food"


async def test_same_name_for_different_users(client, auth_headers, other_auth_headers):
    first = await client.post(
        "/categories", json={"name": "Food"}, headers=auth_headers
    )
    second = await client.post(
        "/categories", json={"name": "Food"}, headers=other_auth_headers
    )

    assert first.status_code == 201
    assert second.status_code == 201


# --- Дубли и ограничения ---


async def test_duplicate_name_same_user(client, auth_headers, create_category):
    await create_category(auth_headers, "Food")

    response = await client.post(
        "/categories", json={"name": "Food"}, headers=auth_headers
    )
    assert response.status_code == 409

    listing = await client.get("/categories", headers=auth_headers)
    assert len(listing.json()) == 1


async def test_rename_to_existing_name(client, auth_headers, create_category):
    await create_category(auth_headers, "Food")
    transport = await create_category(auth_headers, "Transport")

    response = await client.put(
        f"/categories/{transport['id']}",
        json={"name": "Food"},
        headers=auth_headers,
    )
    assert response.status_code == 409

    listing = await client.get("/categories", headers=auth_headers)
    assert [c["name"] for c in listing.json()] == ["Food", "Transport"]


async def test_delete_category_with_transactions(
    client, auth_headers, session, user_credentials, create_category
):
    category = await create_category(auth_headers, "Food")
    user = await session.scalar(
        select(User).where(User.email == user_credentials["email"])
    )
    assert user is not None
    session.add(
        Transaction(
            user_id=user.id,
            category_id=category["id"],
            type=TransactionType.expense,
            amount=Decimal("10.00"),
            date=datetime.now(UTC),
        )
    )
    await session.commit()

    response = await client.delete(
        f"/categories/{category['id']}", headers=auth_headers
    )
    assert response.status_code == 409

    still_there = await client.get(
        f"/categories/{category['id']}", headers=auth_headers
    )
    assert still_there.status_code == 200
