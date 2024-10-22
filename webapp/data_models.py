from datetime import date
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from uuid import uuid4
from pytz import timezone

from pydantic import BaseModel, field_serializer, field_validator, model_validator
from pydantic import Field
from pydantic_settings import SettingsConfigDict

def et_datetime_now():
    eastern = timezone('US/Eastern')
    return datetime.now(tz=eastern)


def et_date_now():
    eastern = timezone('US/Eastern')
    return datetime.now(tz=eastern).date()


def et_date_due():
    eastern = timezone('US/Eastern')
    return datetime.now(tz=eastern).date().replace(day=1)


class WaterUsage(BaseModel):

    id: UUID = Field(default_factory=uuid4)
    watermeter_id: int = Field(nullable=False)
    previous_date: date = Field(default_factory=et_date_now)
    current_date: date = Field(default_factory=et_date_now)
    previous_reading: int = Field(default=0)
    current_reading: int = Field(default=0)
    statement_date: date = Field(default_factory=et_date_due)
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    @field_serializer('id')
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer('previous_date', 'current_date', 'statement_date', 'inserted_at')
    def serialize_date(self, v: date | datetime, _info):
        if isinstance(v, str):
            return v
        else:
            return v.isoformat()

    @model_validator(mode='after')
    def check_water(self):
        if self.current_reading < self.previous_reading:
            raise ValueError(
                'Current reading cannot be less than previous reading'
            )
        return self

    @property
    def water_usage(self):
        return self.current_reading - self.previous_reading

    def water_bill_dollar_amount(self, water_rate: float, service_fee: float):
        return round(self.water_usage * water_rate + service_fee, 2)


class Tenant(BaseModel):

    id: UUID = Field(default_factory=uuid4)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    account_id: UUID | None = Field(default=None)
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    @field_serializer('id', 'account_id')
    def serialize_uuid(self, v: UUID, _info):
        if v is not None:
            return str(v)
        else:
            return v

    @field_serializer('inserted_at')
    def serialize_date(self, v: date | datetime, _info):
        return v.isoformat()    


class Payment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    beneficiary_account_id: UUID
    amount: float = Field(nullable=False)
    payment_dated: date = Field(default_factory=et_date_now)
    payment_received: date = Field(default_factory=et_date_now)
    inserted_at: datetime = Field(default_factory=et_datetime_now)
    payer: Optional[str] = Field(default=None)
    amount_applied: float = Field(default=0)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @field_serializer('id', 'beneficiary_account_id')
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer('payment_dated', 'payment_received', 'inserted_at')
    def serialize_date(self, v: date | datetime, _info):
        return v.isoformat()


class ChargeTypes(str, Enum):
    LATEFEE = 'LATEFEE'
    WATER = 'WATER'
    STORAGE = 'STORAGE'
    RENT = 'RENT'
    OTHER = 'OTHER'


class InvoiceSetting(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    rent_monthly_rate: int = Field(default=475)
    water_monthly_rate: float = Field(default=0.011784)
    water_service_fee: float = Field(default=1.5)
    storage_monthly_rate: int = Field(default=84)
    late_fee_rate: float = Field(default=0.05)
    overdue_cutoff_days: int = Field(default=10)
    effective_as_of: date = Field(default_factory=et_date_now)
    inserted_at: date = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @field_serializer('id')
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer('effective_as_of', 'inserted_at')
    def serialize_date(self, v: date, _info):
        if isinstance(v, date):
            return v.isoformat()
        else:
            return v

    @field_validator(
        "rent_monthly_rate",
        "storage_monthly_rate",
        mode="before",
        check_fields=False
    )
    def coerce_and_round_up(cls, v):
        if isinstance(v, float):
            return round(v, 0)
        return v

    def increase_rates_by_percentage(
        self, percentage: float = 3.0
    ) -> "InvoiceSetting":
        increase_factor = 1 + (percentage / 100)
        return InvoiceSetting(
            rent_monthly_rate=self.rent_monthly_rate * increase_factor,
            water_monthly_rate=self.water_monthly_rate,
            water_service_fee=self.water_service_fee,
            storage_monthly_rate=self.storage_monthly_rate * increase_factor,
            late_fee_rate=self.late_fee_rate,
            overdue_cutoff_days=self.overdue_cutoff_days,
        )

    def set_attributes(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(
                    f"{key} is not a valid attribute of InvoiceSetting."
                )


class AccountsReceivable(BaseModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: UUID = Field(foreign_key='accounts.id', index=True)
    amount_due: float = Field(default=0)
    statement_date: date = Field(default_factory=et_date_now)
    charge_type: ChargeTypes = Field(default=ChargeTypes.RENT)
    paid: bool = Field(default=False)
    details: Optional[dict] = Field(default={})
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)
    
    @field_serializer('id', 'account_id')
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer('statement_date', 'inserted_at')
    def serialize_date(self, v: date | datetime, _info):
        return v.isoformat()

    @field_serializer('charge_type')
    def serialize_enum(self, charge_type: ChargeTypes, _info):
        return charge_type.value


class Property(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    property_code: str = Field(default="")
    street_address: str = Field(default='')
    city_state_zip: str = Field(default='')
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)


class InvoiceFileParse(BaseModel):
    A1: str = Field(default="", alias="business_name")
    A2: str = Field(default="", alias="business_address_1")
    A3: str = Field(default="", alias="business_address_2")
    A4: str = Field(default="", alias="business_contact_phone")
    A5: str = Field(default="", alias="business_contact_email")
    B7: str = Field(default="", alias="tenant_name")
    B8: str = Field(default="", alias="tenant_address_1")
    B9: str = Field(default="", alias="tenant_address_2")
    F3: date = Field(default_factory=et_date_now, alias="invoice_date")
    F4: str = Field(default="", alias="invoice_customer_id")
    F5: float = Field(default=0, alias="invoice_total_amount_due")
    F6: date = Field(default_factory=et_date_due, alias="invoice_due_date")
    A13: Optional[date] = Field(default_factory=None, alias="date_today_1")
    A14: Optional[date] = Field(default_factory=None, alias="date_today_2")
    A15: Optional[date] = Field(default_factory=None, alias="date_late")
    A16: Optional[date] = Field(default_factory=None, alias="date_rent")
    A17: Optional[date] = Field(default_factory=None, alias="date_water")
    A18: Optional[date] = Field(default_factory=None, alias="date_storage")
    A19: Optional[date] = Field(default_factory=None, alias="date_other_rent")
    A22: Optional[str] = Field(default=None, alias="detail_other_rent")
    C13: Optional[str] = Field(default=None, alias="desc_prev_month_paid")
    C14: Optional[str] = Field(default=None, alias="desc_prev_month_residual")
    C15: Optional[str] = Field(default=None, alias="desc_late_fee")
    C16: Optional[str] = Field(default=None, alias="desc_curr_rent")
    C17: Optional[str] = Field(default=None, alias="desc_curr_water")
    C18: Optional[str] = Field(default=None, alias="desc_curr_storage")
    C19: Optional[str] = Field(default=None, alias="desc_other_rent")
    C20: Optional[str] = Field(default=None, alias="desc_prev_overdue")
    F13: Optional[float] = Field(default=None, alias="amt_prev_month_paid")
    F14: Optional[float] = Field(default=None, alias="amt_prev_month_residual")
    F15: Optional[float] = Field(default=None, alias="amt_late_fee")
    F16: Optional[float] = Field(default=None, alias="amt_rent")
    F17: Optional[float] = Field(default=None, alias="amt_water")
    F18: Optional[float] = Field(default=None, alias="amt_storage")
    F19: Optional[float] = Field(default=None, alias="amt_other_rent")
    F20: Optional[float] = Field(default=None, alias="amt_overdue")
    F21: Optional[float] = Field(default=None, alias="amt_total_amount_due")
    A27: Optional[int] = Field(default=None, alias="water_meter_id")
    B26: Optional[date] = Field(default=None, alias="water_prev_date")
    B27: Optional[int] = Field(default=None, alias="water_prev_read")
    C26: Optional[date] = Field(default=None, alias="water_curr_date")
    C27: Optional[int] = Field(default=None, alias="water_curr_read")
    D27: Optional[int] = Field(default=None, alias="water_usage_period")
    E27: Optional[float] = Field(default=None, alias="water_bill_period")
    A37: str = Field(default="", alias="business_name_")
    A38: str = Field(default="", alias="business_address_1_")
    A39: str = Field(default="", alias="business_address_2_")
    A43: str = Field(default="", alias="business_contact_email_")
    F36: date = Field(default_factory=et_date_now, alias="invoice_date_")
    F37: str = Field(default="", alias="invoice_customer_id_")
    F39: date = Field(default_factory=et_date_due, alias="invoice_due_date_")
    F40: float = Field(default=0, alias="invoice_total_amount_due_")

    model_config = SettingsConfigDict(populate_by_name=True)


class BillPreference(str, Enum):
    NO_PAPER = 'NO_PAPER'
    NO_EMAIL = 'NO_EMAIL'
    NO_PREFENCE = 'NO_PREFENCE'


class Account(BaseModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    lot_id: Optional[str] = Field(foreign_key='lots.id')
    account_holder: Optional[UUID] = Field(default=None, foreign_key='tenants.id')
    bill_preference: BillPreference = Field(default=BillPreference.NO_PREFENCE)
    rental_rate_override: Optional[float] = Field(default=None, nullable=True)
    storage_count: float = Field(default=0)
    inserted_at: datetime = Field(default_factory=et_datetime_now)
    updated_on: datetime = Field(default_factory=et_datetime_now)
    deleted_on: Optional[datetime] = Field(default=None)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @field_serializer('id', 'account_holder')
    def serialize_uuid(self, v: UUID, _info):
        if v:
            return str(v)
        else:
            return v

    @field_serializer('updated_on', 'inserted_at', 'deleted_on')
    def serialize_date(self, v: date | datetime, _info):
        if v is None:
            return v
        elif isinstance(v, str):
            return v
        else:
            return v.isoformat()

    @field_serializer('bill_preference')
    def serialize_enum(self, bill_preference: BillPreference, _info):
        return bill_preference.value
