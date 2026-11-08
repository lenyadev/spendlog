import uuid


async def test_health(client, logs):
    await client.get("/health")
    message = next(m for m in logs if m.record["extra"].get("path") == "/health")
    extra = message.record["extra"]
    assert extra["status_code"] == 200
    uuid.UUID(extra["request_id"])  # UUID запроса должно парситься через UUID
    assert message.record["level"].name == "DEBUG"


async def test_404_page(client, logs):
    await client.get("/no-such-route")
    message = next(m for m in logs if m.record["extra"].get("path") == "/no-such-route")
    extra = message.record["extra"]
    assert extra["status_code"] == 404
    uuid.UUID(extra["request_id"])  # UUID запроса должно парситься через UUID
    assert message.record["level"].name == "INFO"
