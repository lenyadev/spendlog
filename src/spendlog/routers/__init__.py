from spendlog.routers.auth import router as auth_router
from spendlog.routers.categories import router as categories_router

all_routers = [auth_router, categories_router]

__all__ = ["all_routers"]
