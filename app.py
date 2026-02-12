import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (自動拆單版)", layout="wide", page_icon="🎁")

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
        
        # 欄位防呆補強
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        
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
st.sidebar.caption("v6.1 | 自動拆分搭贈列")

# 載入資料
df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.error("⚠️ Google 連線忙碌中，請稍候再按側邊欄的更新按鈕。")
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
            sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
            selected_sales_name = st.selectbox(
                "👤 承辦業務", 
                sales_list,
                index=None,
                placeholder="請選擇業務員..."
            )

        with col_cust:
            cust_list = df_customers["客戶名稱"].unique().tolist() if not df_customers.empty else []
            selected_cust_name = st.selectbox(
                "🏢 客戶名稱 (可打字搜尋)", 
                cust_list,
                index=None,
                placeholder="請輸入關鍵字或從選單選擇..."
            )

        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 2. 產品列表 ---
    st.subheader("📦 產品訂購")

    col_filter, col_search = st.columns([1, 2])
    
    display_df = df_products.copy()

    with col_filter:
        all_brands = df_products["品牌"].unique().tolist() if "品牌" in df_products.columns else []
        selected_brands = st.multiselect(
            "🏷️ 品牌篩選", 
            all_brands,
            placeholder="請選擇品牌..."
        )
        if selected_brands:
            display_df = display_df[display_df["品牌"].isin(selected_brands)]

    with col_search:
        product_list = display_df["產品名稱"].unique().tolist()
        search_product_name = st.selectbox(
            "🔍 產品搜尋 (可打字搜尋)", 
            product_list,
            index=None,
            placeholder="請輸入產品名稱關鍵字...",
            help="選擇特定產品後，下方列表只會顯示該產品"
        )
    
    if search_product_name:
        display_df = display_df[display_df["產品名稱"] == search_product_name]

    # --- 準備編輯表格 ---
    display_df = display_df[["產品名稱"]].copy() 
    display_df["訂購數量"] = 0
    display_df["搭贈數量"] = 0 

    st.caption(f"列表顯示 {len(display_df)} 筆產品")

    edited_df = st.data_editor(
        display_df,
        column_config={
            "產品名稱": st.column_config.TextColumn(disabled=True, width="large"),
            "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="正常購買的數量"),
            "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1, help="免費贈送的數量")
        },
        use_container_width=True,
        hide_index=True,
        key="product_gift_split_editor"
    )

    # --- 3. 加入購物車 ---
    items_to_add = edited_df[
        (edited_df["訂購數量"] > 0) | (edited_df["搭贈數量"] > 0)
    ].copy()
    
    if not items_to_add.empty:
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.info(f"已選擇 {len(items_to_add)} 項產品")
            
        with col_btn:
            if not selected_cust_name or not selected_sales_name:
                st.error("⚠️ 請先選擇「業務」與「客戶」")
            else:
                if st.button("⬇️ 加入清單", type="primary", use_container_width=True):
                    for _, row in items_to_add.iterrows():
                        p_name = row["產品名稱"]
                        qty = row["訂購數量"]
                        gift_qty = row["搭贈數量"]
                        
                        original_product = df_products[df_products["產品名稱"] == p_name].iloc[0]
                        
                        st.session_state.cart_list.append({
                            "業務名稱": selected_sales_name,
                            "客戶名稱": selected_cust_name,
                            "產品編號": original_product.get("產品編號", "N/A"),
                            "產品名稱": p_name,
                            "品牌": original_product.get("品牌", ""),
                            "訂購數量": qty,
                            "搭贈數量": gift_qty
                        })
                    st.success("已加入！")
                    st.rerun()

    # --- 4. 確認送出 (拆單邏輯核心) ---
    if len(st.session_state.cart_list) > 0:
        st.divider()
        st.subheader("📋 待送出清單")
        
        # 顯示給使用者看的時候，還是維持一行比較清楚
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df[["產品名稱", "訂購數量", "搭贈數量", "客戶名稱"]], use_container_width=True)
        
        col_submit, col_clear = st.columns([4, 1])
        
        with col_clear:
            if st.button("🗑️ 清空"):
                st.session_state.cart_list = []
                st.rerun()

        with col_submit:
            if st.button("✅ 確認送出 (自動拆分贈品)", type="primary", use_container_width=True):
                with st.spinner("正在寫入雲端..."):
                    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
                    
                    # 查找 ID
                    cust_row = df_customers[df_customers["客戶名稱"] == selected_cust_name]
                    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"
                    
                    sales_row = df_salespeople[df_salespeople["業務名稱"] == selected_sales_name]
                    s_id = sales_row.iloc[0]["業務編號"] if not sales_row.empty else "Unknown"

                    new_rows = []
                    for item in st.session_state.cart_list:
                        # === 拆單邏輯開始 ===
                        
                        # 1. 處理「正常訂購」的部分
                        if item["訂購數量"] > 0:
                            new_rows.append({
                                "訂單編號": order_id,
                                "日期": order_date.strftime("%Y-%m-%d"),
                                "業務編號": s_id,
                                "業務名稱": item["業務名稱"],
                                "客戶編號": c_id,
                                "客戶名稱": item["客戶名稱"],
                                "產品編號": item["產品編號"],
                                "產品名稱": item["產品名稱"], # 正常名稱
                                "品牌": item["品牌"],
                                "訂購數量": item["訂購數量"]
                            })
                        
                        # 2. 處理「搭贈」的部分 (如果有搭贈數量，就多加一列)
                        if item["搭贈數量"] > 0:
                            new_rows.append({
                                "訂單編號": order_id,
                                "日期": order_date.strftime("%Y-%m-%d"),
                                "業務編號": s_id,
                                "業務名稱": item["業務名稱"],
                                "客戶編號": c_id,
                                "客戶名稱": item["客戶名稱"],
                                "產品編號": item["產品編號"],
                                "產品名稱": f"{item['產品名稱']} (搭贈)", # 修改名稱以便區分
                                "品牌": item["品牌"],
                                "訂購數量": item["搭贈數量"] # 這裡填入搭贈的數量
                            })
                        # === 拆單邏輯結束 ===

                    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="訂單紀錄", data=updated_history)
                    
                    st.cache_data.clear()
                    st.session_state.cart_list = []
                    st.success(f"訂單已建立！若有搭贈品項，已自動拆分為獨立列。")
                    time.sleep(2)
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
            st.cache_data.clear()
            st.success("完成！")
            st.rerun()

    with tab3: # 產品
        st.dataframe(df_products, use_container_width=True)
        up_prod = st.file_uploader("上傳產品 Excel (A:編號, B:名稱, C:品牌)", type=['xlsx'])
        if up_prod and st.button("更新產品"):
            new_df = pd.read_excel(up_prod).iloc[:, :3]
            new_df.columns = ["產品編號", "產品名稱", "品牌"]
            conn.update(worksheet="產品資料", data=new_df)
            st.cache_data.clear()
            st.success("完成！")
            st.rerun()

    with tab4: # 業務
        st.dataframe(df_salespeople, use_container_width=True)
        up_sales = st.file_uploader("上傳業務 Excel", type=['xlsx'], key="up_sales")
        if up_sales:
            if st.button("更新業務資料"):
                new_df = pd.read_excel(up_sales).iloc[:, :2]
                new_df.columns = ["業務編號", "業務名稱"]
                conn.update(worksheet="業務資料", data=new_df)
                st.cache_data.clear()
                st.success("完成！")
                st.rerun()