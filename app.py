import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購/領用系統 (Google Sheets版)", layout="wide", page_icon="☁️")

# --- 連接 Google Sheets ---
# 使用 ttl=0 確保每次都從雲端抓取最新資料，不快取
conn = st.connection("gsheets", type=GSheetsConnection)

# 定義讀取資料的函數
def load_data():
    try:
        # 讀取三個分頁
        df_cust = conn.read(worksheet="客戶資料", ttl=0)
        df_prod = conn.read(worksheet="產品資料", ttl=0)
        df_order = conn.read(worksheet="訂單紀錄", ttl=0)
        return df_cust, df_prod, df_order
    except Exception as e:
        st.error(f"無法連接 Google 試算表，請檢查 secrets.toml 設定或權限。\n錯誤訊息: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# 載入資料
df_customers, df_products, df_order_history = load_data()

# --- 初始化 Session State (購物車暫存) ---
if 'cart_list' not in st.session_state:
    st.session_state.cart_list = []

# --- 側邊欄導航 ---
st.sidebar.title("☁️ 雲端系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：下單/領用", "🔧 後台：資料管理"])
st.sidebar.markdown("---")
st.sidebar.caption("v4.0 | Google Sheets 連動版")

# 如果資料讀取失敗，停止執行
if df_customers.empty or df_products.empty:
    st.warning("⚠️ 尚未讀取到資料，請確認 Google Sheet 是否已建立且格式正確。")
    st.stop()

# ==========================================
# 🛒 前台：下單/領用頁面 (無金額版)
# ==========================================
if page == "🛒 前台：下單/領用":
    st.title("🛒 下單/領用專區")
    
    # --- 1. 基本資訊 ---
    with st.container():
        col_cust, col_date = st.columns([1, 1])
        with col_cust:
            # 製作選單：C001 - 台積電
            cust_options = df_customers.apply(
                lambda x: f"{x['客戶編號']} - {x['客戶名稱']}", axis=1
            )
            selected_cust_str = st.selectbox("👤 選擇客戶/單位", cust_options)
            if selected_cust_str:
                selected_cust_id = selected_cust_str.split(" - ")[0]
                selected_cust_name = selected_cust_str.split(" - ")[1]

        with col_date:
            order_date = st.date_input("📅 日期", datetime.now())
    
    st.divider()

    # --- 2. 產品篩選 (僅顯示：編號、品牌、名稱) ---
    st.subheader("📦 產品選擇")

    col_search, col_filter = st.columns([2, 1])
    with col_search:
        search_term = st.text_input("🔍 搜尋產品", placeholder="輸入名稱或編號...")
    with col_filter:
        all_brands = df_products["品牌"].unique() if "品牌" in df_products.columns else []
        selected_brands = st.multiselect("🏷️ 品牌篩選", all_brands)

    # 資料篩選
    display_df = df_products.copy()
    
    # 確保欄位存在 (防呆)
    required_cols = ["產品編號", "產品名稱", "品牌"]
    for col in required_cols:
        if col not in display_df.columns:
            display_df[col] = "" # 若欄位缺失則補空

    if search_term:
        display_df = display_df[
            display_df["產品名稱"].astype(str).str.contains(search_term, case=False) | 
            display_df["產品編號"].astype(str).str.contains(search_term, case=False)
        ]
    
    if selected_brands:
        display_df = display_df[display_df["品牌"].isin(selected_brands)]

    # 準備顯示 (移除單價，只留數量輸入)
    display_df["訂購數量"] = 0
    display_df = display_df[["產品編號", "品牌", "產品名稱", "訂購數量"]]

    # 互動表格
    edited_df = st.data_editor(
        display_df,
        column_config={
            "產品編號": st.column_config.TextColumn(disabled=True),
            "品牌": st.column_config.TextColumn(disabled=True),
            "產品名稱": st.column_config.TextColumn(disabled=True),
            "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="輸入數量")
        },
        use_container_width=True,
        hide_index=True,
        key="product_selector_gsheets"
    )

    # --- 3. 加入清單 ---
    items_to_add = edited_df[edited_df["訂購數量"] > 0].copy()
    
    if not items_to_add.empty:
        if st.button(f"⬇️ 加入 {len(items_to_add)} 項商品", type="primary"):
            for _, row in items_to_add.iterrows():
                st.session_state.cart_list.append({
                    "產品編號": row["產品編號"],
                    "產品名稱": row["產品名稱"],
                    "品牌": row["品牌"],
                    "訂購數量": row["訂購數量"]
                })
            st.success("已加入清單！")
            st.rerun()

    # --- 4. 確認送出 (寫入 Google Sheets) ---
    if len(st.session_state.cart_list) > 0:
        st.divider()
        st.subheader("📋 待送出清單")
        
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df, use_container_width=True)
        
        col_submit, col_clear = st.columns([4, 1])
        
        with col_clear:
            if st.button("🗑️ 清空"):
                st.session_state.cart_list = []
                st.rerun()

        with col_submit:
            if st.button("✅ 確認送出並儲存至雲端", type="primary", use_container_width=True):
                with st.spinner("正在寫入 Google Sheets..."):
                    # 準備新資料
                    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    new_rows = []
                    for item in st.session_state.cart_list:
                        new_rows.append({
                            "訂單編號": order_id,
                            "日期": order_date.strftime("%Y-%m-%d"),
                            "客戶編號": selected_cust_id,
                            "客戶名稱": selected_cust_name,
                            "產品編號": item["產品編號"],
                            "產品名稱": item["產品名稱"],
                            "品牌": item["品牌"],
                            "訂購數量": item["訂購數量"]
                        })
                    
                    # 轉換為 DataFrame
                    new_order_df = pd.DataFrame(new_rows)
                    
                    # 合併舊資料與新資料 (Append模式)
                    # 注意：在大數據量時讀取再寫回效率較低，但適合中小規模
                    updated_order_history = pd.concat([df_order_history, new_order_df], ignore_index=True)
                    
                    # 寫回 Google Sheets
                    conn.update(worksheet="訂單紀錄", data=updated_order_history)
                    
                    # 清空 Session
                    st.session_state.cart_list = []
                    st.success(f"訂單 {order_id} 已成功寫入 Google 試算表！")
                    st.balloons()
                    # 延遲後重新整理以顯示最新數據
                    import time
                    time.sleep(2)
                    st.rerun()

# ==========================================
# 🔧 後台：資料管理 (Google Sheets 連結版)
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理 (雲端同步)")
    st.info("💡 此處資料直接連結 Google Sheets。若要修改，請直接編輯 Google 試算表，或在此處上傳覆蓋。")

    tab1, tab2, tab3 = st.tabs(["📊 訂單紀錄", "👥 客戶資料", "📦 產品資料"])

    with tab1:
        st.subheader("雲端訂單紀錄")
        st.dataframe(df_order_history, use_container_width=True)
        if st.button("🔄 重新整理資料"):
            st.cache_data.clear()
            st.rerun()

    with tab2:
        st.subheader("客戶資料")
        st.dataframe(df_customers, use_container_width=True)
        st.markdown("---")
        st.write("⚠️ 若要更新，建議直接去 Google Sheet 編輯，或是上傳 Excel **完全覆蓋** 目前的雲端資料。")
        
        up_cust = st.file_uploader("上傳 Excel 覆蓋客戶資料", type=['xlsx'])
        if up_cust:
            if st.button("確認覆蓋雲端客戶資料"):
                new_df = pd.read_excel(up_cust).iloc[:, :2] # 只取前兩欄
                new_df.columns = ["客戶編號", "客戶名稱"]
                conn.update(worksheet="客戶資料", data=new_df)
                st.success("雲端資料已更新！")
                st.rerun()

    with tab3:
        st.subheader("產品資料 (無單價)")
        st.dataframe(df_products, use_container_width=True)
        st.markdown("---")
        st.write("⚠️ 若要更新，建議直接去 Google Sheet 編輯，或是上傳 Excel **完全覆蓋** 目前的雲端資料。")

        up_prod = st.file_uploader("上傳 Excel 覆蓋產品資料", type=['xlsx'])
        if up_prod:
            if st.button("確認覆蓋雲端產品資料"):
                new_df = pd.read_excel(up_prod).iloc[:, :3] # 只取前三欄
                new_df.columns = ["產品編號", "產品名稱", "品牌"] # 移除了單價
                conn.update(worksheet="產品資料", data=new_df)
                st.success("雲端資料已更新！")
                st.rerun()