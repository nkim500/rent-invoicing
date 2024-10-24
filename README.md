# Streamlit Rent Management Application

This app enables managing payments, charge receivables, generating monthly rent bills, and performing various account management tasks. It utilizes Streamlit user interface integrated with a locally-hosted FastAPI backend and PostgreSQL database.

## Table of Contents
- [Installation](#installation)
- [How to Use](#how-to-use)
  - [Initializing](#initializing)
  - [UI Overview](#ui-overview)
  - [Manage Payments](#manage-payments)
    - [View Recent Payments](#view-recent-payments)
    - [Add New Payments](#add-new-payments)
    - [Process Payments](#process-payments)
  - [Manage Receivables](#manage-receivables)
    - [Water Report Upload](#water-report-upload)
    - [Recurring Receivables](#recurring-receivables)
    - [One-off Receivables](#one-off-receivables)
  - [Generate Invoices](#generate-invoices)
  - [Accounts and DB Management](#accounts-and-db-management)

## Installation

Pre-requisites:
- Docker
- Python 3.12

To install the app:

1. Clone the repository:
   ```
   git clone https://github.com/nkim500/rent-invoicing.git
   ```

2. Create a `.env` file in the root directory with the following variables:

    ```bash
    # PostgreSQL DB access
    DB_USER={username}
    DB_PASSWORD={password}
    DB_HOST=billing_db
    DB_PORT=5432
    DB_NAME=postgres
    # API access
    HOST=http://billing_service
    PORT=8001
    # Company info for invoices
    BUSINESS_NAME={company_name_with_underscores_replacing_spaces}
    BUSINESS_ADDRESS_1={street_address}
    BUSINESS_ADDRESS_2={city,_state,_zip_code}
    BUSINESS_CONTACT_PHONE={contact_number}
    BUSINESS_CONTACT_EMAIL={contact_email_address}
    # Directories
    OUTPUT_PATH=invoices/
    TEMPLATE_PATH=template/bill_template.xlsx
    ```

3. Navigate to the project directory and run:
   ```
   docker compose up
   ```

Once the containers are built, the app can be restarted using `docker compose up` or via Docker Desktop.

## How to Use

The Streamlit UI is available at [http://localhost:8501](http://localhost:8501). If it doesn’t load, verify Docker containers are running with `docker ps`

---
### Initializing

To initialize the service, following data must be input (recommended to follow the order shown below). This can be done via Streamlit or a Python script:
1. **Invoice Settings**: Configure invoicing rules.
2. **Property**: Input property information.
3. **Water Meters**: Add initial water meters.
4. **Lots**: Add lots and link them to water meters.
5. **Tenants**: Create tenant profiles.
6. **Accounts**: Set up accounts linked to tenants and lots.

After the above steps, if initializing via Python, relationships between entities can be updated using these utility functions:

- Assign water meters to lots `app.utilities.queries.update_tenant_account_id`
- Assign tenants to accounts `app.utilities.queries.update_watermeter_lot_id`
---
### UI Overview:
![ui overview](https://i.imgur.com/yK69tR6.png)

All pages in the application will be configured for the statement date selected in ${\color{red}\large⓵}$ **Statement Date** and calculate invoices using the values shown in ${\color{red}\large⓶}$ **Invoice Setting**. 

- The latter also dictates the monthly billing cycles (payments due on the 1st of each month + 10 day grace period by default)

- Depending on each invoice setting's *effective as of* date value, the user session's invoice setting may auto-align with changes to the session's statement date.

- [*For development*] User can ${\color{red}(a)}$ **Manually set the processing date** to perform tasks on the application as if it was being done on another date than today

---

### Manage Payments
![payments page](https://i.imgur.com/K1ecT37.png)

#### ${\color{blue}\large⓵}$ View Recent Payments

- ![preview_payments](https://i.imgur.com/ZZyxae0.png)

- Check the box labeled "See recently uploaded payments" to view payments.

- Filter payments by date to show entries made since a specified date.

- Delete payment(s) as needed by selecting the desired indices.

#### ${\color{blue}\large⓶}$ Add New Payments

- ![add_payments](https://i.imgur.com/aabmtm4.png)

- Check the "Select to record new payments" box to input new payments.

- Submit payment details (amount, payer info, dates).

- Number of payments for submission can be increased.

- For payments matching an existing entry (based on amount, date, account), confirmation will be required.

- Error is displayed for attempting to submit any payments with amount set to 0.

#### ${\color{blue}\large⓷}$ Process Payments

- ![process_payments](https://i.imgur.com/RFospHm.png)

- Use the "Process payments" button to use available payments for outstanding receivables.

---

### Manage Receivables

Manage Receivables page will show three main functions as shown:

![receivables page](https://imgur.com/irLQAkr.png)

#### ${\color{red}\large⓵}$ Water Report Upload

- Upload monthly water meter readings using the `template/water_report_template.xlsx` file.

- ![water_upload_bad](https://imgur.com/WPiT4E2.png)

- Ensure the column headers reflect the correct date ranges.

- Ensure the report does not have rows with empty readings or rows with previous reading larger than current reading.

- ![water_upload_good](https://imgur.com/CVBRFR1.png)

- Note, the session statement date is set to October 2024, so these water meter readings will be recorded for October 2024 invoice.

#### ${\color{red}\large⓶}$ Recurring Receivables

- ![recurring_receivables](https://imgur.com/8rNZO3n.png)

- Monthly charges for rent, water, storage, and late fees are calculated and shown when selecting **See a preview of charges to be created for this billing cycle**, if they have not already been for the statement date. 

- **Water meter readings for the statement date must be uploaded first to create recurring charges altogether**.

- **Late fee** will appear if the invoices have become overdue, based on the user's processing date (today, by default) and statement date.

- Click **Record new recurring charges** to create them in the database for invoicing

#### ${\color{red}\large⓷}$ One-off Receivables

- ![one_off_charges](https://imgur.com/5O071Sr.png)

- Create one-off charges ("other rent"), by clicking on *Add receivable* and filling in the relevant details.

- User will be prompted to confirm that the new entry is not a duplicate, if possible duplicate entry is detected. 

---

### Generate Invoices

![invoice page](https://i.imgur.com/LP2GtvK.png)

#### ${\color{blue}\large⓵}$ Status Check

- When user opens the Generate Invoices page, the page will indicate whether the necessary data components are recorded in the database for the session's statement date.

#### ${\color{blue}\large⓶}$ Generate Invoices

- If the monthly water, storage and rent charges for the statement date are in the database, user can generate the invoices.

- Create invoices files in .xlsx format by clicking **Generate Invoices**.

- By default, **Update Database** is selected to record the invoice details to the database when the invoice files are created.

- ![invoice_download](https://imgur.com/VVDs2PZ.png)

- After the invoices are created, user will be shown an option to download them to local directory as a .zip file.

---

### Accounts and DB Management

![account mgmt page](https://imgur.com/DC6jSI9.png)

#### ${\color{red}\large⓵}$ Add a New Invoice Setting

- ![add_setting](https://imgur.com/BT5tYDr.png)

- The second to last user input referring to **number of days for grace period** defaults to 10 days.
    - i.e. Unpaid October 1, 2024 invoices created here will be overdue starting October 11, 2024.

- The last user input item referring to **first effective statement date** date helps autofill the correct invoice settings for a given statement date.

#### ${\color{red}\large⓶}$ Open a New Account

![add_account](https://imgur.com/FbuHXGn.png)

- All payments and receivables in this application are attributed to an account.

- Create a new account by filling in the form and submitting to the database.
    - Lot assignment is optional.

- Input values for the first two items **available lots** and **person to assign** will not list any possible options if there are none available. User may consider to create new entities or unlink them from existing accounts to make options available.

- Any inputs to **Enter monthly rent ONLY IF DIFFERENT FROM others'** will take precedent over the default monthly rent in the invoice settings for the new account's monthly rent calculation.

#### ${\color{red}\large⓷}$ Manage Account Details

![delete_account](https://imgur.com/oyBAHiv.png)

- Delete an existing account by selecting from the drop down menu.

#### ${\color{red}\large④}$ Add a New Tenant
![add_tenant](https://imgur.com/kOdCEN0.png)

- Add new tenants by filling in the form.
    - Account assignment is optional.