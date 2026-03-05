import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
import traceback
import io 

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (條碼快搜版)", layout="wide", page_icon="🛍️")

# --- CSS 優化 ---
st.markdown("""
    <style>
    div[data-testid="stNumberInput"] input {
        font-size: 20px !important;
        height: 50px !important;
        text-align: center !important;
        font-weight: bold;
    }
    div.stButton > button {
        height: 55px !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 12px;
    }
    div.stButton > button[kind="primary"] {
        background-color: #28a745;
        border-color: #28a745;
    }
    hr { margin-top: 0.5rem; margin-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 🛠️ 核心輔助函式
# ==========================================
def get_sales_id_2digits(sales_name, df_sales):
    if not sales_name: return "00"
    sales_row = df_sales[df_sales["業務名稱"] == sales_name]
    if sales_row.empty: return "00"
    
    raw_val = sales_row.iloc[0]["業務編號"]
    try:
        return f"{int(float(raw_val)):02d}"
    except:
        return str(raw_val).strip().zfill(2)[-2:]

def clean_barcode(val):
    s = str(val).strip() 
    if s.endswith('.0'): 
        s = s[:-2]
    if s.lower() in ['nan', 'none', '']:
        return ''
    return s

# --- 快取機制 ---
@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        df_cust = conn.read(worksheet="客戶資料")
        df_prod = conn.read(worksheet="產品資料")
        df_sales = conn.read(worksheet="業務資料") 
        df_order = conn.read(worksheet="訂單紀錄")
        
        for df in [df_cust, df_sales, df_prod, df_order]:
            if df is None: return None, None, None, None
            
        df_cust.columns = df_cust.columns.str.strip()
        df_prod.columns = df_prod.columns.str.strip()
        df_sales.columns = df_sales.columns.str.strip()
        df_order.columns = df_order.columns.str.strip()
            
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "品類" not in df_prod.columns: df_prod["品類"] = "一般"
        if "國際條碼" not in df_prod.columns: df_prod["國際條碼"] = ""
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        df_order["BillNo"] = df_order["BillNo"].astype(str).str.replace("'", "", regex=False)
        df_prod["品類"] = df_prod["品類"].fillna("一般")
        
        df_prod["國際條碼"] = df_prod["國際條碼"].apply(clean_barcode)
        
        return df_cust, df_prod, df_sales, df_order
        
    except Exception as e:
        st.error(f"⚠️ 資料庫連線異常，錯誤原因：{e}")
        print(traceback.format_exc())
        return None, None, None, None

df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.stop()

# --- Session State ---
if 'cart_list' not in st.session_state: st.session_state.cart_list = []
if 'input_reset_trigger' not in st.session_state: st.session_state.input_reset_trigger = 0
if 'form_reset_trigger' not in st.session_state: st.session_state.form_reset_trigger = 0

# --- 左側導航 ---
st.sidebar.title("☁️ 系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "📥 訂單匯出", "🔧 後台：資料管理"])
st.sidebar.markdown("---")

st.sidebar.markdown("### 🛒 購物車狀態")
cart_len = len(st.session_state.cart_list)
if cart_len > 0:
    st.sidebar.success(f"已加入 {cart_len} 筆商品")
    st.sidebar.dataframe(pd.DataFrame(st.session_state.cart_list)[["產品名稱","訂購數量"]], hide_index=True)
    if st.sidebar.button("🗑️ 清空購物車"):
        st.session_state.cart_list = []
        st.rerun()
else:
    st.sidebar.info("購物車是空的")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 強制更新雲端資料"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 🚀 1. 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🚀 快速下單系統")

    form_suffix = f"_{st.session_state.form_reset_trigger}"

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            sales_list = df_salespeople["業務名稱"].unique().tolist()
            selected_sales_name = st.selectbox(
                "👤 業務", sales_list, index=None, placeholder="選擇業務...", key=f"sales_sb{form_suffix}"
            )
        with c2:
            current_cust = []
            if selected_sales_name:
                current_cust = df_customers[df_customers["業務名稱"]==selected_sales_name]["客戶名稱"].unique().tolist()
            selected_cust_name = st.selectbox(
                "🏢 客戶", current_cust, index=None, placeholder="選擇客戶...", key=f"cust_sb{form_suffix}"
            )
        
        order_date = st.date_input("📅 日期", datetime.now())

    st.divider()

    st.subheader("➕ 新增商品")
    input_suffix = f"_{st.session_state.input_reset_trigger}"

    # --- 📷 條碼快搜區 ---
    st.markdown("#### 📷 步驟一：條碼快搜 (支援條碼槍或輸入部分數字)")
    barcode_input = st.text_input(
        "輸入部分條碼、完整條碼，或商品名稱關鍵字後按 Enter", 
        placeholder="例如輸入 12345 尋找條碼，或輸入 iPhone...",
        key=f"barcode_scan{input_suffix}"
    )

    st.markdown("