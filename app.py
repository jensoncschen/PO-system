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
                raw_val = sales_row.iloc[0]["業務編號"]
                s_str = str(raw_val).strip()
                if s_str.endswith(".0"): s_str = s_str[:-2]
                s_id_2digits = s_str.zfill(2)[-2:]
            else:
                s_id_2digits = "00"

            # 產生日期與流水號
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
            
            # 取得 CustID
            cust_row = df_customers[df_customers["客戶名稱"] == selected_cust_name]
            c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"

            # 建立資料列
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

            # 寫入
            updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
            conn.update(worksheet="訂單紀錄", data=updated_history)
            
            # 清理
            st.cache_data.clear()
            st.session_state.cart_list = []
            st.balloons()
            st.success(f"訂單 {final_bill_no} 建立成功！")
            time.sleep(2)
            st.rerun()

    # --- ★★★ 新增：側邊欄購物車快捷區 ★★★ ---
    st.sidebar.header("🛒 購物車快捷區")
    
    # 計算目前總數
    current_cart_count = len(st.session_state.cart_list)
    
    if current_cart_count > 0:
        st.sidebar.info(f"目前已選：{current_cart_count} 項商品")
        
        # 功能1: 訂購清單 (折疊式)
        with st.sidebar.expander("👀 檢視清單", expanded=True):
            mini_df = pd.DataFrame(st.session_state.cart_list)
            # 只顯示重點欄位
            st.dataframe(
                mini_df[["產品名稱", "訂購數量", "搭贈數量"]], 
                use_container_width=True, 
                hide_index=True
            )

        # 功能2: 送出訂單
        # 注意: 如果這裡按了，會執行上面的 submit_order_logic
        if st.sidebar.button("✅ 立即送出訂單", type="primary", key="btn_sidebar_submit"):
            submit_order_logic()

        # 功能3: 清除已訂購
        if st.sidebar.button("🗑️ 清除全部商品", key="btn_sidebar_clear"):
            st.session_state.cart_list = []
            st.rerun()
            
    else:
        st.sidebar.caption("🛒 購物車是空的")
        st.sidebar.caption("請在右側選擇產品加入...")

    # --- 2. 產品列表 (主畫面) ---
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

    # 顯示編輯器
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
            use_container_width=True, hide_index=True, key="editor_single_search"
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
                            use_container_width=True, hide_index=True, key=f"editor_{brand}"
                        )
                        editors_data[brand] = edited_brand_df

    # --- 3. 加入購物車 (主畫面按鈕) ---
    all_selected_rows = []
    total_new_items = 0
    for key, df_result in editors_data.items():
        selected = df_result[ (df_result["訂購數量"] > 0) | (df_result["搭贈數量"] > 0) ]
        if not selected.empty:
            all_selected_rows.append(selected)
            total_new_items += len(selected)

    if total_new_items > 0:
        st.markdown("---")
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.success(f"⚡ 這裡選擇了 {total_new_items} 項產品 (請按加入)")
        with col_btn:
            if not selected_cust_name or not selected_sales_name:
                st.error("⚠️ 請先選擇「業務」與「客戶」")
            else:
                if st.button("⬇️ 全部加入購物車", type="primary", use_container_width=True, key="btn_main_add"):
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

    # --- 4. 確認送出區 (主畫面底部，保留給習慣往下捲的人) ---
    if len(st.session_state.cart_list) > 0:
        st.divider()
        st.subheader("📋 待送出清單 (主畫面)")
        
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df[["產品名稱", "訂購數量", "搭贈數量", "客戶名稱"]], use_container_width=True)
        
        col_submit, col_clear = st.columns([4, 1])
        
        with col_clear:
            if st.button("🗑️ 清空", key="btn_main_clear"):
                st.session_state.cart_list = []
                st.rerun()

        with col_submit:
            if st.button("✅ 確認送出 (寫入資料庫)", type="primary", use_container_width=True, key="btn_main_submit"):
                submit_order_logic()

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
    if st.button("🔄 重新整理訂單", key="btn_refresh_backend"):
        st.cache_data.clear()
        st.rerun()