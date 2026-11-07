from spendlog.main import app


def test_routers_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    assert "/categories" in paths
    assert "/categories/{category_id}" in paths
    assert "/transactions/{transaction_id}" in paths
    assert "/transactions" in paths
    assert "/reports/categories" in paths
