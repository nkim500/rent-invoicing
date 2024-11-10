from collections import defaultdict
from datetime import date
from datetime import timedelta
from typing import List
from uuid import UUID

import utilities.data_models as models
import utilities.queries as queries
from configs.config import DBConfigs
from configs.config import build_connection_string
from configs.config import get_logger
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel import create_engine
from utilities.data_transformation import filter_for_new_items
from utilities.data_transformation import incur_late_fee
from utilities.data_transformation import incur_recurring_charges
from utilities.data_transformation import process_accounts_receivables
from utilities.data_transformation import serialize_invoice_input_data_row

logger = get_logger()
db_cfg = DBConfigs()
uri = build_connection_string(db_cfg)
engine = create_engine(uri)
app = FastAPI()


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(bind=engine, checkfirst=True)


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/watermeter")
def submit_new_watermeter_readings(
    reading: models.WaterUsage,
    session: Session = Depends(get_session),
) -> dict | None:
    """Adds a new water usage record to the database

    Args:
        reading (models.WaterUsage): Validated WaterUsage record
        session (Session, optional): Database session, managed by dependency injection

    Raises:
        e: _description_

    Returns:
        dict | None: {"ok": True} if the record was successfully added; raises on failure

    Raises:
        Exception: If an error occurs during the database transaction
    """
    try:
        logger.debug(f"Parsed reading: {reading.model_dump()}")
        session.add(reading)
        session.commit()
        session.refresh(reading)
        return {"ok": True}
    except Exception as e:
        session.rollback()
        raise e


@app.put("/watermeter/{watermeter_id}")
def update_watermeter_lot_id(
    watermeter_id: int, lot_id: str, session: Session = Depends(get_session)
) -> dict:
    q = queries.update_watermeter_lot_id_query(watermeter_id=watermeter_id, lot_id=lot_id)
    session.exec(q)
    session.commit()
    return {"ok": True}


@app.get("/accounts/")
def get_accounts(
    with_tenant_info: bool = False,
    active_only: bool = True,
    session: Session = Depends(get_session),
) -> list[dict] | list[models.Account]:
    if with_tenant_info:
        query = queries.get_accounts_query(
            with_tenant_info=with_tenant_info, active_only=active_only
        )
        response = session.exec(query).all()
        accounts = [{"id": r[0], "lot_id": r[1], "full_name": r[2]} for r in response]
    else:
        query = queries.get_accounts_query(active_only=active_only)
        accounts = session.exec(query).all()
    return accounts


@app.post("/accounts")
def add_new_account(
    account: models.Account, session: Session = Depends(get_session)
) -> dict | None:
    try:
        session.add(account)
        session.commit()
        session.refresh(account)
        return {"ok": True}
    except Exception as e:
        session.rollback()
        raise e


@app.put("/accounts/{account_id}")
def delete_account(account_id: UUID, session: Session = Depends(get_session)) -> dict:
    account = session.get(models.Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.deleted_on = models.et_datetime_now()
    account.lot_id = None
    session.commit()
    return {"ok": True}


def get_receivables_for_statement_date(
    statement_date: date, session: Session
) -> list[models.AccountsReceivable]:
    q = queries.get_receivables_query(statement_date=statement_date)
    return session.exec(q).all()


def get_the_receivable(
    ar_id: UUID | str, session: Session
) -> models.AccountsReceivable | None:
    if isinstance(ar_id, str):
        ar_id = UUID(ar_id)
    q = queries.get_a_receivable_query(ar_id)
    return session.exec(q).one_or_none()


@app.get("/receivables/unpaid", response_model=List[models.AccountsReceivable])
def get_unpaid_receivables(
    account_id: UUID | None = None,
    statement_date: date | None = None,
    processing_date: date | None = None,
    session: Session = Depends(get_session),
) -> list[models.AccountsReceivable]:
    if account_id:
        q = queries.get_unpaid_items_query(
            account_id=account_id,
            statement_date=statement_date,
            processing_date=processing_date,
        )
    else:
        q = queries.get_all_unpaid_items_query(
            statement_date=statement_date, processing_date=processing_date
        )
    return session.exec(q).all()


@app.get("/receivables/other_rent", response_model=List[models.AccountsReceivable])
def get_other_rent_receivables(
    account_id: UUID | None = None,
    statement_date: date | None = None,
    session: Session = Depends(get_session),
) -> list[models.AccountsReceivable]:
    if account_id or statement_date:
        q = queries.get_other_rents_query(
            account_id=account_id, statement_date=statement_date
        )
    else:
        q = queries.get_other_rents_query()
    return session.exec(q).all()


@app.get("/receivables/overdue", response_model=List[models.AccountsReceivable])
def get_new_overdue_receivables(
    current_date: date,
    invoice_setting_id: UUID | None = None,
    session: Session = Depends(get_session),
) -> list[models.AccountsReceivable]:
    if invoice_setting_id:
        q_settings = queries.get_invoice_setting_query(invoice_setting_id)
        setting = session.exec(q_settings).one()
    else:
        setting = models.InvoiceSetting()
    days = setting.overdue_cutoff_days
    q = queries.get_receivables_without_late_fees_query(
        current_date=current_date, days=days
    )
    return session.exec(q).all()


@app.get("/receivables/rents")
def get_rents(
    statement_date: date | None = Query(None), session: Session = Depends(get_session)
) -> list[models.AccountsReceivable | None]:
    q = queries.get_receivable_by_charge_type_query(
        statement_date=statement_date, charge_type=models.ChargeTypes.RENT
    )
    rents = session.exec(q).all()
    return rents


@app.get("/receivables/storages")
def get_storages(
    statement_date: date | None = Query(None), session: Session = Depends(get_session)
) -> list[models.AccountsReceivable | None]:
    q = queries.get_receivable_by_charge_type_query(
        statement_date=statement_date, charge_type=models.ChargeTypes.STORAGE
    )
    storages = session.exec(q).all()
    return storages


@app.post("/receivables")
def submit_new_receivable(
    receivable: models.AccountsReceivable, session: Session = Depends(get_session)
) -> models.AccountsReceivable | None:
    try:
        session.add(receivable)
        session.commit()
        session.refresh(receivable)
        return receivable
    except Exception as e:
        session.rollback()
        raise e


@app.get("/available_payments", response_model=List[models.Payment])
def get_available_payments(
    account_id: UUID | None = None,
    processing_date: date | None = None,
    session: Session = Depends(get_session),
) -> list[models.Payment]:
    q = queries.get_available_payments_query(account_id, processing_date)
    return session.exec(q).all()


@app.get("/payments", response_model=List[models.Payment])
def get_recent_payments(
    since_when: date | None = None,
    processing_date: date | None = None,
    session: Session = Depends(get_session),
):
    if processing_date:
        query = queries.get_available_payments_query(processing_date=processing_date)
    else:
        query = queries.get_recent_payments_query(since_when=since_when)

    payments = session.exec(query).all()
    return payments


@app.post("/payments")
def submit_new_payment(
    payment: models.Payment, session: Session = Depends(get_session)
) -> models.Payment:
    try:
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return payment
    except Exception as e:
        session.rollback()
        raise e


@app.delete("/payments/{payment_id}", status_code=204)
def delete_payment(payment_id: UUID, session: Session = Depends(get_session)):
    payment = session.get(models.Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    session.delete(payment)
    session.commit()


def apply_payments_for_an_account(
    session: Session,
    account_id: UUID,
    processing_date: date | None = None,
    write_mode: bool = True,
):
    try:
        available_payments = get_available_payments(
            account_id=account_id, processing_date=processing_date, session=session
        )
        original_receivables = get_unpaid_receivables(
            account_id=account_id, processing_date=processing_date, session=session
        )

        residual, not_paid, partial_paid, full_paid = process_accounts_receivables(
            accounts_receivables=original_receivables, payments=available_payments
        )

        if write_mode:
            if len(residual) == 1:
                session.add(residual[0])
                session.commit()
            if full_paid + partial_paid:
                for i in full_paid + partial_paid:
                    logger.debug(
                        f"{len(full_paid+partial_paid)} charges to be marked as paid."
                    )
                    ar = get_the_receivable(ar_id=i.id, session=session)
                    ar.paid = True
                    session.add(ar)
                session.commit()
            return 1
        else:
            return residual, not_paid, partial_paid, full_paid

    except Exception as e:
        logger.error(f"Error occurred while processing payments:\t{e}")
        raise e


def apply_payments_for_all(
    session: Session, processing_date: date | None = None, write_mode: bool = True
) -> int:
    q = queries.get_accounts_query(active_only=True)
    accts = session.exec(q).all()
    ids = [i.id for i in accts]
    try:
        ids[0]
    except IndexError:
        logger.error("No active account found")
        return

    count = 0
    output = {}
    if write_mode:
        for id in ids:
            apply_payments_for_an_account(session, id, processing_date, write_mode)
            count += 1
        return count
    else:
        for id in ids:
            residual, not_paid, partial_paid, _ = apply_payments_for_an_account(
                session, id, processing_date, write_mode
            )
            output[id] = [residual, not_paid, partial_paid]
        return output


@app.post("/processing/process_payments/")
def process_payments_api(
    account_id: UUID | None = None,
    statement_date: date | None = None,
    processing_date: date | None = None,
    session: Session = Depends(get_session),
    write_mode: bool = True,
) -> None | int:
    if not statement_date:
        statement_date = date.today().replace(day=1)
    if account_id:
        apply_payments_for_an_account(session, account_id, processing_date, write_mode)
    else:
        count = apply_payments_for_all(session, processing_date, write_mode)
    return count


@app.get("/settings", response_model=List[models.InvoiceSetting])
def get_invoice_setting(
    setting_id: UUID | str | None = None, session: Session = Depends(get_session)
) -> list[models.InvoiceSetting]:
    if setting_id is None:
        query = queries.get_invoice_settings_query()
        settings = session.exec(query).all()
        return settings

    elif isinstance(setting_id, str):
        setting_id = UUID(setting_id)

    query = queries.get_invoice_setting_query(setting_id=setting_id)
    settings = session.exec(query).one_or_none()
    return settings


@app.post("/settings")
def submit_new_invoice_setting(
    setting: models.InvoiceSetting, session: Session = Depends(get_session)
) -> models.InvoiceSetting:
    """
    Adds a new invoice setting to the database

    Args:
        setting (models.InvoiceSetting): Validated invoice setting details
        session (Session): Database session, managed by dependency injection

    Returns:
        models.InvoiceSetting: The saved invoice setting with updated information
    """
    try:
        session.add(setting)
        session.commit()
        session.refresh(setting)
        return setting
    except Exception as e:
        session.rollback()
        raise e


@app.get("/tenants", response_model=models.Tenant)
def get_tenant(
    tenant_id: UUID | None = None, session: Session = Depends(get_session)
) -> models.Tenant:
    if tenant_id:
        query = queries.get_tenant_query(tenant_id)
        tenants = session.exec(query).one()
    else:
        query = queries.get_tenants_query()
        tenants = session.exec(query).all()
    return tenants


@app.get("/unassigned_people")
def get_unassigned_people(
    session: Session = Depends(get_session),
) -> list[models.Tenant | None]:
    query = queries.get_unassigned_people()
    tenants = session.exec(query).all()
    return tenants


@app.post("/tenants", response_model=models.Tenant)
def add_new_tenant(
    tenant: models.Tenant, session: Session = Depends(get_session)
) -> models.Tenant:
    try:
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        return tenant
    except Exception as e:
        session.rollback()
        raise e


@app.put("/tenants/{tenant_id}")
def update_tenant_account_id(
    tenant_id: UUID, account_id: UUID, session: Session = Depends(get_session)
) -> None:
    q = queries.update_tenant_account_id_query(tenant_id=tenant_id, account_id=account_id)
    session.exec(q)
    session.commit()
    return {"ok": True}


@app.get("/water_usages")
def get_water_usages_for_statement_date(
    statement_date: date = Query(...),
    session: Session = Depends(get_session),
    json_mode: bool = False,
):
    query = queries.get_water_usage_query(statement_date)
    water_usages = session.exec(query).all()
    if not len(water_usages):
        return []

    if json_mode:
        water_usages = [(str(i[0]), i[1].model_dump(mode="json")) for i in water_usages]
    return water_usages


def get_receivables_by_charge_type(
    charge_type: models.ChargeTypes,
    statement_date: date | None = None,
    processing_date: date | None = None,
    is_paid: bool | None = None,
    session: Session = Depends(get_session),
) -> list[models.AccountsReceivable]:
    q = queries.get_receivable_by_charge_type_query(
        charge_type=charge_type,
        statement_date=statement_date,
        processing_date=processing_date,
        is_paid=is_paid,
    )
    return session.exec(q).all()


def incur_new_charges(
    charge_type: models.ChargeTypes,
    accounts: list[models.Account],
    setting: models.InvoiceSetting,
    statement_date: date,
    processing_date: date,
    session: Session = Depends(get_session),
) -> list[models.AccountsReceivable | None]:
    if (
        charge_type == models.ChargeTypes.RENT
        or charge_type == models.ChargeTypes.STORAGE
    ):
        return incur_recurring_charges(
            input_list=accounts,
            charge_type=charge_type,
            statement_date=statement_date,
            config=setting,
        )
    elif charge_type == models.ChargeTypes.WATER:
        water_usages = get_water_usages_for_statement_date(
            statement_date=statement_date, session=session, json_mode=False
        )
        if not water_usages:
            logger.debug(f"No water usages found for statement date {statement_date}")
            return
        else:
            return incur_recurring_charges(
                input_list=water_usages,
                charge_type=charge_type,
                statement_date=statement_date,
                config=setting,
            )
    elif charge_type == models.ChargeTypes.LATEFEE:
        base_charge_types = [
            models.ChargeTypes.RENT,
            models.ChargeTypes.STORAGE,
            models.ChargeTypes.WATER,
        ]
        if processing_date >= statement_date + timedelta(
            days=setting.overdue_cutoff_days
        ):
            rent_in_db = get_receivables_by_charge_type(
                charge_type=models.ChargeTypes.RENT,
                statement_date=statement_date,
                processing_date=processing_date,
                session=session,
            )
            if not rent_in_db:
                initially_overdues = []
                for charge_type in base_charge_types:
                    if charge_type == models.ChargeTypes.WATER:
                        input_list = get_water_usages_for_statement_date(
                            statement_date=statement_date,
                            session=session,
                            json_mode=False,
                        )
                    else:
                        input_list = accounts
                    initially_overdues += incur_recurring_charges(
                        input_list=input_list,
                        charge_type=charge_type,
                        statement_date=statement_date,
                        config=setting,
                    )
            else:
                initially_overdues = get_new_overdue_receivables(
                    current_date=processing_date,
                    invoice_setting_id=setting.id,
                    session=session,
                )
        else:
            return []
        late_fees = []
        for acct in accounts:
            pmts = get_available_payments(
                account_id=acct.id,
                processing_date=statement_date
                + timedelta(setting.overdue_cutoff_days - 1),
                session=session,
            )

            for i in pmts:
                session.expunge(i)

            initially_overdue_for_acct = [
                i for i in initially_overdues if i.account_id == acct.id
            ]
            late_fees += incur_late_fee(
                overdue_items=initially_overdue_for_acct,
                config=setting,
                statement_date=statement_date,
                processing_date=processing_date,
                payments=pmts,
            )

        return late_fees


def _get_receivables_or_incur_new_charges(
    charge_type: models.ChargeTypes,
    accounts: list[models.Account],
    setting: models.InvoiceSetting,
    statement_date: date,
    processing_date: date,
    session: Session = Depends(get_session),
) -> list[models.AccountsReceivable]:
    charges = get_receivables_by_charge_type(
        charge_type=charge_type,
        statement_date=statement_date,
        processing_date=None,
        is_paid=None,
        session=session,
    )
    if not charges:
        charges = incur_new_charges(
            charge_type=charge_type,
            accounts=accounts,
            setting=setting,
            statement_date=statement_date,
            processing_date=processing_date,
            session=session,
        )
    return charges


def get_receivables_or_incur_new_charges(
    accounts: list[models.Account],
    setting: models.InvoiceSetting,
    statement_date: date,
    processing_date: date,
    session: Session = Depends(get_session),
) -> dict:
    ars = {}
    for i in models.ChargeTypes:
        ars[i] = _get_receivables_or_incur_new_charges(
            charge_type=i,
            accounts=accounts,
            setting=setting,
            statement_date=statement_date,
            processing_date=processing_date,
            session=session,
        )
    return ars


@app.get("/monthly_charges")
def get_monthly_charges(
    invoice_setting_id: UUID | str,
    statement_date: date,
    processing_date: date | None = None,
    session: Session = Depends(get_session),
    write_mode: bool = False,
) -> dict:
    if not processing_date:
        processing_date = models.et_date_now()

    setting = get_invoice_setting(setting_id=invoice_setting_id, session=session)
    accounts = get_accounts(with_tenant_info=False, active_only=True, session=session)
    receivables_in_db = get_receivables_for_statement_date(
        statement_date=statement_date, session=session
    )
    stmt_receivables = get_receivables_or_incur_new_charges(
        accounts=accounts,
        setting=setting,
        statement_date=statement_date,
        processing_date=processing_date,
        session=session,
    )
    new_rents, new_storages, new_late_fees, new_waters = filter_for_new_items(
        outstanding=receivables_in_db,
        rents=stmt_receivables[models.ChargeTypes.RENT],
        storages=stmt_receivables[models.ChargeTypes.STORAGE],
        new_late_fees=stmt_receivables[models.ChargeTypes.LATEFEE],
        waters=stmt_receivables[models.ChargeTypes.WATER],
    )

    if write_mode:
        return new_rents, new_storages, new_late_fees, new_waters
    else:
        new_dict = defaultdict(list)
        for receivables in [new_rents, new_storages, new_late_fees, new_waters]:
            if receivables:
                for item in receivables:
                    new_dict[item.account_id].append(item)
        new_outs = dict(new_dict)

        in_db_dict = defaultdict(list)
        for item in receivables_in_db:
            in_db_dict[item.account_id].append(item)
        in_db_outs = dict(in_db_dict)

        return {
            key: (new_outs.get(key, []), in_db_outs.get(key, []))
            for key in set(new_outs) | set(in_db_outs)
        }


@app.post("/monthly_charges")
def add_monthly_charges(
    invoice_setting_id: UUID | str,
    statement_date: date,
    processing_date: date | None = None,
    session: Session = Depends(get_session),
) -> int:
    if not processing_date:
        processing_date = models.et_date_now()

    rents, storages, new_late_fees, waters = get_monthly_charges(
        invoice_setting_id=invoice_setting_id,
        statement_date=statement_date,
        processing_date=processing_date,
        session=session,
        write_mode=True,
    )
    try:
        new_charges_count = sum(
            [len(rents), len(storages), len(new_late_fees), len(waters)]
        )
        session.bulk_insert_mappings(models.AccountsReceivable, rents)
        session.bulk_insert_mappings(models.AccountsReceivable, storages)
        session.bulk_insert_mappings(models.AccountsReceivable, new_late_fees)
        if waters:
            session.bulk_insert_mappings(models.AccountsReceivable, waters)
        session.commit()
        return new_charges_count
    except TypeError:
        return {"ERROR": {"msg": "Check if water usages are updated"}}


@app.get("/invoice")
def get_existing_invoices(
    statement_date: date = Query(...),
    invoice_setting_id: UUID | None = Query(None),
    session: Session = Depends(get_session),
) -> list:
    q = queries.get_existing_invoice_query(
        statement_date=statement_date, setting_id=invoice_setting_id
    )
    invoices = session.exec(q).all()

    return invoices


@app.get("/invoice/input_data")
def get_invoice_inputs_data(
    statement_date: date = Query(...),
    invoice_setting_id: str | None = Query(None),
    update_db: bool = False,
    session: Session = Depends(get_session),
) -> list[dict | None]:
    existing_invoices = get_existing_invoices(
        statement_date=statement_date,
        invoice_setting_id=invoice_setting_id,
        session=session,
    )
    if len(existing_invoices) > 0:
        results_from_db = [
            serialize_invoice_input_data_row(inv.details) for inv in existing_invoices
        ]
        return results_from_db

    if isinstance(invoice_setting_id, str):
        invoice_setting_id = UUID(invoice_setting_id)

    inputs_base_q = queries.get_invoice_input_data_query(
        statement_date=statement_date,
        setting_id=invoice_setting_id,
    )
    inputs = session.exec(inputs_base_q).all()

    results = [serialize_invoice_input_data_row(row) for row in inputs]

    if update_db:
        invoices = [
            serialize_invoice_input_data_row(row, as_invoice_object=True)
            for row in inputs
            if row is not None
        ]
        session.add_all(invoices)
        session.commit()

    return results


@app.get("/lots/available")
def get_available_lots(session: Session = Depends(get_session)):
    q = queries.get_available_lots_query()
    available_lots = session.exec(q).all()
    return available_lots
