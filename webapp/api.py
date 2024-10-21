import json
import requests
from datetime import date
from uuid import UUID

import streamlit as st

import data_models as models
from config import AppConfig

config = AppConfig()
host = config.host
port = config.port


def submit_new_invoice_setting(setting: models.InvoiceSetting) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/settings",
        # data=setting.model_dump_json(),
        json=setting.model_dump(),
    )
    return response


def submit_new_wateremeter_readings(reading: models.WaterUsage) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/watermeter",
        json=reading.model_dump(),
    )
    return response


def add_new_receivable(receivable: models.AccountsReceivable) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/receivables/", json=receivable.model_dump()
    )
    return response


def add_new_account(account: models.Account) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/accounts/", json=account.model_dump()
    )
    return response


def delete_account(account_id: UUID | str) -> requests.Response:
    account_id = str(account_id)
    response = requests.put(url=f"{host}:{port}/accounts/{account_id}")


    return json.loads(response.content)


def get_a_list_of_registered_persons() -> list[dict]:
    response=requests.get(url=f"{host}:{port}/tenants")
    persons=json.loads(response.content)
    return persons


def submit_new_tenant(tenant: models.Tenant) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/tenants",
        data=tenant.model_dump_json()
    )
    return response


def get_accounts_and_holder() -> list[dict]:
    response = requests.get(
        url=f"{host}:{port}/accounts/",
        params={"with_tenant_info": True}
    )
    accts = json.loads(response.content)
    return accts


def get_invoice_settings() -> list[dict]:
    response = requests.get(
        url=f"{host}:{port}/settings/"
    )
    settings = json.loads(response.content)
    return settings


def get_monthly_charges(
    invoice_setting_id: str | UUID,
    statement_date: date,
    processing_date: date
) -> list[dict]:

    response = requests.get(
        url=f"{host}:{port}/monthly_charges",
        params={
            "invoice_setting_id": str(invoice_setting_id),
            "statement_date": statement_date.isoformat(),
            "processing_date": processing_date.isoformat()
        }
    )
    charges = json.loads(response.content)
    return charges


def post_monthly_charges(
    invoice_setting_id: str | UUID,
    statement_date: date,
    processing_date: date
) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/monthly_charges",
        params={
                "invoice_setting_id": str(invoice_setting_id),
                "statement_date": statement_date.strftime("%Y-%m-%d"),
                "processing_date": processing_date.isoformat()
            }
    )
    return response


@st.cache_data(ttl=600)
def get_recent_payments(
    since: date | None = None, processing_date: date | None = None
) -> list[dict]:
    params = {}

    if since:
        params["since_when"] = since
    if processing_date:
        params["processing_date"] = processing_date.isoformat()

    response = requests.get(
        url=f"{host}:{port}/payments/",
        params=params
    )
    recent_payments = json.loads(response.content)
    return recent_payments


def get_available_payments(cut_off_date: date | None = None) -> list[dict]:
    params = {}
    if cut_off_date:
        params["processing_date"] = cut_off_date.isoformat()

    response = requests.get(
        url=f"{host}:{port}/available_payments",
        params=params
    )
    payments = json.loads(response.content)
    return payments


def add_new_payment(payment: models.Payment) -> requests.Response:
    response = requests.post(
        url=f"{host}:{port}/payments/",
        json=payment.model_dump()
    )
    return response


def delete_payment(payment_id: UUID | str) -> requests.Response:
    if isinstance(payment_id, UUID):
        payment_id = str(payment_id)

    response = requests.delete(
        url=f"{host}:{port}/payments/{payment_id}",
    )
    return response


def process_payments(processing_date: date | None = None) -> requests.Response:
    params = {}
    if processing_date:
        params['processing_date'] = processing_date.isoformat()
    response = requests.post(
        url=f"{host}:{port}/processing/process_payments",
        json=params
    )
    return response


def get_other_rent_receivables(
    statement_date: date | None = None, account_id: UUID | str | None = None
) -> list[models.AccountsReceivable]:
    params = {}
    if account_id:
        params["account_id"] = str(account_id)
    if statement_date:
        params["statement_date"] = statement_date.strftime("%Y-%m-%d")

    response = requests.get(
        url=f"{host}:{port}/receivables/other_rent",
        params=params
    )
    receivables = json.loads(response.content)
    if receivables:
        receivable_objects = [
            models.AccountsReceivable(
                id=item["id"],
                account_id=item["account_id"],
                amount_due=item["amount_due"],
                statement_date=item["statement_date"],
                charge_type=models.ChargeTypes.OTHER,
                paid=item["paid"],
                details=item["details"],
                inserted_at=item["inserted_at"]
            ) for item in receivables
        ]

    return receivable_objects


def get_new_overdue_receivables(
    statement_date: date, invoice_setting_id: str | UUID
) -> list[dict]:
    response = requests.get(
        url=f"{host}:{port}/receivables/overdue",
        params={
            "statement_date": statement_date.strftime("%Y-%m-%d"),
            "invoice_setting_id": str(invoice_setting_id)
        }
    )
    receivables = json.loads(response.content)
    return receivables


def get_invoice_data(
    statement_date: date,
    setting_id: str | UUID | None = None,
    update_db: bool = True
) -> list[dict]:

    params = {
        "statement_date": statement_date.isoformat(),
        "update_db": update_db
    }
    
    if setting_id:
        if isinstance(setting_id, UUID):
            setting_id = str(setting_id)
        params["invoice_setting_id"] = setting_id
    
    response = requests.get(
        url=f"{host}:{port}/invoice/input_data",
        params=params
    )
    invoice_data = json.loads(response.content)
    return invoice_data


def get_available_lots() -> list[dict]:
    response = requests.get(
        url=f"{host}:{port}/lots/available",
    )
    available_lots = json.loads(response.content)
    return available_lots


def get_unassigned_people() -> list[dict]:
    response = requests.get(
        url=f"{host}:{port}/unassigned_people",
    )
    people = json.loads(response.content)
    return people


def get_invoices_for_statement_date(statement_date: date):
    response = requests.get(
        url=f"{host}:{port}/invoice",
        params={"statement_date": statement_date}
    )
    invoices = json.loads(response.content)
    return invoices


def get_water_usages_for_statement_date(statement_date: date):
    response = requests.get(
        url=f"{host}:{port}/water_usages",
        params={"statement_date": statement_date, "json_mode": True}
    )
    usages = json.loads(response.content)
    return usages


def get_rents_for_statement_date(statement_date: date):
    response = requests.get(
        url=f"{host}:{port}/receivables/rents",
        params={"statement_date": statement_date}
    )
    rents = json.loads(response.content)
    return rents


def get_storages_for_statement_date(statement_date: date):
    response = requests.get(
        url=f"{host}:{port}/receivables/storages",
        params={"statement_date": statement_date}
    )
    storages = json.loads(response.content)
    return storages
