from fastapi.testclient import TestClient

from spendlog.core.config import get_settings
from spendlog.main import app

client = TestClient(app)
settings = get_settings()

def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": settings.app_env}
