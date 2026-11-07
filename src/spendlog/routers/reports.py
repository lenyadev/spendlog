from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query

from spendlog.crud import report as report_crud
from spendlog.dependencies import CurrentUserDep, SessionDep
from spendlog.schemas.report import CategoryReport, CategoryTotal, ReportFilters

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/categories", response_model=CategoryReport)
async def get_categories_report(
    session: SessionDep,
    user: CurrentUserDep,
    filters: Annotated[ReportFilters, Query()],
) -> CategoryReport:
    rows = await report_crud.totals_by_category(session, user.id, filters)
    items = [
        CategoryTotal(
            category_id=row.id,
            category_name=row.name,
            total=row.total,
        )
        for row in rows
    ]
    total = sum((item.total for item in items), Decimal("0.00"))
    return CategoryReport(items=items, total=total)
