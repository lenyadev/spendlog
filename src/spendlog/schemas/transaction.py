from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

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
