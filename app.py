import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 (使用 Wide 模式) ---
st.set_page_config(page_title="雲端訂購系統 (右側懸浮版)", layout="wide", page_icon="🛍️")

# --- CSS 樣式注入：讓右側欄位懸浮固定 (Sticky) ---
st.markdown("""
    <style>
    /* 針對寬螢幕，讓第二個 Column (右側欄) 變成 Sticky */
    @media (min-width: 992px) {
        div[data-testid="column"]:nth-of-type(2) {
            position: sticky;
            top: 60px; /* 距離頂部的高度 */
            height: calc(100vh - 60px);
            overflow-y: auto; /* 內容太多時可捲動 */
            background-color: #f8f9fa; /* 淺灰背景區隔 */
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #dee2e6;
        }
    }
    /* 調整一下標題間距 */
    .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

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

# --- 左側原生側邊欄 (只保留導航與更新) ---
st.sidebar.title("☁️ 系統導航")
if st.sidebar.button("🔄 強制更新資料", key="btn_update_data"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "🔧 後台：資料管理"])
st.sidebar.markdown("---")
st.sidebar.info("💡 提示：右側欄位現在會懸浮跟隨，方便隨時結帳。")

# ==========================================
# 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🛒 業務下單專區")
    
    # --- 1. 基本資訊區 ---
    with st.container():
        col_sales, col_cust, col_date = st.columns(3)
        
        # A. 選擇業務
        with col_sales:
            sales_list = df_salespeople["業務名稱"].unique().tolist() if not df_salespeople.empty else []
            selected_sales_name = st.selectbox(
                "👤 承辦業務", 
                sales_list, 
                index=None, 
                placeholder="請先選擇業務員...",
                key="sb_sales"
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
                placeholder=placeholder_text,
                key="sb_cust"
            )

        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 定義送出訂單邏輯 (BillNo 修正版) ---
    def submit_order_logic():
        if not selected_cust_name or not selected_sales_name:
            st.error("⚠️ 無法送出：請確認已選擇「業務」與「客戶」")
            return
        if len(st.session_state.cart_list) == 0:
            st.error("⚠️ 購物車是空的")
            return

        with st.spinner("正在處理訂單資料..."):
            current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
            if "BillNo" not in current_history.columns: current_history["BillNo"] = ""

            # ==========================================
            # ★ 核心修正：業務編號轉字串邏輯 (個位數補0) ★
            # ==========================================
            sales_row = df_salespeople[df_salespeople["業務名稱"] == selected_sales_name]
            if not sales_row.empty:
                raw_val = sales_row.iloc[0]["業務編號"]
                try:
                    # 嘗試轉為浮點數再轉整數 (處理 6.0 或 "6" 或 6)
                    val_float = float(raw_val)
                    val_int = int(val_float)
                    # 格式化為2位數，不足補0 (6 -> "06", 12 -> "12")
                    s_id_2digits = f"{val_int:02d}"
                except:
                    # 如果失敗 (例如是純英文編號)，退回原本的字串處理
                    s_str = str(raw_val).strip()
                    s_id_2digits = s_str.zfill(2)[-2:]
            else:
                s_id_2digits = "00"
            # ==========================================

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
            
            # 重置選項
            if "sb_sales" in st.session_state: del st.session_state["sb_sales"]
            if "sb_cust" in st.session_state: del st.session_state["sb_cust"]
            
            st.balloons()
            st.success(f"訂單 {final_bill_no} 建立成功！")
            time.sleep(2)
            st.rerun()

    # --- 版面配置：左側(列表) vs 右側(懸浮操作區) ---
    col_main, col_right = st.columns([2.8, 1.2], gap="medium") # 調整比例

    # ==========================
    # LEFT COLUMN: 產品選擇區
    # ==========================
    with col_main:
        st.subheader("📦 產品列表")
        
        # 篩選區
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

        # 顯示編輯器
        editors_data = {} 
        
        if search_product_name:
            st.info(f"📍 搜尋結果：{search_product_name}")
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
            brands_to_show = selected_brands if selected_brands else all_brands
            if not brands_to_show:
                st.warning("無產品顯示")
            else:
                for brand in brands_to_show:
                    brand_df = base_df[base_df["品牌"] == brand].copy()
                    if not brand_df.empty:
                        with st.expander(f"🏷️ {brand} ({len(brand_df)})", expanded=True):
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

        # 收集左側輸入的資料 (準備傳遞給右側顯示)
        items_to_add_preview = []
        for key, df_result in editors_data.items():
            selected = df_result[ (df_result["訂購數量"] > 0) | (df_result["搭贈數量"] > 0) ]
            if not selected.empty:
                items_to_add_preview.append(selected)

    # ==========================
    # RIGHT COLUMN: 懸浮快捷區
    # ==========================
    with col_right:
        st.write("### 🛒 快捷操作區")
        
        # 區塊 1: 顯示「目前正在輸入」的商品 (取代原本的折疊檢視)
        st.markdown("##### ➕ 準備加入...")
        
        if items_to_add_preview:
            # 彙整預覽資料
            preview_df = pd.concat(items_to_add_preview)
            st.dataframe(
                preview_df[["產品名稱", "訂購數量", "搭贈數量"]], 
                use_container_width=True, 
                hide_index=True,
                height=150 # 固定高度避免太長
            )
            
            # 加入購物車按鈕 (直接在這裡)
            if st.button("⬇️ 加入購物車", type="primary", use_container_width=True, key="btn_right_add"):
                if not selected_cust_name or not selected_sales_name:
                    st.error("請先選擇業務與客戶")
                else:
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
                    st.toast("✅ 已加入購物車！")
                    time.sleep(0.5)
                    st.rerun()
        else:
            st.caption("👈 請在左側列表輸入數量")
            st.button("⬇️ 加入購物車", disabled=True, use_container_width=True)

        st.divider()

        # 區塊 2: 購物車總覽 (可編輯)
        st.markdown(f"##### 📋 待送出 ({len(st.session_state.cart_list)})")
        
        if len(st.session_state.cart_list) > 0:
            cart_df = pd.DataFrame(st.session_state.cart_list)
            
            # 購物車編輯器
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
                key="cart_editor_right",
                height=300 # 限制高度
            )
            
            # 同步修改
            if not edited_cart_df.equals(cart_df):
                st.session_state.cart_list = edited_cart_df.to_dict('records')
                st.rerun()

            col_sub, col_clr = st.columns([2, 1])
            with col_clr:
                if st.button("清空", key="btn_clr_right"):
                    st.session_state.cart_list = []
                    st.rerun()
            with col_sub:
                if st.button("✅ 送出訂單", type="primary", use_container_width=True, key="btn_sub_right"):
                    submit_order_logic()
        else:
            st.info("購物車目前是空的")

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