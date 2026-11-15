async def test_from_allowed_origin(client):
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_from_unknown_origin(client):
    response = await client.options(
        "/health",
        headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


async def test_regular_request_from_allowed_origin(client):
    response = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def tests_regular_request_from_unknown_origin(client):
    response = await client.get("/health", headers={"Origin": "https://evil.com"})
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_allow_headers(client):
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
