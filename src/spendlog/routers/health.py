from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from spendlog.dependencies import SessionDep
from spendlog.settings import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.app_env,
    }


@router.get("/db")
async def health_check_db(session: SessionDep) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return {"database": "ok"}
