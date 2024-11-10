from datetime import date
from datetime import timedelta
from uuid import UUID

import utilities.data_models as models
from configs.config import BusinessEntityParams
from configs.config import get_logger
from sqlalchemy import Row

logger = get_logger()


def incur_recurring_charges(
    input_list: list,
    charge_type: models.ChargeTypes,
    statement_date: date | None = None,
    config: models.InvoiceSetting | None = None,
) -> list[models.AccountsReceivable]:
    """
    Generate recurring charge entries for an account based on charge type and settings.

    Args:
        input_list (list):
            List of AccountsReceivable or tuple[Account.id, WaterUsage].
        charge_type (models.ChargeTypes):
            Type of recurring charge to incur among RENT, STORAGE, WATER (except LATEFEE)
        statement_date (date | None, optional):
            Date of the statement; defaults to the current date.
        config (models.InvoiceSetting | None, optional):
            Settings for rate configurations; if None, default InvoiceSetting is used.

    Returns:
        list[models.AccountsReceivable]:
            List of AccountsReceivable entries with computed charges.
    """
    if not len(input_list):
        return
    if config is None:
        config = models.InvoiceSetting()
    if statement_date is None:
        statement_date = models.et_date_now()

    def _get_acct_id(_i: models.AccountsReceivable | tuple) -> str | UUID:
        if (
            charge_type == models.ChargeTypes.RENT
            or charge_type == models.ChargeTypes.STORAGE
        ):
            return _i.id
        elif charge_type == models.ChargeTypes.WATER:
            return _i[0]

    def _calculate_amount_due(
        _i: models.Account | tuple[UUID, models.WaterUsage],
        charge_type: models.ChargeTypes,
    ) -> float:
        if charge_type == models.ChargeTypes.RENT:
            if _i.lot_id is None:
                return 0
            return (
                _i.rental_rate_override
                if _i.rental_rate_override
                else config.rent_monthly_rate
            )
        elif charge_type == models.ChargeTypes.STORAGE:
            return (
                _i.storage_count * config.storage_monthly_rate if _i.storage_count else 0
            )
        elif charge_type == models.ChargeTypes.WATER:
            return _i[1].water_bill_dollar_amount(
                config.water_monthly_rate,
                config.water_service_fee,
            )

    inserts = [
        models.AccountsReceivable(
            account_id=_get_acct_id(i),
            amount_due=_calculate_amount_due(i, charge_type),
            statement_date=statement_date,
            charge_type=charge_type,
        )
        for i in input_list
        if _calculate_amount_due(i, charge_type) != 0
    ]

    return inserts


def incur_late_fee(
    overdue_items: list[models.AccountsReceivable],
    config: models.InvoiceSetting,
    statement_date: date | None = None,
    processing_date: date | None = None,
    payments: list[models.Payment] = None,
) -> list[models.AccountsReceivable]:
    """
    Create late fee entries for overdue accounts based on overdue criteria and settings.

    Args:
        overdue_items (list[models.AccountsReceivable]):
            List of overdue AccountsReceivable items.
        config (models.InvoiceSetting):
            Settings including the late fee rate.
        statement_date (date | None, optional):
            Date of the statement; defaults to the current month's first day.
        processing_date (date | None, optional):
            Date when late fees are processed; determines overdue status.
        payments (list[models.Payment], optional):
            List of payments to check against overdue amounts; defaults to an empty list.

    Returns:
        list[models.AccountsReceivable]:
            List of new late fee AccountsReceivables.
    """
    if payments is None:
        payments = []
    if statement_date is None:
        statement_date = models.et_date_due()

    residuals, not_paid, _, _ = process_accounts_receivables(
        accounts_receivables=overdue_items, payments=payments
    )

    still_overdue = not_paid + residuals
    logger.error(f"Number of overdues {len(still_overdue)}")
    inserts = [
        models.AccountsReceivable(
            account_id=overdue.account_id,
            amount_due=round(overdue.amount_due * config.late_fee_rate, 2),
            statement_date=statement_date,
            charge_type=models.ChargeTypes.LATEFEE,
            details={"original_item_id": str(overdue.id)},
        )
        for overdue in still_overdue
        if (
            not processing_date
            or overdue.statement_date + timedelta(days=10)
            <= processing_date  # setting.overdue_cutoff_days
        )
    ]

    return inserts


def process_accounts_receivables(
    accounts_receivables: list[models.AccountsReceivable],
    payments: list[models.Payment | None],
) -> tuple[
    list[models.AccountsReceivable | None],
    list[models.AccountsReceivable | None],
    list[models.AccountsReceivable | None],
    list[models.AccountsReceivable | None],
]:
    """
    Process payments against accounts receivables, categorizing each as fully paid,
    partially paid, unpaid, or residual.

    Args:
        accounts_receivables (list[models.AccountsReceivable]):
            List of receivable entries to process.
        payments (list[models.Payment | None]):
            List of payments to apply to receivables.

    Returns:
        tuple: Lists of residual, unpaid, partially paid, and fully paid accounts.
    """
    # Sort AccountsReceivables by inserted_at datetime descending
    accounts_receivables = sorted(
        accounts_receivables, key=lambda ar: ar.inserted_at, reverse=True
    )
    residual, not_paid, partially_paid, fully_paid = [], [], [], []
    original_amounts = {i.id: i.amount_due for i in accounts_receivables}

    if not payments:
        return residual, accounts_receivables, partially_paid, fully_paid

    payment_index = 0

    # Iterate through each AccountsReceivable
    for receivable in accounts_receivables:
        tried_processing = False
        while payment_index < len(payments) and receivable.amount_due > 0:
            payment = payments[payment_index]

            # Calculate the remaining amount in the current payment
            available_payment_amount = payment.amount - payment.amount_applied

            if available_payment_amount > 0:
                tried_processing = True
                # Check if the payment can fully cover the receivable
                if available_payment_amount >= receivable.amount_due:
                    # Fully cover the receivable
                    payment.amount_applied += receivable.amount_due
                    receivable.paid = True
                    receivable.amount_due = 0  # Mark receivable as fully paid
                else:
                    # Partially cover the receivable
                    receivable.amount_due -= available_payment_amount
                    payment.amount_applied += available_payment_amount

            # Move to the next payment if the current one is fully utilized
            if payment.amount_applied >= payment.amount:
                payment_index += 1

        # If receivable was partially covered, create a new one for the remaining amount
        if receivable.amount_due > 0 and tried_processing:
            new_receivable = models.AccountsReceivable(
                account_id=receivable.account_id,
                amount_due=round(receivable.amount_due, 2),
                statement_date=receivable.statement_date,
                charge_type=receivable.charge_type,
                paid=False,
                details={"residual carried over from": str(receivable.id)},
                inserted_at=receivable.inserted_at,
            )
            residual.append(new_receivable)
            receivable.amount_due = original_amounts[receivable.id]
            receivable.paid = True
            partially_paid.append(receivable)
        # If receivable was not paid at all, append the original back
        elif receivable.amount_due > 0 and not tried_processing:
            not_paid.append(receivable)
        # If receivable was fully paid, append the original back
        elif receivable.amount_due == 0 and receivable.paid is True:
            receivable.amount_due = original_amounts[receivable.id]
            fully_paid.append(receivable)

    logger.debug(f"There were {len(residual)} residual(s)")
    logger.debug(f"There were {len(not_paid)} not_paid(s)")
    logger.debug(f"There were {len(partially_paid)} partially_paid(s)")
    logger.debug(f"There were {len(fully_paid)} fully_paid(s)")

    return residual, not_paid, partially_paid, fully_paid


def _compare_ar_pair(
    _ar: models.AccountsReceivable, _ars: list[models.AccountsReceivable]
) -> bool:
    """
    Returns True if an AccountsReceivable with the same Account.id, ChargeType, and
    statement date is found within a given list of AccountsReceivable.

    Args:
        _ar (models.AccountsReceivable):
            target AccountsReceivable to compare
        _ars (list[models.AccountsReceivable]):
            list of AccountsReceivable to compare against

    Returns:
        bool: returns True if duplicate found; else returns False
    """
    for i in _ars:
        if (
            _ar.account_id == i.account_id
            and _ar.charge_type.value == i.charge_type.value
            and _ar.statement_date == i.statement_date
            and _ar.charge_type.value != models.ChargeTypes.OTHER.value
        ):
            return True
    return False


def _check_duplicate(
    _receivables_list: list[models.AccountsReceivable],
    _outstanding: list[models.AccountsReceivable],
) -> None:
    """Pops a duplicate entry from _receivables_list if found from _outstanding

    Args:
        _receivables_list (list[models.AccountsReceivable]):
            list of new recurring charges to be created
        _outstanding (list[models.AccountsReceivable]):
            list of recurring charges already in the database
    """
    if not _receivables_list or not _outstanding:
        return

    idx = 0
    to_pop = []
    for i in _receivables_list:
        if _compare_ar_pair(i, _outstanding):
            to_pop.append(idx)
        idx += 1
    for i in reversed(to_pop):
        _receivables_list.pop(i)


def filter_for_new_items(
    outstanding: list[models.AccountsReceivable] = None,
    rents: list[models.AccountsReceivable] = None,
    storages: list[models.AccountsReceivable] = None,
    new_late_fees: list[models.AccountsReceivable] = None,
    waters: list[models.AccountsReceivable] = None,
) -> tuple[
    list[models.AccountsReceivable],
    list[models.AccountsReceivable],
    list[models.AccountsReceivable],
    list[models.AccountsReceivable],
]:
    """
    Filter out duplicate receivable items to retain only new entries.

    Args:
        outstanding (list[models.AccountsReceivable], optional):
            List of outstanding items already recorded in the database
        rents (list[models.AccountsReceivable], optional):
            List of rent items to check for duplicates.
        storages (list[models.AccountsReceivable], optional):
            List of storage items to check for duplicates.
        new_late_fees (list[models.AccountsReceivable], optional):
            List of late fee items to check for duplicates.
        waters (list[models.AccountsReceivable], optional):
            List of water bill items to check for duplicates.

    Returns:
        tuple: Contains lists of new rent, storage, late fee, and water bill items.
    """
    if rents is None:
        rents = []
    if outstanding is None:
        outstanding = []
    if new_late_fees is None:
        new_late_fees = []
    if waters is None:
        waters = []
    if storages is None:
        storages = []
    for receivables in [rents, storages, new_late_fees, waters]:
        _check_duplicate(receivables, outstanding)

    return rents, storages, new_late_fees, waters


def serialize_invoice_input_data_row(
    row: Row, as_invoice_object: bool = False
) -> dict | list[models.Invoice]:
    """
    Parse from SQLAlchemy Row object and convert it into a dictionary or Invoice object.

    Args:
        row (Row):
            SQLAlchemy Row object containing invoice data fields.
        as_invoice_object (bool, optional):
            If True, returns a validated Invoice model object instead of a dictionary.

    Returns:
        dict | list[models.Invoice]:
            Parsed row data in dictionary form or as an Invoice object.
    """
    company = BusinessEntityParams()
    statement_date = row[0]
    total_amount_due = row[9]
    invoice_setting_id = row[22]

    if not total_amount_due:
        return

    lot_id = row[2]
    csz = row[5]
    if lot_id:
        tenant_address_1 = f"{lot_id.replace(row[3], "")} {row[4]}"
    else:
        tenant_address_1 = ""
    if csz:
        tenant_address_2 = csz
    else:
        tenant_address_2 = ""

    parsed = {
        "invoice_customer_id": f"{lot_id}",
        "tenant_address_1": tenant_address_1,
        "tenant_address_2": tenant_address_2,
        "tenant_name": row[6],
        "amt_prev_month_paid": row[10],
        "amt_prev_month_residual": row[8],
        "invoice_total_amount_due": row[9],
        "amt_total_amount_due": row[9],
        "amt_overdue": row[11],
        "amt_other_rent": row[12],
        "amt_rent": row[13],
        "amt_storage": row[14],
        "amt_water": row[15],
        "water_bill_period": row[15],
        "water_prev_read": row[16],
        "water_curr_read": row[17],
        "water_curr_date": row[18],
        "water_prev_date": row[19],
        "water_meter_id": row[20],
        "amt_late_fee": row[21],
    }

    if (row[17] is not None) and (row[16] is not None):
        parsed["desc_curr_water"] = f"""Water bill for {
            parsed['water_prev_date'].strftime("%B %Y")
        }"""
        parsed["date_water"] = statement_date
        parsed["water_usage_period"] = row[17] - row[16]
    else:
        parsed["desc_curr_water"] = None
        parsed["date_water"] = None
        parsed["water_usage_period"] = None

    if row[21]:
        parsed["desc_late_fee"] = "Late fee"
        parsed["date_late"] = statement_date
    else:
        parsed["desc_late_fee"] = None
        parsed["date_late"] = None

    if row[13]:
        parsed["desc_curr_rent"] = f"Lot rent for {(statement_date).strftime("%B %Y")}"
        parsed["date_rent"] = statement_date
    else:
        parsed["desc_curr_rent"] = None
        parsed["date_rent"] = None

    if row[14]:
        parsed["desc_curr_storage"] = f"""Storage rent for {
            (statement_date).strftime("%B %Y")
        }"""
        parsed["date_storage"] = statement_date
    else:
        parsed["desc_curr_storage"] = None
        parsed["date_storage"] = None

    if row[10]:
        parsed["desc_prev_month_paid"] = f"""Bill paid for {
            (statement_date - timedelta(days=28)).strftime("%B %Y")
        }"""
        parsed["date_today_1"] = models.et_date_now()
    else:
        parsed["desc_prev_month_paid"] = None
        parsed["date_today_1"] = None

    if row[8] is not None:
        parsed["desc_prev_month_residual"] = f"""{
            (statement_date - timedelta(days=28)).strftime("%B")
        } bill, less paid"""
        parsed["date_today_2"] = models.et_date_now()
    else:
        parsed["desc_prev_month_residual"] = None
        parsed["date_today_2"] = None

    if row[11]:
        parsed["desc_prev_overdue"] = "Previous overdue"
    else:
        parsed["desc_prev_overdue"] = None

    if row[12]:
        parsed["desc_other_rent"] = "Other rent(s)*"
        parsed["date_other_rent"] = statement_date
        parsed["detail_other_rent"] = f"* Other rents include: {row[23]}"
    else:
        parsed["desc_other_rent"] = None
        parsed["date_other_rent"] = None
        parsed["detail_other_rent"] = None

    parsed["invoice_date"] = models.et_date_now()
    parsed["business_name"] = company.business_name
    parsed["business_address_1"] = company.business_address_1
    parsed["business_address_2"] = company.business_address_2
    parsed["business_contact_phone"] = company.business_contact_phone
    parsed["business_contact_email"] = company.business_contact_email
    parsed["invoice_due_date"] = statement_date
    parsed["business_name_"] = company.business_name.upper()
    parsed["business_address_1_"] = company.business_address_1
    parsed["business_address_2_"] = company.business_address_2
    parsed["business_contact_email_"] = f"Or Zelle to {company.business_contact_email}"
    parsed["invoice_date_"] = parsed["invoice_date"]
    parsed["invoice_customer_id_"] = parsed["invoice_customer_id"]
    parsed["invoice_due_date_"] = parsed["invoice_due_date"]
    parsed["invoice_total_amount_due_"] = parsed["invoice_total_amount_due"]

    if as_invoice_object:
        return models.Invoice.model_validate(
            {
                "invoice_date": parsed["invoice_date"],
                "statement_date": statement_date,
                "account_id": row[1],
                "lot_id": lot_id,
                "tenant_name": parsed["tenant_name"],
                "setting_id": invoice_setting_id,
                "amount_due": parsed["amt_total_amount_due"],
                "details": parsed,
            }
        )

    return parsed
