from sqlalchemy import text


async def test_session_uses_test_database(session):
    name = await session.scalar(text("SELECT current_database()"))
    assert name == "spendlog_test"
