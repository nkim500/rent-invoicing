import json

import data_models as models
import streamlit as st
from api import get_invoice_settings
from api import get_properties
from pages import accounts_management_page
from pages import generate_invoice_from_book
from pages import generate_invoices_page
from pages import manage_payments_page
from pages import manage_receivables_page
from utils import invoice_setting_widget
from utils import properties_widget
from utils import statement_date_widget


def initialize_state():
    st.set_page_config(layout="wide")
    if "dev_mode" not in st.session_state:
        st.session_state["dev_mode"] = False
    if "processing_date" not in st.session_state:
        st.session_state["processing_date"] = models.et_date_now()
    if "statement_date" not in st.session_state:
        st.session_state["statement_date"] = None
    if "invoice_settings" not in st.session_state:
        st.session_state["invoice_settings"] = []
    if "invoice_setting" not in st.session_state:
        st.session_state.invoice_setting = None
    # if "invoice_setting_index" not in st.session_state:
    #     st.session_state.invoice_setting_index = None
    if "props" not in st.session_state:
        st.session_state.props = None
    if "prop" not in st.session_state:
        st.session_state.prop = None


initialize_state()

try:
    st.session_state.invoice_settings = sorted(
        get_invoice_settings(), key=lambda x: x["inserted_at"], reverse=True
    )
except json.JSONDecodeError:
    st.error("No monthly rates in DB. Add them using the DB modification page")
    # st.stop()

try:
    st.session_state.props = get_properties()
except json.JSONDecodeError:
    st.error("No properties listed in DB. Add them using the DB modification page")

statement_date_widget()

invoice_setting_widget(st.session_state.invoice_settings)

properties_widget(st.session_state.props)

st.session_state.dev_mode = st.sidebar.checkbox(
    label="Manually set the processing date", value=False
)

if st.session_state.dev_mode:
    st.session_state.processing_date = st.sidebar.date_input(
        label="Select the date processing data", value=models.et_date_now()
    )


def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        [
            "Manage Payments",
            "Manage Receivables",
            "Generate Invoices",
            "Generate Invoices from Book",
            "Accounts and DB Management",
        ],
    )

    if page == "Manage Payments":
        manage_payments_page()
    elif page == "Manage Receivables":
        manage_receivables_page()
    elif page == "Generate Invoices":
        generate_invoices_page()
    elif page == "Generate Invoices from Book":
        generate_invoice_from_book()
    elif page == "Accounts and DB Management":
        accounts_management_page()


if __name__ == "__main__":
    main()
