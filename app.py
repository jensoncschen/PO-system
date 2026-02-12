import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (防爆量版)", layout="wide", page_icon="☁️")

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 關鍵修正：加入快取機制 ---
# ttl=300 代表資料會被暫存 300秒 (5分鐘)
# 在這 5 分鐘內，不管你怎麼搜尋、篩選，都不會消耗 Google API 額度
@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        # 這裡移除 ttl=0，改由上方的 @st.cache_data 控制
        df_cust = conn.read(worksheet="客戶資料")
        df_prod = conn.read(worksheet="產品資料")
        df_sales = conn.read(worksheet="業務資料") 
        df_order = conn.read(worksheet="訂單紀錄")
        
        # 確保欄位存在 (防呆)
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        
        return df_cust, df_prod, df_sales, df_order
    except Exception as e:
        # 如果爆量了，這裡會回傳 None，稍後處理
        return None, None, None, None

# --- 側邊欄：手動更新與導航 ---
st.sidebar.title("☁️ 系統導航")

# 加入手動更新按鈕
if st.sidebar.button("🔄 強制更新資料"):
    st.cache_data.clear() # 清除快取
    st.rerun() # 重新執行

page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "🔧 後台：資料管理"])
st.sidebar.markdown("---")
st.sidebar.caption("v5.1 | 防爆量快取版")

# 載入資料 (現在會優先讀快取)
df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

# 如果因為額度爆了讀不到資料，顯示友善訊息
if df_customers is None:
    st.error("⚠️ 讀取太頻繁，Google 暫時限制了連線。請等待 1 分鐘後，按下側邊欄的「🔄 強制更新資料」。")
    st.stop()

# --- 初始化 Session State ---
if 'cart_list' not in st.session_state:
    st.session_state.cart_list = []

# ==========================================
# 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🛒 業務下單專區")
    
    # --- 1. 基本資訊 ---
    with st.container():
        col_sales, col_cust, col_date = st.columns(3)
        
        with col_sales:
            # 業務選單
            sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
            selected_sales_name = st.selectbox("👤 承辦業務", sales_list)

        with col_cust:
            # 客戶選單
            cust_list = df_customers["客戶名稱"].unique().tolist() if not df_customers.empty else []
            selected_cust_name = st.selectbox("🏢 客戶名稱", cust_list)

        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 2. 產品列表 ---
    st.subheader("📦 產品訂購")

    # 搜尋功能 (現在打字不會消耗額度了)
    search_term = st.text_input("🔍 搜尋產品名稱", placeholder="輸入關鍵字...")
    
    # 準備顯示資料
    display_df = df_products.copy()
    
    if search_term:
        display_df = display_df[display_df["產品名稱"].astype(str).str.contains(search_term, case=False)]

    display_df = display_df[["產品名稱"]].copy() 
    display_df["訂購數量"] = 0

    # 互動表格
    edited_df = st.data_editor(
        display_df,
        column_config={
            "產品名稱": st.column_config.TextColumn(disabled=True, width="large"),
            "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="請輸入數量")
        },
        use_container_width=True,
        hide_index=True,
        key="product_simple_editor"
    )

    # --- 3. 加入購物車 ---
    items_to_add = edited_df[edited_df["訂購數量"] > 0].copy()
    
    if not items_to_add.empty:
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.info(f"已選擇 {len(items_to_add)} 項產品")
            
        with col_btn:
            if st.button("⬇️ 加入清單", type="primary", use_container_width=True):
                for _, row in items_to_add.iterrows():
                    p_name = row["產品名稱"]
                    qty = row["訂購數量"]
                    
                    original_product = df_products[df_products["產品名稱"] == p_name].iloc[0]
                    
                    st.session_state.cart_list.append({
                        "業務名稱": selected_sales_name,
                        "客戶名稱": selected_cust_name,
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
                    # 寫入時我們必須強制取得最新狀態，所以這裡不使用 cache
                    # 但因為寫入動作不頻繁，所以是安全的
                    
                    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # 重新讀取一次訂單紀錄以確保不覆蓋別人的資料 (這次用 ttl=0)
                    current_history = conn.read(worksheet="訂單紀錄", ttl=0) 

                    # 查找 ID 邏輯
                    cust_row = df_customers[df_customers["客戶名稱"] == selected_cust_name]
                    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"
                    
                    sales_row = df_salespeople[df_salespeople["業務名稱"] == selected_sales_name]
                    s_id = sales_row.iloc[0]["業務編號"] if not sales_row.empty else "Unknown"

                    new_rows = []
                    for item in st.session_state.cart_list:
                        new_rows.append({
                            "訂單編號": order_id,
                            "日期": order_date.strftime("%Y-%m-%d"),
                            "業務編號": s_id,
                            "業務名稱": item["業務名稱"],
                            "客戶編號": c_id,
                            "客戶名稱": item["客戶名稱"],
                            "產品編號": item["產品編號"],
                            "產品名稱": item["產品名稱"],
                            "品牌": item["品牌"],
                            "訂購數量": item["訂購數量"]
                        })
                    
                    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="訂單紀錄", data=updated_history)
                    
                    # 寫入完畢後，清除快取，讓介面之後能讀到最新的訂單
                    st.cache_data.clear()
                    
                    st.session_state.cart_list = []
                    st.success("訂單已建立！")
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 🔧 後台：資料管理
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 訂單紀錄", "👥 客戶資料", "📦 產品資料", "yw 業務資料"])

    with tab1:
        st.dataframe(df_order_history, use_container_width=True)

    with tab2: # 客戶
        st.dataframe(df_customers, use_container_width=True)
        up_cust = st.file_uploader("上傳客戶 Excel (A:編號, B:名稱)", type=['xlsx'])
        if up_cust and st.button("更新客戶"):
            new_df = pd.read_excel(up_cust).iloc[:, :2]
            new_df.columns = ["客戶編號", "客戶名稱"]
            conn.update(worksheet="客戶資料", data=new_df)
            st.cache_data.clear() # 更新後清除快取
            st.success("完成！")
            st.rerun()

    with tab3: # 產品
        st.dataframe(df_products, use_container_width=True)
        up_prod = st.file_uploader("上傳產品 Excel (A:編號, B:名稱, C:品牌)", type=['xlsx'])
        if up_prod and st.button("更新產品"):
            new_df = pd.read_excel(up_prod).iloc[:, :3]
            new_df.columns = ["產品編號", "產品名稱", "品牌"]
            conn.update(worksheet="產品資料", data=new_df)
            st.cache_data.clear() # 更新後清除快取
            st.success("完成！")
            st.rerun()

    with tab4: # 業務
        st.dataframe(df_salespeople, use_container_width=True)
        up_sales = st.file_uploader("上傳業務 Excel", type=['xlsx'], key="up_sales")
        if up_sales:
            if st.button("更新業務資料"):
                try:
                    new_df = pd.read_excel(up_sales).iloc[:, :2]
                    new_df.columns = ["業務編號", "業務名稱"]
                    conn.update(worksheet="業務資料", data=new_df)
                    st.cache_data.clear() # 更新後清除快取
                    st.success("業務資料已更新！")
                    st.rerun()
                except Exception as e:
                    st.error(f"錯誤: {e}")