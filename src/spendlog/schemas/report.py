from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, model_validator

from spendlog.schemas.transaction import TransactionType


class ReportFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    type: TransactionType | None = None

    @model_validator(mode="after")
    def verify_date(self) -> Self:
        if (self.date_from and self.date_to) and (self.date_from > self.date_to):
            raise ValueError("date_from must not be later than date_to")
        return self


class CategoryTotal(BaseModel):
    category_id: int
    category_name: str
    total: Decimal


class CategoryReport(BaseModel):
    items: list[CategoryTotal]
    total: Decimal
