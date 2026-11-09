import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from spendlog.logging_config import setup_logging
from spendlog.routers import all_routers
from spendlog.settings import get_settings

settings = get_settings()
logger = setup_logging(settings.log_level)
app = FastAPI(title=settings.app_name, version=settings.app_version)

for router in all_routers:
    app.include_router(router)


@app.middleware("http")
async def logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = str(uuid.uuid4())
    with logger.contextualize(request_id=request_id):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.bind(
                duration_ms=duration_ms,
                method=request.method,
                path=request.url.path,
                status_code=500,
            ).exception("Request failed")
            raise
        is_health = request.url.path.startswith("/health")
        level = "DEBUG" if is_health and response.status_code < 400 else "INFO"
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        ).log(level, "Request completed")

    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
