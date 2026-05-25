import streamlit as st
from streamlit_gsheets import GSheetsConnection

from pages_app.admin_page import render_admin_page
from pages_app.export_page import render_export_page
from pages_app.order_page import render_order_page
from services.data_service import fetch_all_data
from ui.components import load_css, render_sidebar


# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統", layout="wide")

# --- CSS：Phase 2 樣式模組化 ---
load_css("ui/styles.css")

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 讀取基礎資料 ---
df_customers, df_products, df_salespeople = fetch_all_data(conn)

if df_customers is None:
    st.stop()

# 建立全域產品查表字典
global_prod_dict = df_products.drop_duplicates(subset=["產品名稱"]).set_index("產品名稱").to_dict("index")

# --- Session State ---
if "cart_list" not in st.session_state:
    st.session_state.cart_list = []
if "input_reset_trigger" not in st.session_state:
    st.session_state.input_reset_trigger = 0
if "form_reset_trigger" not in st.session_state:
    st.session_state.form_reset_trigger = 0

# --- 左側快捷區 ---
page = render_sidebar()

if page == "前台下單":
    render_order_page(conn, df_customers, df_products, df_salespeople, global_prod_dict)
elif page == "訂單匯出":
    render_export_page(conn)
elif page == "後台管理":
    render_admin_page()
