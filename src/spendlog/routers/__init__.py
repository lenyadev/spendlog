from spendlog.routers.auth import router as auth_router
from spendlog.routers.categories import router as categories_router
from spendlog.routers.limits import router as limits_router
from spendlog.routers.reports import router as reports_router
from spendlog.routers.transactions import router as transactions_router

all_routers = [
    auth_router,
    categories_router,
    transactions_router,
    limits_router,
    reports_router,
]

__all__ = ["all_routers"]
