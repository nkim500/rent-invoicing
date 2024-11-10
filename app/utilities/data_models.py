from datetime import date
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Optional
from uuid import UUID
from uuid import uuid4

from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import SettingsConfigDict
from pytz import timezone
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import BigInteger
from sqlmodel import Field
from sqlmodel import Relationship
from sqlmodel import SQLModel
from typing_extensions import Self


def et_datetime_now():
    eastern = timezone("US/Eastern")
    return datetime.now(tz=eastern)


def et_date_now():
    return et_datetime_now().date()


def et_date_due():
    return et_date_now().replace(day=1)


def et_date_previous():
    return (et_date_due() - timedelta(days=1)).replace(day=1)


def et_date_next():
    return (et_date_due().replace(day=28) + timedelta(days=4)).replace(day=1)


class ChargeTypes(str, Enum):
    LATEFEE = "LATEFEE"
    WATER = "WATER"
    STORAGE = "STORAGE"
    RENT = "RENT"
    OTHER = "OTHER"


class BillPreference(str, Enum):
    NO_PAPER = "NO_PAPER"
    NO_EMAIL = "NO_EMAIL"
    NO_PREFENCE = "NO_PREFENCE"


class Property(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    property_code: str = Field(default="", index=True)
    street_address: str = Field(default="")
    city_state_zip: str = Field(default="")
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)


class Lot(SQLModel, table=True):
    __tablename__ = "lots"

    id: str = Field(primary_key=True)
    property_code: str = Field(default="AP")
    street_address: str = Field(default="")
    city_state_zip: str = Field(default="")
    details: Optional[dict] = Field(default=None, nullable=True, sa_type=JSONB)
    watermeter_id: Optional[int] = Field(foreign_key="watermeters.id", sa_type=BigInteger)
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def check_water(self):
        try:
            int(self.id.replace(self.property_code, ""))
        except ValueError as e:
            raise ValueError(
                "Lot_id must be constructed as self.property_code + int"
            ) from e
        return self

    @property
    def lot_street_address(self):
        return f"{self.id} {self.street_address}"

    @property
    def lot_full_address(self):
        return f"{self.lot_street_address}, {self.city_state_zip}"

    @property
    def customer_id(self):
        return f"AP{self.id}"


class WaterMeter(SQLModel, table=True):
    __tablename__ = "watermeters"

    id: int = Field(primary_key=True, sa_type=BigInteger)
    lot_id: Optional[str] = Field(default=None, foreign_key="lots.id")
    inserted_at: datetime = Field(default_factory=et_datetime_now)


class WaterUsage(SQLModel, table=True):
    __tablename__ = "water_usage"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    watermeter_id: int = Field(
        foreign_key="watermeters.id", nullable=False, sa_type=BigInteger
    )
    previous_date: date = Field(default_factory=et_date_now)
    current_date: date = Field(default_factory=et_date_now)
    previous_reading: int = Field(default=0)
    current_reading: int = Field(default=0)
    statement_date: date = Field(default_factory=et_date_due)
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    __table_args__ = (
        UniqueConstraint("watermeter_id", "statement_date", name="meter_date_key"),
    )

    @field_serializer("id")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("previous_date", "current_date", "statement_date", "inserted_at")
    def serialize_date(self, v: date | datetime, _info):
        if isinstance(v, str):
            return v
        else:
            return v.isoformat()

    @model_validator(mode="after")
    def check_water(self):
        if self.current_reading < self.previous_reading:
            raise ValueError("Current reading cannot be less than previous reading")
        return self

    @property
    def water_usage(self):
        return self.current_reading - self.previous_reading

    def water_bill_dollar_amount(self, water_rate: float, service_fee: float):
        return round(self.water_usage * water_rate + service_fee, 2)


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    lot_id: Optional[str] = Field(foreign_key="lots.id")
    account_holder: Optional[UUID] = Field(default=None, foreign_key="tenants.id")
    bill_preference: BillPreference = Field(default=BillPreference.NO_PREFENCE)
    rental_rate_override: Optional[float] = Field(default=None, nullable=True)
    storage_count: float = Field(default=0)
    inserted_at: datetime = Field(default_factory=et_datetime_now)
    updated_on: datetime = Field(default_factory=et_datetime_now)
    deleted_on: Optional[datetime] = Field(default=None)

    ars: list["AccountsReceivable"] = Relationship(back_populates="account")
    payments: list["Payment"] = Relationship(back_populates="account")

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @field_serializer("id", "account_holder")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("updated_on", "inserted_at", "deleted_on")
    def serialize_date(self, v: date | datetime, _info):
        if v is None:
            return v
        elif isinstance(v, str):
            return v
        else:
            return v.isoformat()

    @field_serializer("bill_preference")
    def serialize_enum(self, bill_preference: BillPreference, _info):
        return bill_preference.value


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    account_id: UUID | None = Field(default=None, foreign_key="accounts.id")
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @field_serializer("id", "account_id")
    def serialize_uuid(self, v: UUID, _info):
        if v is not None:
            return str(v)
        else:
            return v

    @field_serializer("inserted_at")
    def serialize_date(self, v: date | datetime, _info):
        return v.isoformat()


class AccountsReceivable(SQLModel, table=True):
    __tablename__ = "accounts_receivables"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: UUID = Field(foreign_key="accounts.id", index=True)
    account: Optional[Account] = Relationship(back_populates="ars")
    amount_due: float = Field(default=0)
    statement_date: date = Field(default_factory=et_date_now)
    charge_type: ChargeTypes = Field(default=ChargeTypes.RENT)
    paid: bool = Field(default=False)
    details: Optional[dict] = Field(default={}, sa_type=JSONB)
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def validate_amount_input(self) -> Self:
        if self.amount_due < 0 and self.charge_type != ChargeTypes.OTHER:
            raise ValueError(
                "Amount cannot be negative, unless the type of charge is 'Other'"
            )
        return self

    @field_serializer("charge_type")
    def serialize_enum(self, charge_type: ChargeTypes, _info):
        return charge_type.value

    @field_serializer("id", "account_id")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("statement_date", "inserted_at")
    def serialize_date(self, v: date | datetime, _info):
        return v.isoformat()


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    beneficiary_account_id: UUID = Field(foreign_key="accounts.id", index=True)
    amount: float = Field(nullable=False)
    payment_dated: date = Field(default_factory=et_date_now)
    payment_received: date = Field(default_factory=et_date_now)
    inserted_at: datetime = Field(default_factory=et_datetime_now)
    payer: Optional[str] = Field(default=None)
    amount_applied: float = Field(default=0)
    modified_at: datetime = Field(default_factory=et_datetime_now)
    amount_pre_modify: Optional[float] = Field(default=None)

    account: Optional[Account] = Relationship(back_populates="payments")

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @field_serializer("id", "beneficiary_account_id")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("payment_dated", "payment_received", "inserted_at")
    def serialize_date(self, v: date | datetime, _info):
        return v.isoformat()


class InvoiceSetting(SQLModel, table=True):
    __tablename__ = "invoice_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    rent_monthly_rate: int = Field(default=475)
    water_monthly_rate: float = Field(default=0.011784)
    water_service_fee: float = Field(default=1.5)
    storage_monthly_rate: int = Field(default=84)
    late_fee_rate: float = Field(default=0.05)
    overdue_cutoff_days: int = Field(default=10)
    effective_as_of: date = Field(default_factory=et_date_now)
    inserted_at: datetime = Field(default_factory=et_datetime_now)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    @field_serializer("id")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("effective_as_of", "inserted_at")
    def serialize_date(self, v: date, _info):
        if isinstance(v, date):
            return v.isoformat()
        else:
            return v

    @field_validator(
        "rent_monthly_rate", "storage_monthly_rate", mode="before", check_fields=False
    )
    def coerce_and_round_up(cls, v):
        if isinstance(v, float):
            return round(v, 0)
        return v

    def increase_rates_by_percentage(self, percentage: float = 3.0) -> "InvoiceSetting":
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
                raise AttributeError(f"{key} is not a valid attribute of InvoiceSetting.")


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    invoice_date: date = Field()
    statement_date: date = Field()
    account_id: UUID = Field(foreign_key="accounts.id")
    lot_id: Optional[str] = Field(nullable=True)
    tenant_name: str = Field()
    setting_id: UUID = Field()
    amount_due: float = Field(default=0)
    details: dict = Field(default={}, sa_type=JSONB)
    inserted_at: datetime = Field(default_factory=et_datetime_now)
    delivered_on: Optional[date] = Field(default=None, nullable=True)

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    __table_args__ = (
        UniqueConstraint(
            "invoice_date",
            "statement_date",
            "account_id",
            "setting_id",
            name="unique_invoice_per_stmt_date_key",
        ),
    )

    @model_validator(mode="before")
    def convert_dates_in_details(cls, values: dict):
        # details = values.get("details", {})
        details = values["details"]

        for key, value in details.items():
            if isinstance(value, (date, datetime)):
                details[key] = value.isoformat()

        values["details"] = details
        return values

    @field_serializer("id", "account_id", "setting_id")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("invoice_date", "statement_date", "inserted_at", "delivered_on")
    def serialize_date(self, v: date | datetime, _info):
        if v is None:
            return v
        elif isinstance(v, str):
            return v
        else:
            return v.isoformat()
