import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

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
        response = await call_next(request)
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
