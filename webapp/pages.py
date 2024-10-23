import json

import streamlit as st
from pydantic import ValidationError

import data_models as models
from config import AppConfig
import api
import utils


app_config = AppConfig()
host = app_config.host
port = app_config.port

# model

# pages
# 1. manage changes to lot-tenant mapping
# 3. delete account, add new tenant, link new tenant to an account, 
# 4. some kind of undo function

# current status page - filter by, property, lot (or account)
#  - how much is still outstanding as of today, how much was billed the latest
# apply payments, ingest_water_usage_page needs some instructions


def current_payments_status_page():
    ...


def manage_payments_page():
    st.header("Manage Payments")

    def _initialize_state():
        if "input_count" not in st.session_state:
            st.session_state.input_count = 0
        if "accounts" not in st.session_state:
            st.session_state.accounts = api.get_accounts_and_holder()
        if "recent_pmts" not in st.session_state:
            st.session_state.recent_pmts = api.get_recent_payments(
                since=st.session_state.statement_date
            )
        if "see_recent_pmts" not in st.session_state:
            st.session_state.see_recent_pmts = False
        if "rows_to_show" not in st.session_state:
            st.session_state.rows_to_show = 10
        if "filter_pmts_by_since_date" not in st.session_state:
            st.session_state.filter_pmts_by_since_date = False
        if "del_pmt_idx" not in st.session_state:
            st.session_state.del_pmt_idx = []
        if "delete_pmt_trigger" not in st.session_state:
            st.session_state.delete_pmt_trigger = False
        if "delete_confirm" not in st.session_state:
            st.session_state.delete_confirm = False
        if "allow_submission" not in st.session_state:
            st.session_state.allow_submission = False

    _initialize_state()
    st.session_state.see_recent_pmts = st.checkbox(
        "See recently uploaded payments", value=False
    )
    if st.session_state.see_recent_pmts:
        st.session_state.filter_pmts_by_since_date = st.checkbox(
            "Filter payments by date:", value=False
        )
        if st.session_state.filter_pmts_by_since_date: 
            date_filter = st.date_input(
                "See payments recorded since:", value=models.et_date_now()
            )
            st.session_state.recent_pmts = api.get_recent_payments(since=date_filter)
        if st.button("Show more payments", key="show_more_pmts"):
            st.session_state.rows_to_show += 3
        if (
            st.button("Show less payments", key="show_less_pmts")
            and st.session_state.rows_to_show
        ):
            st.session_state.rows_to_show = max(st.session_state.rows_to_show-3, 0)

    if st.session_state.rows_to_show and st.session_state.see_recent_pmts:
        if not st.session_state.recent_pmts:
            st.error("No uploaded payments to show")
        elif not st.session_state.rows_to_show:
            st.info("Click show more payments to see recent payments")
        else:
            st.write("Recently uploaded payments:")
            st.session_state.pmts_df = utils.preview_payments_dataframe(
                payments=st.session_state.recent_pmts,
                acccounts_with_tenant_info=st.session_state.accounts
            )
            st.dataframe(
                st.session_state.pmts_df.head(
                    st.session_state.rows_to_show
                ).iloc[:,1:]
            )

            st.session_state.delete_pmt_trigger = st.checkbox(
                "Select to delete payment(s) from DB"
            )
            if st.session_state.delete_pmt_trigger:
                st.session_state.del_pmt_idx = st.multiselect(
                    'Select the index of the payment(s) to delete:',
                    st.session_state.pmts_df.head(st.session_state.rows_to_show).index
                )
                st.write("Payments to be deleted:")
                selected_rows = st.session_state.pmts_df.loc[
                    st.session_state.del_pmt_idx
                ]
                st.dataframe(selected_rows.iloc[:,1:])

                st.session_state.delete_confirm = st.button("Click to finalize delete")
                if st.session_state.delete_confirm and st.session_state.del_pmt_idx:
                    delete_cnt = 0
                    for i in st.session_state.del_pmt_idx:
                        resp = api.delete_payment(
                            st.session_state.pmts_df.loc[i].id
                        )
                        delete_cnt += 1 if resp.status_code == 204 else 0
                    if delete_cnt:
                        st.write(f"Successfully deleted {delete_cnt} payments")
                    st.session_state.delete_confirm = False
                    st.session_state.del_pmt_idx = []
                    st.session_state.delete_pmt_trigger = False
                    st.session_state.see_recent_pmts = False
                    st.session_state.filter_pmts_by_since_date = False


    #
    st.subheader("Record New Payments:")
    if st.checkbox("Select to record new payments"):
        if st.button("Add more input field"):
            st.session_state.input_count += 1
        if st.button("Remove input field"):
            st.session_state.input_count = max(st.session_state.input_count-1, 0)

        with st.form("form_payment_submit", clear_on_submit=True):
            inputs = []
            for i in range(st.session_state.input_count):
                st.write(f"**Payment #{i+1}**")
                col1, col2 = st.columns(2)
                amount = st.number_input("Payment Amount", min_value=0.0, key=f"amt_{i}")
                beneficiary = st.selectbox(
                    "Select the lot for which this payment is applied",
                    st.session_state.accounts,
                    format_func=lambda x: f"lot_id: {x['lot_id']} - {x['full_name']}",
                    key=f"acct_{i}"
                )
                with col1:
                    st.write("Payer info:")
                    payer_first_name = st.text_input(
                        "First name", key=f"f_name_{i}"
                    )
                    payer_last_name = st.text_input(
                        "Last name", key=f"l_name_{i}"
                    )
                with col2:
                    st.write("Payment dates:")
                    payment_date = st.date_input(
                        "Check dated (YYYY-MM-DD)", key=f"pmt_dt_{i}"
                    )
                    received_date = st.date_input(
                        "Received (YYYY-MM-DD)", key=f"receive_dt_{i}"
                    )
                full_name = f"{payer_first_name} {payer_last_name}"
                inputs.append(
                    [amount, payment_date, received_date, full_name, beneficiary]
                )
            submitted = st.form_submit_button("Submit")

        if submitted and inputs:
            success_counter = 0
            fail_counter = 0
            no_amt_count = 0
            uploadables = []

            for i in inputs:
                if i[0] > 0:
                    payment = models.Payment(
                        beneficiary_account_id=i[-1]["id"],
                        amount=i[0],
                        payment_dated=i[1],
                        payment_received=i[2],
                        payer=i[3]
                    )
                    uploadables.append(payment)
                else:
                    no_amt_count += 1
                    continue

            if utils.duplicate_payment_entry_check(
                uploadables, st.session_state.recent_pmts
            ):
                st.info(
                    """
                        Possible duplicate payment(s) have been found.
                        Are you sure you want to upload the payment(s)?
                    """
                )
                if st.button("Upload payments"):
                    st.session_state.allow_submission = True
            else:
                st.session_state.allow_submission = True

            if st.session_state.allow_submission:
                for i in uploadables:
                    res_add_payment = api.add_new_payment(i)
                    if res_add_payment.status_code == 200:
                        success_counter += 1
                    else:
                        fail_counter += 1
            
            st.session_state.allow_submission = False
            st.session_state.input_count = 0

            if success_counter:
                st.success(f"Successfully uploaded {success_counter} payment(s)")
            if fail_counter:
                st.error(f"Could not upload {fail_counter} payment(s)")
            if no_amt_count:
                st.error(
                    f"Did not upload {no_amt_count} payment(s) with value 0 or less"
                )
    
    #
    st.subheader("Process Payments")
    if st.button("Apply available payments to outstanding receivables"):
        if st.session_state.processing_date:
            st.write(st.session_state.processing_date)
            response_process = api.process_payments(st.session_state.processing_date)
        else:
            response_process = api.process_payments()
        if response_process.status_code == 200:
            counts = json.loads(response_process.content)
            st.success(f"Payments applied to {counts} accounts")
        else:
            st.error("Failed to process payments")


def manage_receivables_page():
    st.header("Manage Receivables")

    def _initialize_state():
        # Recurring receivables
        if "processing_date" not in st.session_state:
            st.session_state["processing_date"] = models.et_date_now()
        if "new_charges" not in st.session_state:
            st.session_state["new_charges"] = False
        if "show_submission_confirm_check" not in st.session_state:
            st.session_state["show_submission_confirm_check"] = False
        if "receivable_df" not in st.session_state:
            st.session_state["receivable_df"] = None
        if "preview_cols" not in st.session_state:
            st.session_state["preview_cols"] = None
        # Water usage
        if "uploaded_file" not in st.session_state:
            st.session_state["uploaded_file"] = None
        if "water_df" not in st.session_state:
            st.session_state["water_df"] = None
        if "water_meter_check" not in st.session_state:
            st.session_state.water_meter_check = False
        # One off charges
        if "input_count_" not in st.session_state:
            st.session_state.input_count_ = 0
        if "accounts" not in st.session_state:
            st.session_state.accounts = api.get_accounts_and_holder()
        if "allow_submission" not in st.session_state:
            st.session_state.allow_submission = False
        if "submitted" not in st.session_state:
            st.session_state.submitted = False

    _initialize_state()

    statement_date = st.session_state.statement_date
    invoice_setting = st.session_state.invoice_setting

    #
    st.subheader("Upload water report")

    st.session_state.uploaded_file = st.file_uploader(
        "Upload the water report Excel file (.xlsx)", type=["xlsx"]
    )
    apicount = 0
    apiresponses = []
    if st.session_state.uploaded_file is not None:
        try:
            st.session_state.water_df = utils.ingest_water_meter_readings(
                st.session_state.uploaded_file
            )
        except AssertionError:
            st.error(
                "Please make sure the date columns are in 'YYYY-MM-DD' format"
            )
            st.stop()
        st.write("Preview of the uploaded file:")
        st.dataframe(st.session_state.water_df)

    if st.session_state.water_df is not None:
        st.session_state.water_usages = utils.generate_water_usage_objects(
            st.session_state.water_df, statement_date
        )
        if type(st.session_state.water_usages[0]) in (str, int):
            st.error(
                f"Please check meter readings for lots {
                    ", ".join(str(i) for i in st.session_state.water_usages)
                }"
            )
            st.session_state.water_meter_check = False
        else:
            st.session_state.water_meter_check = True

        if st.session_state.water_meter_check:
            if st.button("Submit Data"):
                for water_usage in st.session_state.water_usages:
                    res = api.submit_new_wateremeter_readings(reading=water_usage)
                    if res.status_code == 200:
                        apicount += 1
                        apiresponses.append(json.loads(res.content))
                st.write(f"Successfully recorded {apicount} new watermeter readings")

    # Receivables preview and upload
    st.subheader("Create and upload recurring receivables")
    if (
        st.button("See a preview of charges to be created for this billing cycle")
        and invoice_setting
    ):
        st.info(
            f"""
                Breakdown of receivables to be created for the statement period of {
                statement_date
            } and how available payments will be applied
            """
        )
        wu = api.get_water_usages_for_statement_date(statement_date)
        if not wu:
            st.error("No water usages for this statement date to create new charges")

        receivables = api.get_monthly_charges(
            invoice_setting_id=invoice_setting['id'],
            statement_date=statement_date,
            processing_date=st.session_state.processing_date
        )
        accounts = api.get_accounts_and_holder()
        if st.session_state.processing_date:
            payments = api.get_available_payments(
                cut_off_date=st.session_state.processing_date
            )
        else:
            payments = api.get_available_payments()
        st.session_state.receivable_df = utils.preview_charges_dataframe(
            receivables=receivables,
            accounts=accounts,
            payments=payments,
        )
        st.write("Rent, storage, water, and late fees will be recorded, if shown below:")  # to be changed to higlighted
        st.dataframe(
            st.session_state.receivable_df,
            hide_index=True,
            height=35*len(st.session_state.receivable_df)+38,
        )

    if st.button("Record new recurring charges"):
        st.session_state.show_submission_confirm_check = True

    if st.session_state.show_submission_confirm_check:
        st.info("Please review that the new charges to be created are correct")
        if st.checkbox("Are you sure you want to submit?"):
            if st.button("Submit"):
                st.write("Submitting new charges to the database...")
                api_response = api.post_monthly_charges(
                    invoice_setting_id=invoice_setting['id'],
                    statement_date=statement_date,
                    processing_date=st.session_state.processing_date
                )
                if api_response.status_code == 200:
                    cnt = json.loads(api_response.content)
                    st.success(f"{cnt} new charges have been recorded in the database")
                else:
                    st.error("New charges could not be recorded in the database")
                    st.json(api_response.content)
                st.session_state.show_submission_confirm_check = False    


    # Other rent upload
    st.subheader("Create and upload one-off receivables")

    if st.button("Add receivable"):
        st.session_state.input_count_ += 1
    if st.button("Remove receivable"):
        st.session_state.input_count_ -= 1
    
    if st.session_state.input_count_ > 0:
        with st.form("one_off_charge_form"):
            inputs = []
            for i in range(st.session_state.input_count_):
                st.write(f"**New one-off charge #{i+1}**")
                amount_due = st.number_input(
                    "Amount to charge", min_value=0.0, key=f"due_{i}",
                )
                p_account = st.selectbox(
                    "Select the lot for which this payment is applied",
                    st.session_state.accounts,
                    format_func=lambda x: f"lot_id: {x['lot_id']} - {x['full_name']}",
                    key=f"p_acct_{i}"
                )
                rec_detail = st.text_input(
                    "Add brief note about the charge to be created", key=f"r_deet_{i}"
                )
                statement_date = st.date_input(
                    label="Which statement date is this charge for?",
                    value=st.session_state.statement_date,
                    key=f"one_off_{i}"
                )
                paid = st.selectbox(
                    label="Is it paid?",
                    options=[False, True],
                    key=f"is_paid_{i}"
                )
                inputs.append(
                    [amount_due, rec_detail, paid, p_account]
                )
            st.session_state.submitted = st.form_submit_button("Submit")

    if st.session_state.submitted and inputs:
        success_counter = 0
        fail_counter = 0
        no_amt_count = 0
        uploadables = []

        for i in inputs:
            if i[0] > 0:
                receivable = models.AccountsReceivable(
                    account_id=i[-1]["id"],
                    amount_due=i[0],
                    paid=i[2],
                    charge_type=models.ChargeTypes.OTHER,
                    details={"note": i[1]}
                )
                uploadables.append(receivable)
            else:
                no_amt_count += 1
                continue

        other_rents_in_db = api.get_other_rent_receivables()

        if utils.duplicate_accounts_receivable_entry_check(
            uploadables, other_rents_in_db
        ):
            st.info(
                """
                    Possible duplicate receivable(s) have been found.
                    Are you sure you want to upload the receivable(s)?
                """
            )
            if st.button("Upload receivable"):
                st.session_state.allow_submission = True
        else:
            st.session_state.allow_submission = True

        if st.session_state.allow_submission:
            for i in uploadables:
                res_add_rec = api.add_new_receivable(i)
                if res_add_rec.status_code == 200:
                    success_counter += 1
                else:
                    fail_counter += 1
        
        if success_counter:
            st.success(f"Successfully uploaded {success_counter} receivable(s)")
        if fail_counter:
            st.error(f"Could not upload {fail_counter} receivable(s)")
        if no_amt_count:
            st.error(
                f"Did not upload {no_amt_count} receivable(s) with value of 0 or less"
            )

        st.session_state.allow_submission = False
        st.session_state.submitted = False
        


def generate_invoices_page():
    st.header("Process Payments and Generate Invoices")

    def _initialize_state():
        if "invoice_data" not in st.session_state:
            st.session_state["invoice_data"] = []
        if "generate_invoices" not in st.session_state:
            st.session_state.generate_invoices = False
        if "download_triggered" not in st.session_state:
            st.session_state.download_triggered = False
        if "upload_invoice_to_db" not in st.session_state:
            st.session_state.upload_invoice_to_db = True
        
    _initialize_state()
    statement_date = st.session_state.statement_date
    template_path = app_config.template_path
    export_path = app_config.output_path
    invoice_setting = st.session_state.invoice_setting

    i_check = api.get_invoices_for_statement_date(statement_date)
    if i_check: 
        st.info("Invoice for this statement date already in DB")

    w_check = api.get_water_usages_for_statement_date(statement_date)
    if w_check:
        st.success("Water readings in DB for this statement date")
    else:
        st.error("Water readings not found in DB for this statement date")
    
    s_check = api.get_storages_for_statement_date(statement_date)
    if s_check:
        st.success("Storages in DB for this statement date")
    else:
        st.error("Storages not found in DB For this statement_date")

    r_check = api.get_rents_for_statement_date(statement_date)
    if r_check:
        st.success("Rents in DB for this statement date")
    else:
        st.error("Rents not found in DB for this statement date")

    o_check = api.get_other_rent_receivables(statement_date)
    if o_check:
        st.info(f"{len(o_check)} other rents found in DB for this statement date")
    else:
        st.info("No other rents found in DB for this statement date")
    

    st.subheader("Generate invoice")

    st.session_state.generate_invoices = st.button("Generate invoices")
    st.session_state.upload_invoice_to_db = st.checkbox("Update database", value=True)

    if st.session_state.generate_invoices:
        utils.clear_directory(export_path)
        try:
            raw = api.get_invoice_data(
                statement_date=statement_date,
                setting_id=invoice_setting['id'],
                update_db=st.session_state.upload_invoice_to_db
            )
        except json.JSONDecodeError:
            st.error("Check if the receivables for the statement date is in the DB")
            return

        st.session_state.invoice_data = [
            models.InvoiceFileParse(**i) for i in raw if i
        ]
        file_paths = utils.generate_invoices(
            template_path=template_path,
            input_data=st.session_state.invoice_data,
            export_path=export_path,
        )
        st.write(f"Generated {len(file_paths)} invoice(s)")
        utils.user_download_invoice_zip(export_path)


def accounts_management_page():
    st.header("Manage accounts and database")

    def _initialize_state():
        if "add_setting" not in st.session_state:
            st.session_state.add_setting = False
        if "add_tenant" not in st.session_state:
            st.session_state.add_tenant = False
        if "accounts_in_db" not in st.session_state:
            st.session_state.accounts_in_db = api.get_accounts_and_holder()
        if "add_account" not in st.session_state:
            st.session_state.add_account = False
        if "manage_account" not in st.session_state:
            st.session_state.manage_account = False
        if "account_to_change" not in st.session_state:
            st.session_state.account_to_change = False
        if "del_acct_trigger" not in st.session_state:
            st.session_state.del_acct_trigger = False
        if "del_acct_confirm" not in st.session_state:
            st.session_state.del_acct_confirm = False
        if "chg_acct_deet_trigger" not in st.session_state:
            st.session_state.chg_acct_deet_trigger = False
        if "tenant_submitted" not in st.session_state:
            st.session_state.tenant_submitted = False

    _initialize_state()
    st.subheader("Add a new invoice setting")
    st.session_state.add_setting = st.checkbox(
        "Select to add a new invoice setting", value=False
    )

    if st.session_state.add_setting:
        with st.form("create_invoice_setting", clear_on_submit=True):
            rent_monthly_rate = st.number_input(
                label="Enter monthly rental rate",
                value=st.session_state.invoice_setting["rent_monthly_rate"],
                help="Enter dollar amount, per month",
                min_value=0
            )
            water_monthly_rate = st.number_input(
                label="Enter monthly water bill rate per gallon",
                value=st.session_state.invoice_setting["water_monthly_rate"],
                help="Enter dollar amount, per water usage unit.",
                min_value=0.0,
                max_value=0.9,
                step=1e-6,
                format="%.6f"
            )
            water_service_fee = st.number_input(
                label="Enter monthly water bill service fee",
                value=st.session_state.invoice_setting["water_service_fee"],
                help="Enter dollar amount per month.",
                min_value=0.0
            )
            storage_monthly_rate = st.number_input(
                label="Enter monthly storage rate",
                value=st.session_state.invoice_setting["storage_monthly_rate"],
                help="Enter dollar amount per month.",
                min_value=0
            )
            late_fee_rate = st.number_input(
                label="Enter late fee percentage rate (in decimals)",
                value=st.session_state.invoice_setting["late_fee_rate"],
                help="E.g. Enter 0.05, if the late fee is 5%.",
                min_value=0.0
            )
            overdue_cutoff_days = st.number_input(
                label="Enter number of days for grace period until invoice is \
                    considered overdue",
                value=st.session_state.invoice_setting["overdue_cutoff_days"],
                help="E.g. Enter 10, if the 10th of each month is the last day \
                    of the grace period.",
                min_value=0
            )
            effective_as_of = st.date_input(
                label="Enter the first statement date this setting becomes \
                    effective for invoicing",
                value=st.session_state.statement_date,
            )

            setting_submitted = st.form_submit_button("Submit")

        if setting_submitted:
            try:
                new_setting = models.InvoiceSetting.model_validate(
                    {
                        "rent_monthly_rate": rent_monthly_rate,
                        "water_monthly_rate": water_monthly_rate,
                        "water_service_fee": water_service_fee,
                        "storage_monthly_rate": storage_monthly_rate,
                        "late_fee_rate": late_fee_rate,
                        "overdue_cutoff_days": overdue_cutoff_days,
                        "effective_as_of": effective_as_of
                    }
                )
                new_setting_response = api.submit_new_invoice_setting(new_setting)
                if new_setting_response.status_code == 200:
                    st.success("New setting was successfully uploaded")
                else:
                    st.error("New setting failed to upload")

            except ValidationError:
                st.error(
                    "New setting could not be constructed properly.\
                    Please check values."
                )

            st.session_state.add_setting = False


    #
    st.subheader("Open a new account")
    st.session_state.add_account = st.checkbox(
        "Select to open a new account", value=False
    )

    if st.session_state.add_account:
        st.session_state.lots = api.get_available_lots()
        st.session_state.potential_tenants = api.get_unassigned_people()

        if not st.session_state.lots:
            st.info("There are no available lots to assign to an account")

        with st.form("add_account_form", clear_on_submit=True):
            lot_id = st.selectbox(
                label="Select an available lot to assign to this account",
                options=st.session_state.lots,
                format_func=lambda x: x["id"],
                help="""
                    If you would like to assign a lot to a new account, use the\
                    database management tool to remove a lot from another account\
                    or delete an active account.
                """
            )
            account_holder = st.selectbox(
                label="Select a person to assign to this account",
                options=st.session_state.potential_tenants,
                format_func=lambda x: f"{x["first_name"]} {x["last_name"]}",
                help="""
                    If the person for this account is not listed, add the person\
                    by using the 'Add a new tenant' section.
                """
            )
            bill_preference = st.selectbox(
                label="Select the billing preference for this account",
                options=[preference.value for preference in models.BillPreference],
                index=[
                    preference for preference in models.BillPreference
                ].index(models.BillPreference.NO_PREFENCE)
            )
            rental_rate_override = st.number_input(
                label="Enter monthly rent ONLY IF DIFFERENT from others'",
                value=None,
                min_value=0
            )
            storage_count = st.number_input(
                label="Enter number of storage(s) assigned to this account",
                value=0,
                min_value=0
            )
            submit_account = st.form_submit_button("Submit account")
        
        if submit_account:
            try:
                if lot_id:
                    lot = lot_id["id"]
                else:
                    lot = None
                new_account = models.Account.model_validate(
                    {
                        "lot_id": lot,
                        "account_holder": account_holder["id"],
                        "bill_preference": bill_preference,
                        "rental_rate_override": rental_rate_override,
                        "storage_count": storage_count
                    }
                )
                new_acct_resp = api.add_new_account(new_account)
                if new_acct_resp.status_code == 200:
                    st.success("New account was successfully uploaded")
                else:
                    st.error("New account failed to upload")

            except ValidationError:
                st.error(
                    "New account could not be constructed properly. Please check\
                    values."
                )

            st.session_state.add_account = False


    #
    st.subheader("Manage an account's details")
    st.session_state.manage_account = st.checkbox(
        "Select to update account details", value=False
    )

    if st.session_state.manage_account:
        st.session_state.account_to_change = st.selectbox(
            "Select the account to update",
            options=st.session_state.accounts_in_db,
            format_func=lambda x: (
                f"lot_id: {x['lot_id'] if x['lot_id'] else 'n/a'} - {x['full_name']}"
                if x is not None else None
            ),
            index=None
        )

        st.session_state.del_acct_trigger = st.checkbox(
            "Delete this account", value=False
        )
        if st.session_state.del_acct_trigger:
            st.session_state.del_acct_confirm = st.button("Confirm to delete")
            if st.session_state.del_acct_confirm:
                resp = api.delete_account(st.session_state.account_to_change["id"])
                if resp.content["ok"]:
                    st.success("The account is now deleted")
                else:
                    st.error("Failed to delete account")
        
        # st.checkbox("Assign lot to an account")
        # st.checkbox("Assign tenant to an account")
        # st.checkbox("Remove tenant from an account")

    #
    st.subheader("Add a new tenant")
    st.session_state.add_tenant = st.checkbox(
        "Select to add a new tenant", value=False
    )

    if st.session_state.add_tenant:
        st.session_state.tenant_submitted = False

        with st.form("create_a_new_tenant", clear_on_submit=True):
            first_name = st.text_input(label="Enter the tenant's first name")
            last_name = st.text_input(label="Enter the tenant's last name")
            acct_assignment = st.selectbox(
                label="Assign tenant to an account?",
                options=[None]+st.session_state.accounts_in_db,
                format_func=lambda x: (
                    f"lot_id: {x['lot_id'] if x['lot_id'] else 'n/a'}-{x['full_name']}"
                    if x is not None else None
                ),
                index=0
            )
            st.session_state.tenant_submitted = st.form_submit_button("Add this tenant")

    if st.session_state.tenant_submitted:
        try:
            new_tenant = models.Tenant.model_validate(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "account_id": acct_assignment["id"] if acct_assignment else None
                }
            )
            new_tenant_response = api.submit_new_tenant(new_tenant)
            if new_tenant_response.status_code == 200:
                st.success(
                    f"New tenant {first_name} {last_name} was successfully\
                    uploaded"
                )
            else:
                st.error("New tenant failed to upload")

        except ValidationError:
            st.error("Tenant could not be constructed properly. Please check values.")
        
        st.session_state.add_tenant = False
