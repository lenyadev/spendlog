from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from spendlog.dependencies import SessionDep
from spendlog.routers import all_routers
from spendlog.settings import get_settings
from spendlog.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(settings.log_level)
app = FastAPI(title=settings.app_name, version=settings.app_version)

for router in all_routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    logger.debug("x")
    logger.error("y")
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
