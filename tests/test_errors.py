import uuid

import httpx
import pytest
from fastapi import APIRouter

from spendlog.main import app


@pytest.fixture
def boom_route():

    router = APIRouter()
    count = len(app.router.routes)

    @router.get("/boom")
    async def boom_endpoint():
        raise RuntimeError("boom")

    app.include_router(router)

    yield
    del app.router.routes[count:]


async def test_error_handling(boom_route, logs):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "boom" not in response.text
    message = next(m for m in logs if m.record["extra"].get("path") == "/boom")
    extra = message.record["extra"]
    assert extra["status_code"] == 500
    uuid.UUID(extra["request_id"])  # UUID запроса должно парситься через UUID
    assert message.record["level"].name == "ERROR"
