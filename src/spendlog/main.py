from fastapi import FastAPI

from spendlog.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Spendlog API",
    version="0.1.0"
)

@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
    }