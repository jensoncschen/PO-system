import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (名稱連動版)", layout="wide", page_icon="🛍️")

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
        
        # 防呆與欄位補全
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        
        # ★ 重點修改：改用「業務名稱」來做關聯 ★
        if "業務名稱" not in df_cust.columns: df_cust["業務名稱"] = ""
        
        # 強制轉字串並去除前後空白，避免 "王小明 " 和 "王小明" 對不上的問題
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        
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
st.sidebar.caption("v11.1 | 業務名稱連動版")

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
    
    # --- 1. 基本資訊 (名稱連動核心) ---
    with st.container():
        col_sales, col_cust, col_date = st.columns(3)
        
        # A. 選擇業務
        with col_sales:
            sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
            selected_sales_name = st.selectbox(
                "👤 承辦業務", sales_list, index=None, placeholder="請先選擇業務員..."
            )

        # B. 選擇客戶 (直接用名稱篩選)
        with col_cust:
            current_cust_list = []
            
            if selected_sales_name:
                # 直接篩選：客戶資料表中「業務名稱」欄位等於「選定業務」的資料
                filtered_cust_df = df_customers[df_customers["業務名稱"] == selected_sales_name]
                current_cust_list = filtered_cust_df["客戶名稱"].unique().tolist()
                
                # 防呆：如果該業務名下沒客戶
                if not current_cust_list:
                    placeholder_text = f"⚠️ {selected_sales_name} 名下尚無客戶資料"
                else:
                    placeholder_text = "請選擇客戶..."
            else:
                # 若未選業務，顯示全部 (或提示先選業務)
                current_cust_list = df_customers["客戶名稱"].unique().tolist()
                placeholder_text = "請先選擇業務員以載入清單..."

            selected_cust_name = st.selectbox(
                "🏢 客戶名稱", 
                current_cust_list, 
                index=None, 
                placeholder=placeholder_text,
                help="此選單會根據左側選擇的業務員自動篩選"
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
                    st.toast("✅ 加入購物車！") 
                    time.sleep(0.5)
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
            if st.button("✅ 確認送出 (寫入資料庫)", type="primary", use_container_width=True):
                with st.spinner("正在處理訂單資料..."):
                    
                    current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
                    if "BillNo" not in current_history.columns: current_history["BillNo"] = ""

                    # 取得業務編號 (用來產生單號 PersonID)
                    sales_row = df_salespeople[df_salespeople["業務名稱"] == selected_sales_name]
                    if not sales_row.empty:
                        raw_val = sales_row.iloc[0]["業務編號"]
                        s_str = str(raw_val).strip()
                        if s_str.endswith(".0"): s_str = s_str[:-2]
                        s_id_2digits = s_str.zfill(2)[-2:]
                    else:
                        s_id_2digits = "00"

                    date_str_8 = order_date.strftime('%Y%m%d')
                    prefix = f"{s_id_2digits}{date_str_8}"
                    
                    existing_ids = current_history["BillNo"].astype(str).tolist()
                    matching_ids = [oid for oid in existing_ids if oid.startswith(prefix) and len(oid) == 13]
                    
                    if matching_ids:
                        sequences = []
                        for oid in matching_ids:
                            try:
                                seq_num = int(oid[-3:])
                                sequences.append(seq_num)
                            except: continue
                        next_seq = max(sequences) + 1 if sequences else 1
                    else:
                        next_seq = 1
                    
                    final_bill_no = f"{prefix}{str(next_seq).zfill(3)}"
                    cust_row = df_customers[df_customers["客戶名稱"] == selected_cust_name]
                    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"

                    new_rows = []
                    for item in st.session_state.cart_list:
                        if item["訂購數量"] > 0:
                            new_rows.append({
                                "BillDate": date_str_8,
                                "BillNo": final_bill_no,
                                "PersonID": s_id_2digits,
                                "PersonName": item["業務名稱"],
                                "CustID": c_id,
                                "ProdID": item["產品編號"],
                                "ProdName": item["產品名稱"],
                                "Quantity": item["訂購數量"]
                            })
                        if item["搭贈數量"] > 0:
                            new_rows.append({
                                "BillDate": date_str_8,
                                "BillNo": final_bill_no,
                                "PersonID": s_id_2digits,
                                "PersonName": item["業務名稱"],
                                "CustID": c_id,
                                "ProdID": item["產品編號"],
                                "ProdName": f"{item['產品名稱']} (搭贈)", 
                                "Quantity": item["搭贈數量"]
                            })

                    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="訂單紀錄", data=updated_history)
                    
                    st.cache_data.clear()
                    st.session_state.cart_list = []
                    st.balloons()
                    st.success(f"訂單 {final_bill_no} 建立成功！")
                    time.sleep(2)
                    st.rerun()

# ==========================================
# 🔧 後台管理
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理")
    
    try:
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        st.info("💡 溫馨提示：客戶、產品、業務資料請直接在 Google 試算表 中修改，系統會自動同步。")
        st.markdown(f"👉 [點擊這裡開啟 Google 試算表]({sheet_url})")
    except:
        st.info("💡 客戶、產品、業務資料請直接在 Google 試算表 中修改。")

    st.divider()
    st.subheader("📊 歷史訂單紀錄")
    st.dataframe(df_order_history, use_container_width=True)
    
    if st.button("🔄 重新整理訂單"):
        st.cache_data.clear()
        st.rerun()