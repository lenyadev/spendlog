from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from spendlog.models.base import Base, TimestampMixin


class MonthlyLimit(Base, TimestampMixin):
    __tablename__ = "monthly_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column()
    month: Mapped[date] = mapped_column(Date())
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
