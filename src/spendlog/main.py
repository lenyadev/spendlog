from fastapi import FastAPI

from spendlog.settings import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}