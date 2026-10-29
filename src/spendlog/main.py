from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from spendlog.session import SessionDep
from spendlog.settings import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
    }


@app.get("/health/db", tags=["health"])
async def health_check_db(session: SessionDep) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"database": "ok"}
