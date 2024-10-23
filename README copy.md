# Streamlit Rent Management Application

This Streamlit app is designed to manage payments, charge receivables, generate monthly rent bills, and perform other account management tasks.

The app integrates with a locally-hosted FastAPI backend and PostgreSQL database to facilitate tasks on frontend

# Table of Contents
- [Installation](#installation)
- [How to Use](#how-to-use)
    - [Initializing](#initializing)
    - [Manage Payments Page](#manage-payments)
    - [View Recent Payments](#view-recent-payments)
    - [Add New Payments](#add-new-payments)
    - [Process Payments](#process-payments)
- [Manage Receivables Page](#manage-receivables)
- [Generate Invoices Page](#generate-invoices)
- [Accounts and DB Management Page](#accounts_and_db_management)


# Installation
Pre-requisite installations on the user machine:
- Docker (download link here)
- Python 3.12 (download link here)

Clone this repository to local directory, by typing the following command in git-enabled bash:

    `git clone https://github.com/nkim500/rent-invoicing.git`

File named *.env* with following variables is required in the same directory:

```bash
# Below for PostgreSQL DB access
DB_USER={username}
DB_PASSWORD={password}
DB_HOST=billing_db
DB_PORT=5432
DB_NAME=postgres

# Below to access API endpoints
HOST=http://billing_service
PORT=8001

# Below company information to display on invoices
BUSINESS_NAME={company_name_with_underscores_replacing_spaces}
BUSINESS_ADDRESS_1={street_address}
BUSINESS_ADDRESS_2={city,_state,_zip_code}
BUSINESS_CONTACT_PHONE={contact_number}
BUSINESS_CONTACT_EMAIL={contact_email_address}

# Below in-container directory to store invoice files
OUTPUT_PATH=invoices/

# Below local directory to locate invoice template Excel file
TEMPLATE_PATH=template/bill_template.xlsx
```

After the steps above, navigate to the local repository in bash and type command `docker compose up` to build the Docker containers

- User should see three containers build: `billing_console`, `billing_service`, `billing_db`

- After the initial build, if the applicatoin is shut down, user can restart the application (a) with the `docker compose up` command or (b) by pressing the play (▶️) button shown next to `rent_invoicing` under Containers & Apps in Docker Desktop application

# How to Use

Streamlit user interface will be available at http://localhost:8501 by default.

If the webpage does not render, please check whether the Docker containers are operational, by typing `docker ps` in bash.

## Initializing

Below are list of data inputs required to intialize this service. User can perform these tasks via Streamlit or Python script.

- **Insert Data**, in the following order *(if initializing via Streamlit)*
    - **Invoice Settings**: Define and insert invoicing configuration applied to all accounts
    - **Property**: Insert the main property information
    - **Water Meters**: Insert initial water meters
    - **Lots**: Insert initial lots *(linked to the water meters)*
    - **Tenants**: Add new tenants
    - **Accounts**: Create new accounts *(linked to the lots and tenants)*

- If initializing via Python, subsequently, update relationships
   - Assign water meters to lots with `app.utilities.queries.update_tenant_account_id`
   - Assign tenants to accounts with `app.utilities.queries.update_watermeter_lot_id`

Note:
- **Invoice Settings** will configure the invoicing behavior.
    - The application assumes a billing cycle of one month, with the invoice coming due on the first of every statement month. 
    - The "overdue..." attribute will dictate when an invoice has gone past the grace period and has become overdue, which is on the 11th day of the statement month, by default (grace period can be revised)
    - The "effective as of" attribute will help autofill the invoice setting value in the app
    - The other fees and rates will be used in receivables calculation
        - If **Accounts** has any value in rental_rate_override attribute, it will over ride the monthly rental rate from the invoice setting in rental rate calculation


## Layout Overview

The invoice setting and statement date displayed will persist across various pages.

Selected values for them will be used in the functions. When the statement date changes, selected invoice setting will automatically change to the most recent configuration with the effective-as-of date before the set statement date. If the automatically set invoice setting is not correct, user should manually change the invoice setting as well. 

"Manually set the processing date", if checked, will request user for date input. This date input will configure the application to perform tasks as if they were done on the input date. For example, if processing date is manually set to 2024/01/01, the invoices will be generated as if it was made on January 1, 2024.

## Manage Payments Page

### View Recent Payments

- You can view recently uploaded payments by checking the box labeled `See recently uploaded payments`.
- If you filter payments by date, payments inserted since the filter date will show
- You can also view the desired number of payments using the `Show more payments` and `Show less payments` buttons.
- If you wish to delete a payment, select it by index and confirm your selection before deletion.

### Add New Payments

- To add a new payment, click on the checkbox `Select to record new payments`.
- Input payment details for each entry (amount, payer info, and payment dates), and submit the form when done.
- If there are duplicate payments or entries with a zero amount, appropriate warnings or errors will be displayed.
- If there is a payment with the same amount and beneficiary account and date already recorded, user will be asked to confirm the new submission before being able to actually record to avoid erroneous uploads.

### Process Payments

- Click on the `Process payments` button to use available payments to 'pay off' outstanding receivables of respective accounts.


## Manage Receivables Page

### 1. Water Report Upload
User can upload the monthly water meter readings by completing the template found in `webapp/template/water_report_template.xlsx`. The column headers containing dates should be updated to reflect the start and end dates for the meter readings.

### 2. Recurring Receivables
Utility (i.e. water), storage, rent, and late fee receivables are assumed to be incurred on a monthly basis. This means that if there are receivables in the database with the same statement date.

Currently, having the water usages for the statement date in the database is a pre-requisite to create the monthly recurring charges. For recording water usage, please see the report upload function in *1. Water Report Upload* above. 

If new monthly charges can be created for the statement date , **Charges Preview** will show rent, storage, water, and late fees columns based on account data.

Once the user **Submit Charges** and confirms submission, new recurring charges will be recorded in the database.

Note, that late fees are only incurred for the receivable's statement date and will not compound monthly. The basis for late fee calculation is the difference between the statement date's new receivables and available payment amounts for respective accounts, when the invoice has become overdue. 


### 3. One-off Receivables
Users can create one-off receivables ("other rent") for specific accounts. The details of these charges will be listed on the invoice. 

If there is a one-off receivable for a matching account, statement date, and amount already recorded in the database, the user will be prompted to confirm that the new entry is not a duplicate entry.


# Generate Invoices Page

This page in the Streamlit application is responsible for processing payments and generating invoices for various accounts.

## Key Functions

### 1. Data Checks
Before generating invoices, the page checks for the existence of related data, including the monthly charges, for the statement date:
- **Invoice Check**: Verifies if invoices for the selected statement date already exist in the database.
- **Water Usages**: Checks for the presence of water usage readings.
- **Storage**: Checks if storage charges have been recorded.
- **Rents**: Ensures that rent information is present in the database.
- **Other Rents**: Identifies if other one-off rent charges are in the database.
The invoice can be generated if all three of water usage, storage and rent for the statement date exist in the databae

### 2. Invoice Generation
- **Generate Invoices Button** will trigger the invoices to be generated inside the Docker container.
- If **Update Database** is selected, the application will also record with newly generated invoices to the database.

When invoices are generated, user will be provided with an option to download the generated invoices in a zip file to the user's local machine.


# Accounts and DB Management Page

This page in the Streamlit application contains functionalities for other administrative tasks such as managing accounts, tenants, and invoice settings in the database.

## Key Functions

### 1. Add a New Invoice Setting
- **Add Setting**: Allows user to add a new invoice setting
### 2. Open a New Account
- **Add Account**: Allows users to add a new account. If there are no lot options available to assign to a new account, user will either need to unassign a lot from an existing account or delete an existing account. If the user does not see the tenant to be assigned to a new account, the user will need to add the tenant first
### 3. Manage Account Details
- **Manage Account**: Allows the user to choose an account to update from a list of existing accounts.
- **Delete Account**: If selected, the user can delete the selected account. A confirmation is required before the deletion is processed.

### 4. Add a New Tenant
- **Add Tenant**: Allows the user to add new tenant