import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (簡潔版)", layout="wide", page_icon="☁️")

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # 讀取四個分頁：新增了 '業務資料'
        df_cust = conn.read(worksheet="客戶資料", ttl=0)
        df_prod = conn.read(worksheet="產品資料", ttl=0)
        df_sales = conn.read(worksheet="業務資料", ttl=0) # 新增
        df_order = conn.read(worksheet="訂單紀錄", ttl=0)
        
        # 確保欄位存在 (防呆)
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        
        return df_cust, df_prod, df_sales, df_order
    except Exception as e:
        st.error(f"資料讀取錯誤，請確認 Google Sheet 是否有 '業務資料' 分頁。\n錯誤訊息: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# 載入資料
df_customers, df_products, df_salespeople, df_order_history = load_data()

# --- 初始化 Session State ---
if 'cart_list' not in st.session_state:
    st.session_state.cart_list = []

# --- 側邊欄導航 ---
st.sidebar.title("☁️ 系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "🔧 後台：資料管理"])
st.sidebar.markdown("---")
st.sidebar.caption("v5.0 | 極簡介面版")

if df_customers.empty or df_products.empty:
    st.warning("⚠️ 讀取不到資料，請檢查 Google Sheet 設定。")
    st.stop()

# ==========================================
# 🛒 前台：下單作業 (極簡顯示)
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🛒 業務下單專區")
    
    # --- 1. 基本資訊 (只顯示名稱) ---
    with st.container():
        col_sales, col_cust, col_date = st.columns(3)
        
        with col_sales:
            # 【需求2】建立業務資料，只顯示名稱
            # 製作名稱清單
            sales_list = df_salespeople["業務名稱"].unique().tolist()
            selected_sales_name = st.selectbox("👤 承辦業務", sales_list)

        with col_cust:
            # 【需求3】客戶資料只顯示名稱
            cust_list = df_customers["客戶名稱"].unique().tolist()
            selected_cust_name = st.selectbox("🏢 客戶名稱", cust_list)

        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 2. 產品列表 (只顯示名稱與數量) ---
    st.subheader("📦 產品訂購")

    # 搜尋功能
    search_term = st.text_input("🔍 搜尋產品名稱", placeholder="輸入關鍵字...")
    
    # 準備顯示資料
    # 【需求4】只顯示產品名稱與數量
    display_df = df_products.copy()
    
    if search_term:
        display_df = display_df[display_df["產品名稱"].astype(str).str.contains(search_term, case=False)]

    # 為了讓使用者輸入，我們建立一個包含「產品名稱」和「訂購數量」的表
    # 注意：這裡我們暫時隱藏 ID，送出時再反查
    display_df = display_df[["產品名稱"]].copy() 
    display_df["訂購數量"] = 0

    # 互動表格
    edited_df = st.data_editor(
        display_df,
        column_config={
            "產品名稱": st.column_config.TextColumn(disabled=True, width="large"), # 鎖定名稱不可改
            "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="請輸入數量")
        },
        use_container_width=True,
        hide_index=True,
        key="product_simple_editor"
    )

    # --- 3. 加入購物車邏輯 ---
    # 篩選出有填寫數量的商品
    items_to_add = edited_df[edited_df["訂購數量"] > 0].copy()
    
    if not items_to_add.empty:
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.info(f"已選擇 {len(items_to_add)} 項產品")
            
        with col_btn:
            if st.button("⬇️ 加入清單", type="primary", use_container_width=True):
                # 這裡最關鍵：因為前台只顯示名稱，我們需要用名稱去「原始資料」找回 ID 和 品牌
                for _, row in items_to_add.iterrows():
                    p_name = row["產品名稱"]
                    qty = row["訂購數量"]
                    
                    # 反查原始資料 (取得第一筆符合名稱的資料)
                    original_product = df_products[df_products["產品名稱"] == p_name].iloc[0]
                    
                    st.session_state.cart_list.append({
                        "業務名稱": selected_sales_name, # 紀錄業務
                        "客戶名稱": selected_cust_name, # 紀錄客戶
                        "產品編號": original_product.get("產品編號", "N/A"),
                        "產品名稱": p_name,
                        "品牌": original_product.get("品牌", ""),
                        "訂購數量": qty
                    })
                st.success("已加入！")
                st.rerun()

    # --- 4. 確認送出 ---
    if len(st.session_state.cart_list) > 0:
        st.divider()
        st.subheader("📋 待送出清單")
        
        # 顯示時也簡單一點
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df[["產品名稱", "訂購數量", "客戶名稱", "業務名稱"]], use_container_width=True)
        
        col_submit, col_clear = st.columns([4, 1])
        
        with col_clear:
            if st.button("🗑️ 清空"):
                st.session_state.cart_list = []
                st.rerun()

        with col_submit:
            if st.button("✅ 確認送出 (儲存至 Google Sheets)", type="primary", use_container_width=True):
                with st.spinner("正在寫入雲端..."):
                    # 準備詳細訂單資料 (包含 ID) 用於後台紀錄
                    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # 這裡需要查找客戶 ID 和 業務 ID (為了資料庫完整性，雖然前台不顯示)
                    # 1. 找客戶 ID
                    cust_row = df_customers[df_customers["客戶名稱"] == selected_cust_name]
                    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"
                    
                    # 2. 找業務 ID
                    sales_row = df_salespeople[df_salespeople["業務名稱"] == selected_sales_name]
                    s_id = sales_row.iloc[0]["業務編號"] if not sales_row.empty else "Unknown"

                    new_rows = []
                    for item in st.session_state.cart_list:
                        new_rows.append({
                            "訂單編號": order_id,
                            "日期": order_date.strftime("%Y-%m-%d"),
                            "業務編號": s_id,    # 新增
                            "業務名稱": item["業務名稱"], # 新增
                            "客戶編號": c_id,
                            "客戶名稱": item["客戶名稱"],
                            "產品編號": item["產品編號"],
                            "產品名稱": item["產品名稱"],
                            "品牌": item["品牌"],
                            "訂購數量": item["訂購數量"]
                        })
                    
                    updated_history = pd.concat([df_order_history, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="訂單紀錄", data=updated_history)
                    
                    st.session_state.cart_list = []
                    st.success("訂單已建立！")
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 🔧 後台：資料管理 (新增業務管理)
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理")
    
    # 新增 Tab 4: 業務資料
    tab1, tab2, tab3, tab4 = st.tabs(["📊 訂單紀錄", "👥 客戶資料", "📦 產品資料", "yw 業務資料"])

    with tab1:
        st.dataframe(df_order_history, use_container_width=True)
        if st.button("🔄 重新整理"): st.rerun()

    with tab2: # 客戶
        st.dataframe(df_customers, use_container_width=True)
        up_cust = st.file_uploader("上傳客戶 Excel (A:編號, B:名稱)", type=['xlsx'])
        if up_cust and st.button("更新客戶"):
            new_df = pd.read_excel(up_cust).iloc[:, :2]
            new_df.columns = ["客戶編號", "客戶名稱"]
            conn.update(worksheet="客戶資料", data=new_df)
            st.success("完成！")
            st.rerun()

    with tab3: # 產品
        st.dataframe(df_products, use_container_width=True)
        up_prod = st.file_uploader("上傳產品 Excel (A:編號, B:名稱, C:品牌)", type=['xlsx'])
        if up_prod and st.button("更新產品"):
            new_df = pd.read_excel(up_prod).iloc[:, :3] # 取前三欄
            new_df.columns = ["產品編號", "產品名稱", "品牌"]
            conn.update(worksheet="產品資料", data=new_df)
            st.success("完成！")
            st.rerun()

    with tab4: # 業務 (新增功能)
        st.subheader("業務員資料管理")
        st.info("格式要求：A欄 (業務編號)、B欄 (業務名稱)")
        st.dataframe(df_salespeople, use_container_width=True)
        
        up_sales = st.file_uploader("上傳業務 Excel", type=['xlsx'], key="up_sales")
        if up_sales:
            if st.button("更新業務資料"):
                try:
                    new_df = pd.read_excel(up_sales).iloc[:, :2] # 取前兩欄
                    new_df.columns = ["業務編號", "業務名稱"]
                    conn.update(worksheet="業務資料", data=new_df)
                    st.success("業務資料已更新！")
                    st.rerun()
                except Exception as e:
                    st.error(f"錯誤: {e}")