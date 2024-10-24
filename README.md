# Streamlit Rent Management Application

This app enables managing payments, charge receivables, generating monthly rent bills, and performing various account management tasks. It utilizes Streamlit user interface integrated with a locally-hosted FastAPI backend and PostgreSQL database.

## Table of Contents
- [Installation](#installation)
- [How to Use](#how-to-use)
  - [Initializing](#initializing)
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


### Initializing

To initialize the service, following data must be input (recommended to follow the order shown below). This can be done via Streamlit or a Python script:

1. **Invoice Settings**: Configure invoicing rules.
2. **Property**: Input property information.
3. **Water Meters**: Add initial water meters.
4. **Lots**: Add lots and link them to water meters.
5. **Tenants**: Create tenant profiles.
6. **Accounts**: Set up accounts linked to tenants and lots.

After the above steps, if initializing via Python, relationships between entities can be updated using these utility functions:

- Assign water meters to lots:  
  `app.utilities.queries.update_tenant_account_id`
- Assign tenants to accounts:  
  `app.utilities.queries.update_watermeter_lot_id`

#### Note:
- **Invoice Settings** dictate the billing cycle and fees. The billing cycle defaults to one month, with invoices due on the 1st of each month.
- The **overdue cut off days** attribute determines when an invoice becomes overdue (default is 10 days after the statement date).
- The **effective as of** date helps autofill the correct invoice settings for a given statement date.
- If any, values in **rental rate override** attribute of **Accounts** will take precedent over the default monthly rent in the invoice settings for monthly rent calculation.

### Manage Payments
![payments page](https://github.com/user-attachments/assets/9fc38706-c672-4b9d-9954-62e06e9180ae)
#### View Recent Payments

- Check the box labeled "See recently uploaded payments" to view payments.
- Filter payments by date to show entries from a specific period.
- Adjust the number of displayed payments with "Show more" or "Show less" buttons.
- Select a payment and confirm deletion if needed.

#### Add New Payments

- Check the "Select to record new payments" box to input new payments.
- Submit payment details (amount, payer info, dates).
- Number of payments for submission can be increased.
- For payments matching an existing entry (based on amount, date, account), confirmation will be required.
- Error is displayed for attempting to submit any payments with amount set to 0.

#### Process Payments

- Use the "Process payments" button to use available payments for outstanding receivables.

### Manage Receivables
![receivables page](https://private-user-images.githubusercontent.com/86082214/379459923-bc8442a2-81b9-4030-9de2-a91d75f7a442.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Mjk3MTcwODMsIm5iZiI6MTcyOTcxNjc4MywicGF0aCI6Ii84NjA4MjIxNC8zNzk0NTk5MjMtYmM4NDQyYTItODFiOS00MDMwLTlkZTItYTkxZDc1ZjdhNDQyLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNDEwMjMlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjQxMDIzVDIwNTMwM1omWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTY3NGM1ZDY2ZTgxNTdkOWQ4MzJhNjdhOWVkOTA1NDY2YTU5Zjg5OTI5NDZmZjhkZGM4OWE1NTI2ZDUyOTNlNDImWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.S_sRv_kJDF_bcPVYRiJJVQDzpTOcs9WPS59eAVx_H94)
#### Water Report Upload

- Upload monthly water meter readings by filling in the `template/water_report_template.xlsx` file. Make sure the column headers reflect the correct date ranges.

#### Recurring Receivables

- Monthly charges for rent, water, storage, and late fees are calculated and shown when selecting *See a preview of charges to be created for this billing cycle*, if they have not already been for the statement date. 

- Currently, **water usage report must be uploaded for the statement date to generate recurring charges**.

#### One-off Receivables

- Create one-off charges ("other rent") that will appear on invoices, by clicking on *Add receivable*. Confirm to avoid duplicating charges. 

### Generate Invoices
![invoice page](https://private-user-images.githubusercontent.com/86082214/379460061-8a47ea24-0723-47a0-9876-6160d7a62a09.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Mjk3MTc0NTgsIm5iZiI6MTcyOTcxNzE1OCwicGF0aCI6Ii84NjA4MjIxNC8zNzk0NjAwNjEtOGE0N2VhMjQtMDcyMy00N2EwLTk4NzYtNjE2MGQ3YTYyYTA5LnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNDEwMjMlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjQxMDIzVDIwNTkxOFomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPWM0NmNmZDZjOGYxMGE0YWY1NTk4Njg5NjYzNzFmNWVhMDQ2ZGIxMWI5NDUyYjg4OTkyODk1NTU2MTYwYWZkZTgmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.WFsOX-FLhCa4Mga6eqq29W_axdR8l-UljQ8xHI65iBA)

This page will note if monthly charges for the statement date exists before generating invoices. This page will also note if the invoice for the statement date already exists

#### Generate Invoices

- "Generate Invoices" will create .xlsx files in the `billing_console` container and selecting "Update Database" will record the invoice details to the database when the files are created.

- After the invoices are created, user will be shown an option to download them as a .zip file.

### Accounts and DB Management
![account mgmt page](https://private-user-images.githubusercontent.com/86082214/379460199-66a67a3c-d42c-45db-bdf8-49d9a36b9ba0.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Mjk3MTc0NTgsIm5iZiI6MTcyOTcxNzE1OCwicGF0aCI6Ii84NjA4MjIxNC8zNzk0NjAxOTktNjZhNjdhM2MtZDQyYy00NWRiLWJkZjgtNDlkOWEzNmI5YmEwLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNDEwMjMlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjQxMDIzVDIwNTkxOFomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTAxNmUxMTUyMzU1MGRiY2JkODdhODMwMGYwOWYzMWQ4ZDQzZGRlMDVhNTdlZDkyYzI4YjdjNGE3MjdhNmNkYTMmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.Wkq50LYwp-_tcV-kxSN44wrTlFxpJvm2ei3bxdyVauA)
#### Add a New Invoice Setting

- Allows users to configure new invoice settings.

#### Open a New Account

- Opens a new account. Ensure that available lots and tenants are present before creating an account.

#### Manage Account Details

- Manage or delete existing accounts, with confirmation required for deletions.

#### Add a New Tenant

- Add new tenants to the system.