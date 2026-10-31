from datetime import datetime
from decimal import Decimal
from enum import Enum as EnumType

from sqlalchemy import DateTime, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from spendlog.models.base import Base, TimestampMixin


class TransactionType(EnumType):
    expense = "expense"
    income = "income"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column()
    category_id: Mapped[int] = mapped_column()
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
