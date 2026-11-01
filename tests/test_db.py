from sqlalchemy import func, select, text

from spendlog.models import User


async def test_schema_created(test_engine):
    async with test_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        names = {row[0] for row in result}
    assert {"users", "categories", "transactions", "monthly_limits"} <= names


async def test_insert_user(session):
    session.add(User(email="a@test.com", password_hash="a"))
    await session.commit()

    count = await session.scalar(select(func.count()).select_from(User))
    assert count == 1


async def test_db_is_clean_after_previous_test(session):
    count = await session.scalar(select(func.count()).select_from(User))
    assert count == 0


async def test_health_db_uses_test_db(client):
    response = await client.get("/health/db")
    assert response.status_code == 200
