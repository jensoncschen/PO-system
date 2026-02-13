import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (精簡後台版)", layout="wide", page_icon="🛍️")

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 快取機制 ---
@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        df_cust = conn.read(worksheet="客戶資料")
        df_prod = conn.read(worksheet="產品資料")
        df_sales = conn.read(worksheet="業務資料") 
        df_order = conn.read(worksheet="訂單紀錄")
        
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        
        return df_cust, df_prod, df_sales, df_order
    except Exception as e:
        return None, None, None, None

# --- 側邊欄 ---
st.sidebar.title("☁️ 系統導航")
if st.sidebar.button("🔄 強制更新資料"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "🔧 後台：資料管理"])
st.sidebar.markdown("---")
st.sidebar.caption("v10.0 | 純雲端維護版")

# 載入資料
df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.error("⚠️ Google 連線忙碌中，請稍候再按側邊欄的更新按鈕。")
    st.stop()

# --- 初始化 Session State ---
if 'cart_list' not in st.session_state:
    st.session_state.cart_list = []

# ==========================================
# 🛒 前台：下單作業 (維持不變)
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🛒 業務下單專區")
    
    # --- 1. 基本資訊 ---
    with st.container():
        col_sales, col_cust, col_date = st.columns(3)
        with col_sales:
            sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
            selected_sales_name = st.selectbox(
                "👤 承辦業務", sales_list, index=None, placeholder="請選擇業務員..."
            )
        with col_cust:
            cust_list = df_customers["客戶名稱"].unique().tolist() if not df_customers.empty else []
            selected_cust_name = st.selectbox(
                "🏢 客戶名稱", cust_list, index=None, placeholder="請輸入關鍵字搜尋..."
            )
        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 2. 產品列表 ---
    st.subheader("📦 產品訂購")

    col_filter, col_search = st.columns([1, 2])
    
    base_df = df_products.copy()
    base_df["訂購數量"] = 0
    base_df["搭贈數量"] = 0

    with col_filter:
        all_brands = df_products["品牌"].unique().tolist() if "品牌" in df_products.columns else []
        selected_brands = st.multiselect("🏷️ 品牌篩選", all_brands, placeholder="預設顯示全部...")

    with col_search:
        filtered_for_search = base_df.copy()
        if selected_brands:
            filtered_for_search = filtered_for_search[filtered_for_search["品牌"].isin(selected_brands)]
        product_list = filtered_for_search["產品名稱"].unique().tolist()
        search_product_name = st.selectbox(
            "🔍 精準搜尋", product_list, index=None, placeholder="搜尋特定產品..."
        )

    # --- 顯示邏輯 ---
    editors_data = {} 

    if search_product_name:
        st.info(f"📍 已鎖定產品：{search_product_name}")
        target_df = base_df[base_df["產品名稱"] == search_product_name].copy()
        edited_df = st.data_editor(
            target_df[["產品名稱", "訂購數量", "搭贈數量"]],
            column_config={
                "產品名稱": st.column_config.TextColumn(disabled=True, width="large"),
                "訂購數量": st.column_config.NumberColumn(min_value=0, step=1),
                "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1)
            },
            use_container_width=True,
            hide_index=True,
            key="editor_single_search"
        )
        editors_data["search"] = edited_df

    else:
        brands_to_show = selected_brands if selected_brands else all_brands
        if not brands_to_show:
            st.warning("沒有可顯示的產品品牌。")
        else:
            for brand in brands_to_show:
                brand_df = base_df[base_df["品牌"] == brand].copy()
                if not brand_df.empty:
                    with st.expander(f"🏷️ {brand} ({len(brand_df)} 項產品)", expanded=True):
                        edited_brand_df = st.data_editor(
                            brand_df[["產品名稱", "訂購數量", "搭贈數量"]],
                            column_config={
                                "產品名稱": st.column_config.TextColumn(disabled=True),
                                "訂購數量": st.column_config.NumberColumn(min_value=0, step=1),
                                "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1)
                            },
                            use_container_width=True,
                            hide_index=True,
                            key=f"editor_{brand}"
                        )
                        editors_data[brand] = edited_brand_df

    # --- 3. 加入購物車 ---
    total_items_selected = 0
    all_selected_rows = []

    for key, df_result in editors_data.items():
        selected = df_result[ (df_result["訂購數量"] > 0) | (df_result["搭贈數量"] > 0) ]
        if not selected.empty:
            all_selected_rows.append(selected)
            total_items_selected += len(selected)

    if total_items_selected > 0:
        st.markdown("---")
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.success(f"⚡ 已選擇 {total_items_selected} 項產品")
            
        with col_btn:
            if not selected_cust_name or not selected_sales_name:
                st.error("⚠️ 請先選擇「業務」與「客戶」")
            else:
                if st.button("⬇️ 全部加入購物車", type="primary", use_container_width=True):
                    for df_chunk in all_selected_rows:
                        for _, row in df_chunk.iterrows():
                            p_name = row["產品名稱"]
                            qty = row["訂購數量"]
                            gift_qty = row["搭贈數量"]
                            original_product = df_products[df_products["產品名稱"]