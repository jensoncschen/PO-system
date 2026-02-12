import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (品牌分區版)", layout="wide", page_icon="🛍️")

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
st.sidebar.caption("v7.0 | 品牌視覺分區版")

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

    # --- 2. 產品列表 (品牌分區核心邏輯) ---
    st.subheader("📦 產品訂購")

    col_filter, col_search = st.columns([1, 2])
    
    # 原始資料備份
    base_df = df_products.copy()
    base_df["訂購數量"] = 0
    base_df["搭贈數量"] = 0

    with col_filter:
        all_brands = df_products["品牌"].unique().tolist() if "品牌" in df_products.columns else []
        selected_brands = st.multiselect("🏷️ 品牌篩選", all_brands, placeholder="預設顯示全部...")

    with col_search:
        # 為了讓搜尋選單只顯示「符合篩選品牌」的產品，我們這裡做個過濾
        filtered_for_search = base_df.copy()
        if selected_brands:
            filtered_for_search = filtered_for_search[filtered_for_search["品牌"].isin(selected_brands)]
            
        product_list = filtered_for_search["產品名稱"].unique().tolist()
        search_product_name = st.selectbox(
            "🔍 精準搜尋", product_list, index=None, placeholder="搜尋特定產品 (選取後將隱藏其他列表)..."
        )

    # --- 顯示邏輯判定 ---
    editors_data = {} # 用來收集各個品牌表格的結果

    # 情況 A: 使用者選定了特定產品 -> 只顯示單一表格
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
        # 存入結果字典 (key="search")
        editors_data["search"] = edited_df

    # 情況 B: 一般瀏覽 -> 依照品牌分區顯示
    else:
        # 決定要顯示哪些品牌
        brands_to_show = selected_brands if selected_brands else all_brands
        
        if not brands_to_show:
            st.warning("沒有可顯示的產品品牌。")
        else:
            # 迴圈：為每個品牌建立一個區塊
            for brand in brands_to_show:
                # 篩選出該品牌的資料
                brand_df = base_df[base_df["品牌"] == brand].copy()
                
                if not brand_df.empty:
                    # 使用 expander (可折疊) 讓版面更整潔，預設展開 (expanded=True)
                    with st.expander(f"🏷️ {brand} ({len(brand_df)} 項產品)", expanded=True):
                        
                        # 顯示表格
                        edited_brand_df = st.data_editor(
                            brand_df[["產品名稱", "訂購數量", "搭贈數量"]],
                            column_config={
                                "產品名稱": st.column_config.TextColumn(disabled=True),
                                "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="購買量"),
                                "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1, help="贈送量")
                            },
                            use_container_width=True,
                            hide_index=True,
                            # 重要：每個 data_editor 必須有唯一的 key，我們用品牌名稱當 key
                            key=f"editor_{brand}"
                        )
                        # 將這個品牌的編輯結果存起來
                        editors_data[brand] = edited_brand_df

    # --- 3. 加入購物車 (彙整所有表格資料) ---
    # 我們需要遍歷 editors_data 裡面的所有 dataframe
    total_items_selected = 0
    all_selected_rows = []

    for key, df_result in editors_data.items():
        # 找出有填寫數量的列
        selected = df_result[ (df_result["訂購數量"] > 0) | (df_result["搭贈數量"] > 0) ]
        if not selected.empty:
            all_selected_rows.append(selected)
            total_items_selected += len(selected)

    if total_items_selected > 0:
        st.markdown("---")
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.success(f"⚡ 已在各區塊中選擇共 {total_items_selected} 項產品")
            
        with col_btn:
            if not selected_cust_name or not selected_sales_name:
                st.error("⚠️ 請先選擇「業務」與「客戶」")
            else:
                if st.button("⬇️ 全部加入購物車", type="primary", use_container_width=True):
                    # 處理彙整後的資料
                    for df_chunk in all_selected_rows:
                        for _, row in df_chunk.iterrows():
                            p_name = row["產品名稱"]
                            qty = row["訂購數量"]
                            gift_qty = row["搭贈數量"]
                            
                            # 反查原始詳細資料 (含編號、品牌)
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
                    st.toast("✅ 已成功加入購物車！") # 使用 toast 提示比較輕量
                    time.sleep(1)
                    st.rerun()

    # --- 4. 確認送出 ---
    if len(st.session_state.cart_list) > 0:
        st.divider()
        st.subheader("📋 待送出清單")
        
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
                        # 拆單邏輯: 正常
                        if item["訂購數量"] > 0:
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
                        # 拆單邏輯: 搭贈
                        if item["搭贈數量"] > 0:
                            new_rows.append({
                                "訂單編號": order_id,
                                "日期": order_date.strftime("%Y-%m-%d"),
                                "業務編號": s_id,
                                "業務名稱": item["業務名稱"],
                                "客戶編號": c_id,
                                "客戶名稱": item["客戶名稱"],
                                "產品編號": item["產品編號"],
                                "產品名稱": f"{item['產品名稱']} (搭贈)", 
                                "品牌": item["品牌"],
                                "訂購數量": item["搭贈數量"]
                            })

                    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="訂單紀錄", data=updated_history)
                    
                    st.cache_data.clear()
                    st.session_state.cart_list = []
                    st.balloons()
                    st.success(f"訂單已建立！")
                    time.sleep(2)
                    st.rerun()

# ==========================================
# 🔧 後台管理 (維持不變)
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理")
    tab1, tab2, tab3, tab4 = st.tabs(["📊 訂單紀錄", "👥 客戶資料", "📦 產品資料", "yw 業務資料"])

    with tab1:
        st.dataframe(df_order_history, use_container_width=True)

    with tab2: 
        st.dataframe(df_customers, use_container_width=True)
        up_cust = st.file_uploader("上傳客戶 Excel", type=['xlsx'])
        if up_cust and st.button("更新客戶"):
            new_df = pd.read_excel(up_cust).iloc[:, :2]
            new_df.columns = ["客戶編號", "客戶名稱"]
            conn.update(worksheet="客戶資料", data=new_df)
            st.cache_data.clear()
            st.success("完成！")
            st.rerun()

    with tab3: 
        st.dataframe(df_products, use_container_width=True)
        up_prod = st.file_uploader("上傳產品 Excel", type=['xlsx'])
        if up_prod and st.button("更新產品"):
            new_df = pd.read_excel(up_prod).iloc[:, :3]
            new_df.columns = ["產品編號", "產品名稱", "品牌"]
            conn.update(worksheet="產品資料", data=new_df)
            st.cache_data.clear()
            st.success("完成！")
            st.rerun()

    with tab4: 
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