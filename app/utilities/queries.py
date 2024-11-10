from datetime import date
from datetime import timedelta
from uuid import UUID

import utilities.data_models as models
from sqlalchemy import UUID as UUIDSA
from sqlalchemy import Select
from sqlalchemy import Update
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import literal
from sqlalchemy import not_
from sqlalchemy import or_
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.sql.functions import coalesce
from sqlmodel import and_
from sqlmodel import case
from sqlmodel import select


def get_receivables_query(statement_date: date | None = None) -> Select:
    """Retrieve accounts receivable, optionally filtered by statement date

    Args:
        statement_date (date | None):
            The statement date to filter the receivables; retrieves all if None

    Returns:
        Select:
            A SQLAlchemy `Select` statement to query accounts receivable
    """
    query = select(models.AccountsReceivable)
    if statement_date:
        query = query.where(
            or_(
                models.AccountsReceivable.statement_date == statement_date,
                models.AccountsReceivable.paid.is_(False),
            )
        )
    return query


def get_receivables_sum_query(statement_date: date | None = None) -> Select:
    """Return the total amount due for each account, grouped by account ID

    Args:
        statement_date (date | None):
            The statement date to filter by; retrieves all if None

    Returns:
        Select: A SQLAlchemy `Select` statement to query total due per account
    """
    query = select(
        models.AccountsReceivable.account_id.label("account_id"),
        func.sum(models.AccountsReceivable.amount_due).label("receivables_sum"),
    ).group_by(models.AccountsReceivable.account_id)
    if statement_date:
        query = query.where(models.AccountsReceivable.statement_date == statement_date)

    return query


def get_a_receivable_query(ar_id: UUID) -> Select:
    """Fetch a specific accounts receivable by its unique ID

    Args:
        ar_id (UUID): The unique ID of the accounts receivable to retrieve

    Returns:
        Select: A SQLAlchemy `Select` statement for the specified accounts receivable
    """
    return select(models.AccountsReceivable).where(models.AccountsReceivable.id == ar_id)


def get_payments_query() -> Select:
    """Aggregate payment amounts by beneficiary account, with total for each

    Returns:
        Select: A SQLAlchemy `Select` statement for payments aggregation
    """
    query = select(
        models.Payment.beneficiary_account_id.label("account_id"),
        func.sum(models.Payment.amount).label("payments_sum"),
    ).group_by(models.Payment.beneficiary_account_id)
    return query


def get_water_usage_query(statement_date: date | None = None) -> Select:
    """Fetch water usage data, optionally filtered by statement date

    Args:
        statement_date (date | None):
            The statement date for filtering water usage; retrieves all if None

    Returns:
        Select:
            A SQLAlchemy `Select` statement for water usage data
    """
    query = (
        select(models.Account.id, models.WaterUsage)
        .join_from(models.Account, models.Lot, models.Account.lot_id == models.Lot.id)
        .join_from(
            models.Lot,
            models.WaterMeter,
            models.Lot.watermeter_id == models.WaterMeter.id,
        )
        .where(models.Account.deleted_on.is_(None))
    )

    if statement_date:
        query = query.join_from(
            models.WaterMeter,
            models.WaterUsage,
            models.WaterMeter.id == models.WaterUsage.watermeter_id,
        ).where(models.WaterUsage.statement_date == statement_date)
    else:
        subquery = select(
            models.WaterUsage,
            func.row_number()
            .over(
                partition_by=models.WaterUsage.watermeter_id,
                order_by=desc(models.WaterUsage.statement_date),
            )
            .label("row_num"),
        ).subquery()
        query = query.join_from(
            models.WaterMeter, subquery, models.WaterMeter.id == subquery.c.watermeter_id
        ).where(subquery.c.row_num == 1)

    return query


def update_watermeter_lot_id_query(watermeter_id: int, lot_id: str) -> Update:
    """Update the lot ID associated with a specified water meter

    Args:
        watermeter_id (int): The ID of the water meter to update
        lot_id (str): The new lot ID to associate with the water meter

    Returns:
        Update: A SQLAlchemy `Update` statement for the specified water meter
    """
    return (
        update(models.WaterMeter)
        .where(models.WaterMeter.id == watermeter_id)
        .values(lot_id=lot_id)
    )


def update_tenant_account_id_query(tenant_id: UUID, account_id: UUID) -> Update:
    """Associate a tenant with a specific account ID

    Args:
        tenant_id (UUID): The unique ID of the tenant
        account_id (UUID): The account ID to associate with the tenant

    Returns:
        Update: A SQLAlchemy `Update` statement for the tenant’s account association
    """
    return (
        update(models.Tenant)
        .where(models.Tenant.id == tenant_id)
        .values(account_id=account_id)
    )


def get_other_rents_query(
    account_id: UUID | None = None, statement_date: date | None = None
) -> Select:
    """Fetch 'other' type rent charges for a specified account and date

    Args:
        account_id (UUID | None):
            The account ID to filter by; retrieves all if None
        statement_date (date | None):
            The statement date to filter by; retrieves all if None

    Returns:
        Select: A SQLAlchemy `Select` statement for 'other' rent charges
    """
    query = select(models.AccountsReceivable).where(
        and_(
            (models.AccountsReceivable.charge_type == models.ChargeTypes.OTHER),
            (models.AccountsReceivable.account_id == account_id if account_id else True),
        )
    )
    if statement_date:
        query = query.where(models.AccountsReceivable.statement_date == statement_date)

    return query.order_by(models.AccountsReceivable.inserted_at.desc())


def get_unpaid_items_query(
    account_id: UUID,
    statement_date: date | None = None,
    processing_date: date | None = None,
) -> Select:
    """Retrieve unpaid accounts receivable for an account, with optional date filters

    Args:
        account_id (UUID):
            The account ID to filter by
        statement_date (date | None):
            The statement date to filter by; retrieves all if None
        processing_date (date | None):
            The processing date to filter by; retrieves all if None

    Returns:
        Select: A SQLAlchemy `Select` statement for unpaid accounts receivable
    """
    query = select(models.AccountsReceivable).where(
        and_(
            models.AccountsReceivable.paid.is_(False),
            models.AccountsReceivable.account_id == account_id,
        )
    )
    if statement_date:
        query = query.where(models.AccountsReceivable.statement_date == statement_date)
    if processing_date:
        query = query.where(models.AccountsReceivable.statement_date <= processing_date)

    return query.order_by(models.AccountsReceivable.inserted_at.desc())


def get_all_unpaid_items_query(
    statement_date: date | None = None, processing_date: date | None = None
) -> Select:
    """Fetch all unpaid accounts receivable, optionally filtered by date

    Args:
        statement_date (date | None):
            The statement date for filtering; retrieves all if None
        processing_date (date | None):
            The processing date for filtering; retrieves all if None

    Returns:
        Select:
            A SQLAlchemy `Select` statement for all unpaid accounts receivable
    """
    query = select(models.AccountsReceivable).where(
        models.AccountsReceivable.paid.is_(False)
    )
    if statement_date:
        query = query.where(models.AccountsReceivable.statement_date < statement_date)
    if processing_date:
        query = query.where(models.AccountsReceivable.statement_date <= processing_date)
    return query


def get_receivable_by_charge_type_query(
    charge_type: models.ChargeTypes,
    statement_date: date | None = None,
    processing_date: date | None = None,
    is_paid: bool | None = None,
) -> Select:
    """Retrieve receivables by charge type, with optional filters

    Args:
        charge_type (models.ChargeTypes):
            The type of charge to filter by
        statement_date (date | None):
            The statement date for filtering; retrieves all if None
        processing_date (date | None):
            The processing date for filtering; retrieves all if None
        is_paid (bool | None):
            Filter by payment status; retrieves all if None

    Returns:
        Select: A SQLAlchemy `Select` statement for accounts receivable by charge type
    """
    query = select(models.AccountsReceivable).where(
        models.AccountsReceivable.charge_type == charge_type
    )
    if statement_date:
        query = query.where(models.AccountsReceivable.statement_date == statement_date)
    if processing_date:
        query = query.where(models.AccountsReceivable.statement_date <= processing_date)
    if is_paid:
        query = query.where(models.AccountsReceivable.paid.is_(is_paid))
    return query


def get_available_payments_query(
    account_id: UUID | None = None, processing_date: date | None = None
) -> Select:
    """Fetch payments available for application, filtered by account and date

    Args:
        account_id (UUID | None):
            The account ID to filter by; retrieves all if None
        processing_date (date | None):
            The processing date for filtering; retrieves all if None

    Returns:
        Select: A SQLAlchemy `Select` statement for available payments
    """
    query = select(models.Payment).where(
        models.Payment.amount > models.Payment.amount_applied
    )
    if account_id:
        query = query.where(models.Payment.beneficiary_account_id == account_id)
    if processing_date:
        query = query.where(models.Payment.payment_received <= processing_date)

    return query


def get_invoice_settings_query():
    """Retrieve invoice settings

    Args:
        statement_date (date | None):
            The statement date to filter the settings; retrieves all if None

    Returns:
        Select: A SQLAlchemy `Select` statement for invoice settings
    """
    return select(models.InvoiceSetting).order_by(
        models.InvoiceSetting.inserted_at.desc()
    )


def get_invoice_setting_query(setting_id: UUID | str):
    """Retrieve a specific invoice setting by ID, handling UUID or string input

    Args:
        setting_id (UUID | str): The unique identifier of the invoice setting

    Returns:
        Select: A SQLAlchemy `Select` statement to fetch the invoice setting
    """
    if isinstance(setting_id, str):
        try:
            setting_id = UUID(setting_id)
        except Exception as e:
            raise e
    return select(models.InvoiceSetting).where(models.InvoiceSetting.id == setting_id)


def get_recent_payments_query(since_when: date | None = None):
    """Fetch recent payments since a specified date, if provided

    Args:
        since_when (date | None): The date to filter recent payments; fetches all if None

    Returns:
        Select: A SQLAlchemy `Select` statement for recent payments
    """
    return (
        select(models.Payment)
        .where(models.Payment.inserted_at >= since_when if since_when else True)
        .order_by(models.Payment.inserted_at.desc())
    )


def get_tenants_query():
    """Retrieve all tenants ordered by their last name

    Returns:
        Select: A SQLAlchemy `Select` statement for all tenants
    """
    return select(models.Tenant).order_by(models.Tenant.last_name)


def get_tenant_query(tenant_id: UUID):
    """Fetch a specific tenant by ID

    Args:
        tenant_id (UUID): The unique identifier of the tenant

    Returns:
        Select: A SQLAlchemy `Select` statement for the tenant
    """
    return select(models.Tenant).where(models.Tenant.id == tenant_id)


def get_accounts_query(with_tenant_info: bool = False, active_only: bool = False):
    """
        Retrieve account information, optionally with tenant details or active status
        filter

    Args:
        with_tenant_info (bool): Whether to include tenant details
        active_only (bool): Whether to fetch only active accounts

    Returns:
        Select: A SQLAlchemy `Select` statement for accounts with optional filters
    """
    if with_tenant_info:
        query = select(
            models.Account.id,
            models.Account.lot_id,
            func.concat(models.Tenant.first_name, " ", models.Tenant.last_name).label(
                "full_name"
            ),
        ).join(models.Tenant, models.Account.account_holder == models.Tenant.id)
    else:
        query = select(models.Account)

    if active_only:
        query = query.where(models.Account.deleted_on.is_(None))

    return query.order_by(models.Account.lot_id)


def get_receivables_without_late_fees_query(current_date: date, days: int = 10):
    """
        Fetch receivables due before a specified number of days from the current date,
        excluding late fees

    Args:
        current_date (date): The date to calculate receivables due by
        days (int): The number of days to filter receivables by (default is 10)

    Returns:
        Select: A SQLAlchemy `Select` statement for receivables without late fees
    """
    late_fee_subquery = (
        select(models.AccountsReceivable.details["original_item_id"].astext.cast(UUIDSA))
        .where(models.AccountsReceivable.charge_type == models.ChargeTypes.LATEFEE)
        .scalar_subquery()
    )
    return select(models.AccountsReceivable).where(
        models.AccountsReceivable.statement_date + timedelta(days=days) <= current_date,  # noqa: E501
        models.AccountsReceivable.charge_type != models.ChargeTypes.LATEFEE,
        models.AccountsReceivable.paid.is_(False),
        not_(models.AccountsReceivable.id.in_(late_fee_subquery)),
    )


def get_existing_invoice_query(
    statement_date: date | None, setting_id: UUID | None = None
):
    """Retrieve an invoice by statement date and setting ID, if provided

    Args:
        statement_date (date | None): The statement date for the invoice
        setting_id (UUID | None): The invoice setting ID to filter by

    Returns:
        Select: A SQLAlchemy `Select` statement for an existing invoice
    """
    return select(models.Invoice).where(
        models.Invoice.statement_date == statement_date if statement_date else True,
        models.Invoice.setting_id == setting_id if setting_id else True,
    )


def get_invoice_input_data_query(statement_date: date, setting_id: UUID | None = None):
    """
        Fetch invoice input data based on statement date and setting ID, including
        subqueries for rates and charges

    Args:
        statement_date (date): The statement date for calculating input data
        setting_id (UUID | None): The invoice setting ID to filter by

    Returns:
        Select: A SQLAlchemy `Select` statement for detailed invoice input data
    """
    adj = statement_date - timedelta(days=28)
    previous_month_date = adj.replace(day=1)

    invoice_setting_subquery = (
        select(
            models.InvoiceSetting.water_monthly_rate,
            models.InvoiceSetting.water_service_fee,
            models.InvoiceSetting.rent_monthly_rate,
            models.InvoiceSetting.storage_monthly_rate,
            models.InvoiceSetting.late_fee_rate,
            models.InvoiceSetting.id,
        )
        .where(models.InvoiceSetting.id == setting_id if setting_id else True)
        .order_by(models.InvoiceSetting.inserted_at.desc())
        .limit(1)
    ).subquery()

    # Previous bill subqueries
    previous_bill_subquery = (
        select(func.sum(models.AccountsReceivable.amount_due))
        .where(
            models.AccountsReceivable.account_id == models.Account.id,
            models.AccountsReceivable.statement_date == previous_month_date,
        )
        .scalar_subquery()
    )

    previous_bill_less_paid_subquery = coalesce(
        select(func.sum(models.AccountsReceivable.amount_due))
        .where(
            models.AccountsReceivable.account_id == models.Account.id,
            models.AccountsReceivable.statement_date == previous_month_date,
            models.AccountsReceivable.paid.is_(False),
            models.AccountsReceivable.charge_type != models.ChargeTypes.LATEFEE,
        )
        .scalar_subquery(),
        0,
    )

    total_amount_due_subquery = (
        select(func.sum(models.AccountsReceivable.amount_due))
        .where(
            models.AccountsReceivable.account_id == models.Account.id,
            models.AccountsReceivable.paid.is_(False),
        )
        .scalar_subquery()
    )

    previous_month_late_fee_post_payments_subquery = (
        select(func.sum(models.AccountsReceivable.amount_due))
        .where(
            models.AccountsReceivable.statement_date == previous_month_date,
            models.AccountsReceivable.charge_type == models.ChargeTypes.LATEFEE,
            models.AccountsReceivable.paid.is_(False),
            models.AccountsReceivable.account_id == models.Account.id,
        )
        .scalar_subquery()
    )

    previous_month_payments_subquery = (
        select(func.sum(models.Payment.amount))
        .where(
            models.Payment.beneficiary_account_id == models.Account.id,
            models.Payment.payment_dated >= previous_month_date,
            models.Payment.payment_dated < statement_date,
        )
        .scalar_subquery()
    )  # what if there are remainder from the months before?

    # Total amount of receivables older than one month before statement_date
    overdue_amount_subquery = (
        select(func.sum(models.AccountsReceivable.amount_due))
        .where(
            models.AccountsReceivable.account_id == models.Account.id,
            models.AccountsReceivable.statement_date < previous_month_date,
            models.AccountsReceivable.paid.is_(False),
        )
        .scalar_subquery()
    )

    unpaid_other_charge_subquery = (
        select(func.sum(models.AccountsReceivable.amount_due))
        .where(
            models.AccountsReceivable.account_id == models.Account.id,
            models.AccountsReceivable.charge_type == models.ChargeTypes.OTHER,
            models.AccountsReceivable.paid.is_(False),
            models.AccountsReceivable.statement_date == statement_date,
        )
        .scalar_subquery()
    )

    notes_subquery = (
        select(text("array_to_string(array_agg(details->>'note'), '; ')"))
        .where(
            models.AccountsReceivable.account_id == models.Account.id,
            models.AccountsReceivable.charge_type == models.ChargeTypes.OTHER,
            models.AccountsReceivable.paid.is_(False),
            models.AccountsReceivable.statement_date == statement_date,
        )
        .scalar_subquery()
    )

    query = (
        select(
            literal(statement_date).label("statement_date"),  # 0
            models.Account.id,
            models.Account.lot_id,
            models.Lot.property_code,
            models.Lot.street_address,
            models.Lot.city_state_zip,
            func.concat(models.Tenant.first_name, " ", models.Tenant.last_name).label(
                "full_name"
            ),
            previous_bill_subquery.label("previous_bill_amount"),
            previous_bill_less_paid_subquery.label("previous_bill_less_paid"),
            total_amount_due_subquery.label("total_amount_due"),
            previous_month_payments_subquery.label("previous_month_payments"),  # 10
            overdue_amount_subquery.label("overdue_amount"),
            unpaid_other_charge_subquery.label("unpaid_other_charge"),
            case(
                (models.Account.lot_id.is_(None), 0),
                (
                    models.Account.rental_rate_override.isnot(None),
                    models.Account.rental_rate_override,
                ),
                else_=invoice_setting_subquery.c.rent_monthly_rate,
            ).label("rent"),
            case(
                (models.Account.storage_count == 0, None),
                else_=invoice_setting_subquery.c.storage_monthly_rate
                * models.Account.storage_count,
            ).label("storage"),
            case(
                (
                    models.WaterUsage.id.isnot(None),
                    (
                        models.WaterUsage.current_reading
                        - models.WaterUsage.previous_reading
                    )
                    * invoice_setting_subquery.c.water_monthly_rate
                    + invoice_setting_subquery.c.water_service_fee,
                ),
                else_=0,
            ).label("water_bill_amount"),
            models.WaterUsage.previous_reading.label("previous_water_reading"),
            models.WaterUsage.current_reading.label("current_water_reading"),
            models.WaterUsage.current_date.label("current_water_date"),
            models.WaterUsage.previous_date.label("previous_water_date"),
            models.WaterMeter.id.label("water_meter_id"),  # 20
            previous_month_late_fee_post_payments_subquery.label("late_fee"),
            invoice_setting_subquery.c.id,
            notes_subquery.label("other_rents_notes"),
        )
        .outerjoin_from(
            models.Account, models.Lot, models.Account.lot_id == models.Lot.id
        )
        .join_from(
            models.Account,
            models.Tenant,
            models.Account.account_holder == models.Tenant.id,
        )
        .outerjoin_from(
            models.Lot, models.WaterMeter, models.Lot.id == models.WaterMeter.lot_id
        )
        .outerjoin_from(
            models.WaterMeter,
            models.WaterUsage,
            (models.WaterMeter.id == models.WaterUsage.watermeter_id)
            & (models.WaterUsage.statement_date == statement_date),
        )
        .where(models.Account.deleted_on.is_(None))
    )

    return query


def get_available_lots_query() -> Select:
    """Retrieve lots that are available for assignment, with water meter information

    Returns:
        Select: A SQLAlchemy `Select` statement for available lots
    """
    return (
        select(models.Lot)
        .outerjoin(models.Account, models.Lot.id == models.Account.lot_id)
        .where(
            and_(
                or_(
                    (models.Account.id.is_(None)), (models.Account.deleted_on.isnot(None))
                ),
                models.Lot.watermeter_id.isnot(None),
            )
        )
        .order_by(models.Lot.property_code, models.Lot.id)
    )


def get_unassigned_people() -> Select:
    """Fetch all tenants without an assigned account

    Returns:
        Select: A SQLAlchemy `Select` statement for unassigned tenants
    """
    return select(models.Tenant).where(models.Tenant.account_id.is_(None))
