from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from spendlog.budget import calc_usage, month_bounds
from spendlog.crud import limit as limit_crud
from spendlog.crud import transaction as transaction_crud
from spendlog.dependencies import CurrentUserDep, SessionDep
from spendlog.models import MonthlyLimit
from spendlog.schemas.limit import LimitCreate, LimitRead, LimitUpdate, LimitUsage

router = APIRouter(prefix="/limits", tags=["limits"])


@router.get("/current", response_model=LimitUsage)
async def get_current_usage(user: CurrentUserDep, session: SessionDep) -> LimitUsage:
    today = datetime.now(
        UTC
    ).date()  # границы месяца в UTC, часовой пояс пользователя не учитывается
    month = today.replace(day=1)
    start, end = month_bounds(today)

    limit = await limit_crud.get_by_month(session, user.id, month)
    spent = await transaction_crud.sum_expenses(session, user.id, start, end)

    limit_amount = limit.amount if limit is not None else None
    remaining, percent_used = calc_usage(limit_amount, spent)
    return LimitUsage(
        month=month,
        limit=limit_amount,
        spent=spent,
        remaining=remaining,
        percent_used=percent_used,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LimitRead)
async def create_limit(
    data: LimitCreate, user: CurrentUserDep, session: SessionDep
) -> MonthlyLimit:
    try:
        return await limit_crud.create(session, user.id, data.month, data.amount)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Limit for this month already exists"
        ) from None


@router.put("", response_model=LimitRead)
async def update_limit(
    data: LimitUpdate, user: CurrentUserDep, session: SessionDep
) -> MonthlyLimit:
    limit = await limit_crud.get_by_month(session, user.id, data.month)
    if limit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Limit not found")
    return await limit_crud.update(session, limit, data.amount)
