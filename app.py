import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (預設折疊版)", layout="wide", page_icon="🛍️")

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
        
        # 防呆
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        if "業務名稱" not in df_cust.columns: df_cust["業務名稱"] = ""
        
        # 清洗資料
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        df_order["BillNo"] = df_order["BillNo"].astype(str).str.replace("'", "", regex=False)
        
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
if 'current_step' not in st.session_state:
    st.session_state.current_step = 1 # 1:選購頁, 2:結帳頁

# --- 初始化「確認後」的訂單資訊 ---
if 'confirmed_sales' not in st.session_state: st.session_state.confirmed_sales = ""
if 'confirmed_cust' not in st.session_state: st.session_state.confirmed_cust = ""
if 'confirmed_date' not in st.session_state: st.session_state.confirmed_date = datetime.now()

# --- 左側導航 ---
st.sidebar.title("☁️ 系統導航")
if st.sidebar.button("🔄 強制更新資料", key="btn_update_data"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "🔧 後台：資料管理"])
st.sidebar.markdown("---")

cart_count = len(st.session_state.cart_list)
if cart_count > 0:
    st.sidebar.success(f"🛒 購物車內有 {cart_count} 筆商品")
    if st.session_state.current_step == 1:
        if st.sidebar.button("前往結帳 ➡️"):
            st.session_state.current_step = 2
            st.rerun()
else:
    st.sidebar.caption("🛒 購物車是空的")

# ==========================================
# 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    
    # ---------------------------------------------------------
    # STEP 1: 商品選購頁面
    # ---------------------------------------------------------
    if st.session_state.current_step == 1:
        st.title("🛒 步驟 1/2：選擇商品")
        
        # --- 基本資訊區 ---
        with st.container():
            col_sales, col_cust, col_date = st.columns(3)
            
            with col_sales:
                sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
                selected_sales_name = st.selectbox(
                    "👤 承辦業務", sales_list, index=None, placeholder="請先選擇業務員...", key="sb_sales"
                )

            with col_cust:
                current_cust_list = []
                placeholder_text = "請先選擇業務員..."
                if selected_sales_name:
                    filtered_cust_df = df_customers[df_customers["業務名稱"] == selected_sales_name]
                    current_cust_list = filtered_cust_df["客戶名稱"].unique().tolist()
                    placeholder_text = "請選擇客戶..." if current_cust_list else f"⚠️ {selected_sales_name} 名下無客戶"
                
                selected_cust_name = st.selectbox(
                    "🏢 客戶名稱", current_cust_list, index=None, placeholder=placeholder_text, key="sb_cust"
                )

            with col_date:
                order_date = st.date_input("📅 訂單日期", datetime.now())
        
        st.divider()

        # --- 產品列表區 ---
        st.subheader("📦 產品列表")
        st.caption("💡 點擊品牌名稱可展開/折疊商品清單") # 增加提示
        
        c_filter, c_search = st.columns([1, 2])
        base_df = df_products.copy()
        base_df["訂購數量"] = 0
        base_df["搭贈數量"] = 0

        with c_filter:
            all_brands = df_products["品牌"].unique().tolist() if "品牌" in df_products.columns else []
            selected_brands = st.multiselect("🏷️ 品牌", all_brands)

        with c_search:
            filtered_for_search = base_df.copy()
            if selected_brands:
                filtered_for_search = filtered_for_search[filtered_for_search["品牌"].isin(selected_brands)]
            product_list = filtered_for_search["產品名稱"].unique().tolist()
            search_product_name = st.selectbox("🔍 搜尋", product_list, index=None, placeholder="輸入產品名稱...")

        editors_data = {} 
        
        # 顯示產品表格
        if search_product_name:
            # 如果是精準搜尋，就直接顯示該產品 (不用折疊)
            target_df = base_df[base_df["產品名稱"] == search_product_name].copy()
            edited_df = st.data_editor(
                target_df[["產品名稱", "訂購數量", "搭贈數量"]],
                column_config={
                    "產品名稱": st.column_config.TextColumn(disabled=True),
                    "訂購數量": st.column_config.NumberColumn(min_value=0, step=1),
                    "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1)
                },
                use_container_width=True, hide_index=True, key="editor_single_search"
            )
            editors_data["search"] = edited_df
        else:
            # 品牌列表顯示
            brands_to_show = selected_brands if selected_brands else all_brands
            for brand in brands_to_show:
                brand_df = base_df[base_df["品牌"] == brand].copy()
                if not brand_df.empty:
                    # ★★★ 關鍵修改：expanded=False (預設折疊) ★★★
                    with st.expander(f"🏷️ {brand} ({len(brand_df)})", expanded=False):
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

        # --- 底部：前往結帳按鈕 ---
        items_to_add_preview = []
        count_new_items = 0
        for key, df_result in editors_data.items():
            selected = df_result[ (df_result["訂購數量"] > 0) | (df_result["搭贈數量"] > 0) ]
            if not selected.empty:
                items_to_add_preview.append(selected)
                count_new_items += len(selected)

        st.markdown("---")
        col_space, col_action = st.columns([3, 1])
        
        with col_action:
            btn_label = f"🛒 加入並前往結帳 ({count_new_items} 新項目)" if count_new_items > 0 else "🛒 前往結帳確認"
            
            if st.button(btn_label, type="primary", use_container_width=True):
                # 1. 檢查業務客戶
                if not selected_cust_name or not selected_sales_name:
                    st.error("⚠️ 請先在上方選擇「業務」與「客戶」")
                else:
                    # 2. 加入商品
                    if items_to_add_preview:
                        for df_chunk in items_to_add_preview:
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
                        keys_to_clear = [key for key in st.session_state.keys() if key.startswith("editor_")]
                        for key in keys_to_clear:
                            del st.session_state[key]

                    # 存檔訂單資訊
                    st.session_state.confirmed_sales = selected_sales_name
                    st.session_state.confirmed_cust = selected_cust_name
                    st.session_state.confirmed_date = order_date

                    # 3. 切換頁面
                    if len(st.session_state.cart_list) > 0:
                        st.session_state.current_step = 2
                        st.rerun()
                    else:
                        st.warning("請至少選擇一項商品。")

    # ---------------------------------------------------------
    # STEP 2: 購物車結帳頁面
    # ---------------------------------------------------------
    elif st.session_state.current_step == 2:
        st.title("📋 步驟 2/2：確認訂單")
        
        c_sales = st.session_state.confirmed_sales
        c_cust = st.session_state.confirmed_cust
        c_date = st.session_state.confirmed_date.strftime('%Y-%m-%d')

        st.info(f"👤 業務：**{c_sales}** |  🏢 客戶：**{c_cust}** |  📅 日期：**{c_date}**")

        if len(st.session_state.cart_list) > 0:
            cart_df = pd.DataFrame(st.session_state.cart_list)
            
            st.markdown("##### 購物車內容 (可直接修改或刪除)")
            edited_cart_df = st.data_editor(
                cart_df,
                column_config={
                    "產品名稱": st.column_config.TextColumn(disabled=True),
                    "訂購數量": st.column_config.NumberColumn(min_value=0, step=1),
                    "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1),
                },
                column_order=["產品名稱", "訂購數量", "搭贈數量"],
                use_container_width=True,
                num_rows="dynamic",
                key="cart_editor_final",
                height=400
            )
            
            if not edited_cart_df.equals(cart_df):
                st.session_state.cart_list = edited_cart_df.to_dict('records')
                st.rerun()

            st.divider()
            
            col_back, col_submit = st.columns([1, 3])
            
            with col_back:
                if st.button("⬅️ 返回繼續選購", use_container_width=True):
                    st.session_state.current_step = 1
                    st.rerun()
            
            with col_submit:
                if st.button("✅ 確認無誤，送出訂單", type="primary", use_container_width=True):
                    
                    with st.spinner("正在寫入雲端資料庫..."):
                        current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
                        if "BillNo" not in current_history.columns: current_history["BillNo"] = ""
                        current_history["BillNo"] = current_history["BillNo"].astype(str).str.replace("'", "", regex=False)

                        # 使用存檔的資訊
                        sales_row = df_salespeople[df_salespeople["業務名稱"] == c_sales]
                        if not sales_row.empty:
                            raw_val = sales_row.iloc[0]["業務編號"]
                            try:
                                val_int = int(float(raw_val))
                                s_id_2digits = f"{val_int:02d}"
                            except:
                                s_str = str(raw_val).strip()
                                s_id_2digits = s_str.zfill(2)[-2:]
                        else:
                            s_id_2digits = "00"

                        date_str_8 = st.session_state.confirmed_date.strftime('%Y%m%d')
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
                        
                        raw_bill_no = f"{prefix}{str(next_seq).zfill(3)}"
                        final_bill_no_for_sheet = f"'{raw_bill_no}" 
                        
                        cust_row = df_customers[df_customers["客戶名稱"] == c_cust]
                        c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"

                        new_rows = []
                        for item in st.session_state.cart_list:
                            if item["訂購數量"] > 0:
                                new_rows.append({
                                    "BillDate": date_str_8,
                                    "BillNo": final_bill_no_for_sheet,
                                    "PersonID": s_id_2digits,
                                    "PersonName": c_sales,
                                    "CustID": c_id,
                                    "ProdID": item["產品編號"],
                                    "ProdName": item["產品名稱"],
                                    "Quantity": item["訂購數量"]
                                })
                            if item["搭贈數量"] > 0:
                                new_rows.append({
                                    "BillDate": date_str_8,
                                    "BillNo": final_bill_no_for_sheet,
                                    "PersonID": s_id_2digits,
                                    "PersonName": c_sales,
                                    "CustID": c_id,
                                    "ProdID": item["產品編號"],
                                    "ProdName": f"{item['產品名稱']} (搭贈)", 
                                    "Quantity": item["搭贈數量"]
                                })

                        updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                        conn.update(worksheet="訂單紀錄", data=updated_history)
                        
                        # 清空與重置
                        st.cache_data.clear()
                        st.session_state.cart_list = []
                        st.session_state.current_step = 1 # 回到第一頁
                        
                        if "sb_sales" in st.session_state: del st.session_state["sb_sales"]
                        if "sb_cust" in st.session_state: del st.session_state["sb_cust"]
                        
                        st.balloons()
                        st.success(f"訂單 {raw_bill_no} 建立成功！即將返回首頁...")
                        time.sleep(2)
                        st.rerun()
        else:
            st.warning("購物車是空的，請返回選購。")
            if st.button("⬅️ 返回選購"):
                st.session_state.current_step = 1
                st.rerun()

# ==========================================
# 🔧 後台管理
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理")
    try:
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        st.markdown(f"👉 [開啟 Google 試算表]({sheet_url})")
    except: pass
    st.divider()
    st.dataframe(df_order_history, use_container_width=True)
    if st.button("🔄 重新整理"):
        st.cache_data.clear()
        st.rerun()