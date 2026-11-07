from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LimitBase(BaseModel):
    month: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @field_validator("month")
    @classmethod
    def normalize_month(cls, value: date) -> date:
        return value.replace(day=1)


class LimitCreate(LimitBase):
    pass


class LimitUpdate(LimitBase):
    pass


class LimitRead(LimitBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class LimitUsage(BaseModel):
    month: date
    limit: Decimal | None
    spent: Decimal
    remaining: Decimal | None
    percent_used: Decimal | None
