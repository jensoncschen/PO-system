import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (側邊快捷版)", layout="wide", page_icon="🛍️")

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 輔助函式：ID 清洗工具 ---
def clean_id_str(val):
    s = str(val).strip()
    if s.endswith(".0"):
        return s[:-2]
    return s

# --- 快取機制 ---
@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        df_cust = conn.read(worksheet="客戶資料")
        df_prod = conn.read(worksheet="產品資料")
        df_sales = conn.read(worksheet="業務資料") 
        df_order = conn.read(worksheet="訂單紀錄")
        
        # 防呆
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        if "業務名稱" not in df_cust.columns: df_cust["業務名稱"] = ""
        
        # 清洗資料
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        
        return df_cust, df_prod, df_sales, df_order
    except Exception as e:
        return None, None, None, None

# --- 載入資料 ---
df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.error("⚠️ Google 連線忙碌中，請稍候再按側邊欄的更新按鈕。")
    st.stop()

# --- 初始化 Session State ---
if 'cart_list' not in st.session_state:
    st.session_state.cart_list = []

# --- 側邊欄：上方導航區 ---
st.sidebar.title("☁️ 系統導航")
if st.sidebar.button("🔄 強制更新資料", key="btn_update_data"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "🔧 後台：資料管理"])
st.sidebar.markdown("---")

# ==========================================
# 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🛒 業務下單專區")
    
    # --- 1. 基本資訊 ---
    with st.container():
        col_sales, col_cust, col_date = st.columns(3)
        
        # A. 選擇業務
        with col_sales:
            sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
            selected_sales_name = st.selectbox(
                "👤 承辦業務", sales_list, index=None, placeholder="請先選擇業務員..."
            )

        # B. 選擇客戶
        with col_cust:
            current_cust_list = []
            placeholder_text = "請先選擇業務員..."
            
            if selected_sales_name:
                filtered_cust_df = df_customers[df_customers["業務名稱"] == selected_sales_name]
                current_cust_list = filtered_cust_df["客戶名稱"].unique().tolist()
                if not current_cust_list:
                    placeholder_text = f"⚠️ {selected_sales_name} 名下無客戶"
                else:
                    placeholder_text = "請選擇客戶..."
            
            selected_cust_name = st.selectbox(
                "🏢 客戶名稱", 
                current_cust_list, 
                index=None, 
                placeholder=placeholder_text
            )

        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 定義送出訂單的核心邏輯 (讓側邊欄與主畫面共用) ---
    def submit_order_logic():
        # 1. 檢查必要欄位
        if not selected_cust_name or not selected_sales_name:
            st.error("⚠️ 無法送出：請確認已選擇「業務」與「客戶」")
            return
        
        if len(st.session_state.cart_list) == 0:
            st.error("⚠️ 購物車是空的")
            return

        with st.spinner("正在處理訂單資料..."):
            # 讀取最新歷史紀錄
            current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
            if "BillNo" not in current_history.columns: current_history["BillNo"] = ""

            # 產生 PersonID (2碼)
            sales_row = df_salespeople[df_salespeople["業務名稱"] == selected_sales_name]
            if not sales_row.empty:
                raw_val = sales_row.iloc