import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購單系統", layout="wide")
st.title("☁️ 簡易雲端訂購單系統")

# --- 初始化 Session State (用於暫存訂單資料) ---
if 'order_history' not in st.session_state:
    st.session_state.order_history = pd.DataFrame(columns=["訂單時間", "客戶名稱", "產品名稱", "單價", "數量", "總價"])

if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- 1. 側邊欄：資料匯入區 ---
st.sidebar.header("📁 資料管理")
st.sidebar.markdown("請先上傳基礎資料，若無則使用預設測試資料。")

# 客戶資料上傳
cust_file = st.sidebar.file_uploader("匯入客戶資料 (Excel/CSV)", type=['xlsx', 'csv'])
if cust_file:
    if cust_file.name.endswith('.csv'):
        df_customers = pd.read_csv(cust_file)
    else:
        df_customers = pd.read_excel(cust_file)
else:
    # 預設測試資料
    df_customers = pd.DataFrame({"客戶名稱": ["台積電", "聯發科", "鴻海", "中華電信"]})

# 產品資料上傳
prod_file = st.sidebar.file_uploader("匯入產品資料 (Excel/CSV)", type=['xlsx', 'csv'])
if prod_file:
    if prod_file.name.endswith('.csv'):
        df_products = pd.read_csv(prod_file)
    else:
        df_products = pd.read_excel(prod_file)
else:
    # 預設測試資料
    df_products = pd.DataFrame({
        "產品名稱": ["高階伺服器", "工業電腦", "AI 晶片模組", "散熱風扇"],
        "單價": [200000, 35000, 50000, 1200]
    })

# --- 2. 主畫面：訂單操作介面 ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 新增訂單")
    
    # 選擇客戶
    selected_customer = st.selectbox("選擇客戶", df_customers["客戶名稱"].unique())
    
    # 選擇產品
    product_list = df_products["產品名稱"].unique()
    selected_product_name = st.selectbox("選擇產品", product_list)
    
    # 自動帶出單價
    unit_price = df_products[df_products["產品名稱"] == selected_product_name]["單價"].values[0]
    st.info(f"產品單價: ${unit_price:,.0f}")
    
    # 輸入數量
    quantity = st.number_input("數量", min_value=1, value=1)
    
    # 計算小計
    subtotal = unit_price * quantity
    st.metric("預估金額", f"${subtotal:,.0f}")

    if st.button("加入訂單清單", type="primary"):
        new_item = {
            "訂單時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "客戶名稱": selected_customer,
            "產品名稱": selected_product_name,
            "單價": unit_price,
            "數量": quantity,
            "總價": subtotal
        }
        # 加入歷史紀錄
        new_df = pd.DataFrame([new_item])
        st.session_state.order_history = pd.concat([st.session_state.order_history, new_df], ignore_index=True)
        st.success("✅ 已新增一筆訂單！")

with col2:
    st.subheader("📋 訂單紀錄與匯出")
    
    if not st.session_state.order_history.empty:
        # 顯示訂單表格
        display_df = st.session_state.order_history.sort_values(by="訂單時間", ascending=False)
        st.dataframe(display_df, use_container_width=True)
        
        # 統計資訊
        total_revenue = display_df["總價"].sum()
        st.markdown(f"### 💰 總營收: :red[${total_revenue:,.0f}]")
        
        # --- 3. Excel 匯出功能 ---
        st.write("---")
        st.subheader("📤 匯出資料")
        
        # 將 DataFrame 轉為 Excel Bytes
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            display_df.to_excel(writer, index=False, sheet_name='訂單明細')
        
        st.download_button(
            label="📥 下載 Excel 訂單報表",
            data=buffer.getvalue(),
            file_name=f"訂單匯出_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("目前尚無訂單資料，請從左側新增。")

# --- 頁尾 ---
st.markdown("---")
st.caption("雲端訂購單系統 v1.0 | Designed by Gemini Engineer")