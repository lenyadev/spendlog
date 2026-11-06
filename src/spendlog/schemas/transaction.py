from decimal import Decimal
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from spendlog.models.transaction import TransactionType


class TransactionBase(BaseModel):
    type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    date: AwareDatetime
    category_id: int
    comment: str | None = Field(default=None, max_length=255)


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(TransactionBase):
    pass


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TransactionFilters(BaseModel):
    type: TransactionType | None = None
    category_id: int | None = None
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def verify_date(self) -> Self:
        if (self.date_from and self.date_to) and (self.date_from > self.date_to):
            raise ValueError("date_from must not be later than date_to")
        return self


class TransactionPage(BaseModel):
    items: list[TransactionRead]
    total: int
    limit: int
    offset: int
