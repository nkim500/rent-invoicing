import json
from datetime import date
from uuid import UUID

import data_models as models
import requests
import streamlit as st
from config import AppConfig

config = AppConfig()
host = config.host
port = config.port


def submit_new_invoice_setting(setting: models.InvoiceSetting) -> requests.Response:
    """POST request to create an invoice setting to the server

    Args:
        setting (models.InvoiceSetting): Invoice setting details to be created

    Returns:
        requests.Response: API response, containing the created object or error message
    """
    response = requests.post(
        url=f"{host}:{port}/settings",
        json=setting.model_dump(),
    )
    return response


def submit_new_wateremeter_readings(reading: models.WaterUsage) -> requests.Response:
    """POST request to create a new water usage record

    Args:
        reading (models.WaterUsage): Water usage record to be created

    Returns:
        requests.Response: API response, containing the created object or error message
    """
    response = requests.post(
        url=f"{host}:{port}/watermeter",
        json=reading.model_dump(),
    )
    return response


def add_new_receivable(receivable: models.AccountsReceivable) -> requests.Response:
    """POST request to add a new accounts receivable

    Args:
        receivable (models.AccountsReceivable): AccountsReceivable object to add

    Returns:
        requests.Response: Server response for the created receivable
    """
    response = requests.post(
        url=f"{host}:{port}/receivables/", json=receivable.model_dump()
    )
    return response


def add_new_account(account: models.Account) -> requests.Response:
    """POST request to add a new account

    Args:
        account (models.Account): Account object to create

    Returns:
        requests.Response: Server response for the created account
    """
    response = requests.post(url=f"{host}:{port}/accounts", json=account.model_dump())
    return response


def delete_account(account_id: UUID | str) -> requests.Response:
    """PUT request to delete an account by ID

    Args:
        account_id (UUID | str): ID of the account to delete

    Returns:
        requests.Response: JSON-decoded server response
    """
    response = requests.put(url=f"{host}:{port}/accounts/{str(account_id)}")
    status = response.status_code
    if status // 100 == 2:
        return json.loads(response.content)
    else:
        return {"ok": False}


def get_a_list_of_registered_persons() -> list[dict]:
    """GET request to fetch registered persons

    Returns:
        list[dict]: List of persons registered in the system
    """
    response = requests.get(url=f"{host}:{port}/tenants")
    return json.loads(response.content)


def submit_new_tenant(tenant: models.Tenant) -> requests.Response:
    """POST request to create a new tenant

    Args:
        tenant (models.Tenant): Tenant object to add

    Returns:
        requests.Response: Server response for the created tenant
    """
    response = requests.post(url=f"{host}:{port}/tenants", data=tenant.model_dump_json())
    return response


def get_accounts_and_holder() -> list[dict]:
    """GET request to fetch accounts with tenant information

    Returns:
        list[dict]: Accounts with associated tenant info
    """
    response = requests.get(
        url=f"{host}:{port}/accounts/", params={"with_tenant_info": True}
    )
    return json.loads(response.content)


def get_invoice_settings() -> list[dict]:
    """GET request to retrieve all invoice settings

    Returns:
        list[dict]: List of invoice settings
    """
    response = requests.get(url=f"{host}:{port}/settings/")
    return json.loads(response.content)


def get_properties() -> list[dict]:
    """GET request to retrieve all registered properties

    Returns:
        list[dict]: List of properties
    """
    response = requests.get(url=f"{host}:{port}/properties/")
    return json.loads(response.content)


def get_monthly_charges(
    invoice_setting_id: str | UUID, statement_date: date, processing_date: date
) -> list[dict]:
    """GET request to fetch monthly charges by invoice settings and date

    Args:
        invoice_setting_id (str | UUID): ID of invoice settings to apply
        statement_date (date): Date of statement
        processing_date (date): Date of charge processing

    Returns:
        list[dict]: Monthly charge details
    """
    response = requests.get(
        url=f"{host}:{port}/monthly_charges",
        params={
            "invoice_setting_id": str(invoice_setting_id),
            "statement_date": statement_date.isoformat(),
            "processing_date": processing_date.isoformat(),
        },
    )
    return json.loads(response.content)


def post_monthly_charges(
    invoice_setting_id: str | UUID, statement_date: date, processing_date: date
) -> requests.Response:
    """POST request to create monthly charges for the given dates and settings

    Args:
        invoice_setting_id (str | UUID): ID of invoice settings
        statement_date (date): Date of statement
        processing_date (date): Date for processing the charges

    Returns:
        requests.Response: Server response for the created charges
    """
    response = requests.post(
        url=f"{host}:{port}/monthly_charges",
        params={
            "invoice_setting_id": str(invoice_setting_id),
            "statement_date": statement_date.strftime("%Y-%m-%d"),
            "processing_date": processing_date.isoformat(),
        },
    )
    return response


@st.cache_data(ttl=600)
def get_recent_payments(
    since: date | None = None, processing_date: date | None = None
) -> list[dict]:
    """GET request to fetch recent payments based on date filters

    Args:
        since (date, optional): Earliest date to filter payments
        processing_date (date, optional): Date when payments are processed

    Returns:
        list[dict]: List of recent payments
    """
    params = {}
    if since:
        params["since_when"] = since
    if processing_date:
        params["processing_date"] = processing_date.isoformat()

    response = requests.get(url=f"{host}:{port}/payments/", params=params)
    return json.loads(response.content)


def get_available_payments(cut_off_date: date | None = None) -> list[dict]:
    """GET request to retrieve available payments up to the cut-off date

    Args:
        cut_off_date (date, optional): Latest date to consider payments

    Returns:
        list[dict]: Available payments filtered by cut-off date
    """
    params = {}
    if cut_off_date:
        params["processing_date"] = cut_off_date.isoformat()

    response = requests.get(url=f"{host}:{port}/available_payments", params=params)
    return json.loads(response.content)


def add_new_payment(payment: models.Payment) -> requests.Response:
    """POST request to add a new payment

    Args:
        payment (models.Payment): Payment object to add

    Returns:
        requests.Response: Server response for the added payment
    """
    response = requests.post(url=f"{host}:{port}/payments/", json=payment.model_dump())
    return response


def delete_payment(payment_id: UUID | str) -> requests.Response:
    """DELETE request to remove a payment by its ID

    Args:
        payment_id (UUID | str): ID of the payment to delete

    Returns:
        requests.Response: Server response after deletion
    """
    response = requests.delete(
        url=f"{host}:{port}/payments/{str(payment_id)}",
    )
    return response


def process_payments(processing_date: date | None = None) -> requests.Response:
    """POST request to process payments, optionally with a specified date

    Args:
        processing_date (date, optional): Date to process payments

    Returns:
        requests.Response: Server response after processing payments
    """
    params = {}
    if processing_date:
        params["processing_date"] = processing_date.isoformat()
    response = requests.post(
        url=f"{host}:{port}/processing/process_payments", json=params
    )
    return response


def get_other_rent_receivables(
    statement_date: date | None = None, account_id: UUID | str | None = None
) -> list[models.AccountsReceivable]:
    """GET request to fetch other rent receivables, filtered by date and account ID

    Args:
        statement_date (date, optional): Date of the statement
        account_id (UUID | str, optional): Account ID to filter receivables

    Returns:
        list[models.AccountsReceivable]: List of AccountsReceivable records
    """
    params = {}
    if account_id:
        params["account_id"] = str(account_id)
    if statement_date:
        params["statement_date"] = statement_date.strftime("%Y-%m-%d")

    response = requests.get(url=f"{host}:{port}/receivables/other_rent", params=params)
    receivables = json.loads(response.content)

    receivable_objects = (
        [
            models.AccountsReceivable(
                id=item["id"],
                account_id=item["account_id"],
                amount_due=item["amount_due"],
                statement_date=item["statement_date"],
                charge_type=models.ChargeTypes.OTHER,
                paid=item["paid"],
                details=item["details"],
                inserted_at=item["inserted_at"],
            )
            for item in receivables
        ]
        if receivables
        else receivables
    )

    return receivable_objects


def get_new_overdue_receivables(
    statement_date: date, invoice_setting_id: str | UUID
) -> list[dict]:
    """GET request to fetch new overdue receivables by date and invoice setting

    Args:
        statement_date (date): Date of the statement
        invoice_setting_id (str | UUID): Invoice setting ID to filter receivables

    Returns:
        list[dict]: List of overdue receivables
    """
    response = requests.get(
        url=f"{host}:{port}/receivables/overdue",
        params={
            "statement_date": statement_date.strftime("%Y-%m-%d"),
            "invoice_setting_id": str(invoice_setting_id),
        },
    )
    return json.loads(response.content)


def get_invoice_data(
    statement_date: date, setting_id: str | UUID | None = None, update_db: bool = True
) -> list[dict]:
    """GET request to retrieve invoice data based on date, setting, and update flag

    Args:
        statement_date (date): Date of the statement
        setting_id (str | UUID, optional): Invoice setting ID for filtering
        update_db (bool, optional): Whether to update the database

    Returns:
        list[dict]: Invoice data records
    """
    params = {"statement_date": statement_date.isoformat(), "update_db": update_db}

    if setting_id:
        params["invoice_setting_id"] = str(setting_id)

    response = requests.get(url=f"{host}:{port}/invoice/input_data", params=params)
    return json.loads(response.content)


def get_existing_invoice_data(
    statement_date: date, setting_id: str | UUID | None = None
) -> list[dict]:
    """GET request to retrieve existing invoice data based on date, setting

    Args:
        statement_date (date): Date of the statement
        setting_id (str | UUID, optional): Invoice setting ID for filtering

    Returns:
        list[dict]: Invoice data records
    """
    params = {"statement_date": statement_date.isoformat()}

    if setting_id:
        params["invoice_setting_id"] = str(setting_id)

    response = requests.get(url=f"{host}:{port}/invoice", params=params)
    return json.loads(response.content)


def get_available_lots() -> list[dict]:
    """GET request to fetch available lots

    Returns:
        list[dict]: Available lot details
    """
    response = requests.get(url=f"{host}:{port}/lots/available")
    return json.loads(response.content)


def get_unassigned_people() -> list[dict]:
    """GET request to retrieve people without assigned lots

    Returns:
        list[dict]: List of unassigned people
    """
    response = requests.get(url=f"{host}:{port}/unassigned_people")
    return json.loads(response.content)


def get_invoices_for_statement_date(statement_date: date):
    """GET request to fetch invoices for a given statement date

    Args:
        statement_date (date): Date of the statement

    Returns:
        list[dict]: Invoices associated with the date
    """
    response = requests.get(
        url=f"{host}:{port}/invoice", params={"statement_date": statement_date}
    )
    return json.loads(response.content)


def get_water_usages_for_statement_date(statement_date: date):
    """GET request to fetch water usage for a specific statement date

    Args:
        statement_date (date): Date of the statement

    Returns:
        list[dict]: Water usage records
    """
    response = requests.get(
        url=f"{host}:{port}/water_usages",
        params={"statement_date": statement_date, "json_mode": True},
    )
    return json.loads(response.content)


def get_rents_for_statement_date(statement_date: date):
    """GET request to fetch rent charges for a specific statement date

    Args:
        statement_date (date): Date of the statement

    Returns:
        list[dict]: Rent charge details
    """
    response = requests.get(
        url=f"{host}:{port}/receivables/rents", params={"statement_date": statement_date}
    )
    return json.loads(response.content)


def get_storages_for_statement_date(statement_date: date):
    """GET request to fetch storage charges for a specific statement date

    Args:
        statement_date (date): Date of the statement

    Returns:
        list[dict]: Storage charge details
    """
    response = requests.get(
        url=f"{host}:{port}/receivables/storages",
        params={"statement_date": statement_date},
    )
    return json.loads(response.content)
