from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from spendlog.models.base import Base, TimestampMixin


class MonthlyLimit(Base, TimestampMixin):
    __tablename__ = "monthly_limits"
    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_monthly_limits_user_id_month"),
        CheckConstraint("amount > 0", name="ck_monthly_limits_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    month: Mapped[date] = mapped_column(Date())
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
