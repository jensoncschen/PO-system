import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
import traceback
import io 

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統", layout="wide", page_icon="🛍️")

# --- CSS 優化 ---
st.markdown("""
    <style>
    div[data-testid="stNumberInput"] input {
        font-size: 16px !important;
        height: 40px !important;
        text-align: center !important;
        font-weight: bold;
    }
    div[data-testid="stNumberInput"] input::placeholder {
        color: #cccccc;
        font-weight: normal;
    }
    div.stButton > button {
        height: 55px !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 12px;
    }
    div.stButton > button[kind="primary"] {
        background-color: #28a745;
        border-color: #28a745;
    }
    hr { margin-top: 0.5rem; margin-bottom: 0.5rem; }
    .input-label {
        display: flex; align-items: center; justify-content: flex-end; 
        height: 40px; font-weight: bold; color: #555;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 🛠️ 核心輔助函式
# ==========================================
def get_sales_id_3digits(sales_name, df_sales):
    if not sales_name: return "000"
    sales_row = df_sales[df_sales["業務名稱"] == sales_name]
    if sales_row.empty: return "000"
    raw_val = sales_row.iloc[0]["業務編號"]
    try:
        return f"{int(float(raw_val)):03d}"
    except:
        return str(raw_val).strip().zfill(3)[-3:]

def clean_barcode(val):
    s = str(val).strip() 
    if s.endswith('.0'): s = s[:-2]
    if s.lower() in ['nan', 'none', '']: return ''
    return s

@st.cache_data(show_spinner=False)
def generate_excel_file(df):
    excel_buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='訂單紀錄')
    except:
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='訂單紀錄')
    return excel_buffer.getvalue()

def submit_new_order(cart_list, sales_name, cust_name, order_date, conn, df_sales, df_cust):
    s_id_3digits = get_sales_id_3digits(sales_name, df_sales)
    s_id_2digits_for_billno = s_id_3digits[-2:]
    date_str_8 = order_date.strftime('%Y%m%d')
    prefix = f"{s_id_2digits_for_billno}{date_str_8}"
    
    cust_row = df_cust[df_cust["客戶名稱"] == cust_name]
    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"
    
    # 【優化：結帳時才即時讀取最新訂單紀錄計算序號】
    with st.spinner("⏳ 正在取得最新訂單序號..."):
        current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
    
    if "BillNo" not in current_history.columns: current_history["BillNo"] = ""
    current_history["BillNo"] = current_history["BillNo"].astype(str).str.replace("'", "", regex=False)
    
    existing_ids = current_history["BillNo"].astype(str).tolist()
    matching_ids = [oid for oid in existing_ids if oid.startswith(prefix) and len(oid) == 13]
    if matching_ids:
        seqs = [int(oid[-3:]) for oid in matching_ids if oid[-3:].isdigit()]
        next_seq = max(seqs) + 1 if seqs else 1
    else: 
        next_seq = 1
    
    raw_bill_no = f"{prefix}{str(next_seq).zfill(3)}"
    final_bill_no = f"'{raw_bill_no}"
    final_person_id = f"'{s_id_3digits}"
    
    new_rows = []
    for item in cart_list:
        if item["訂購數量"] > 0:
            new_rows.append({
                "BillDate": date_str_8, "BillNo": final_bill_no,
                "PersonID": final_person_id, "PersonName": sales_name,
                "CustID": c_id, "ProdID": item["產品編號"], "ProdName": item["產品名稱"],
                "Quantity": item["訂購數量"]
            })
        if item["搭贈數量"] > 0:
            new_rows.append({
                "BillDate": date_str_8, "BillNo": final_bill_no,
                "PersonID": final_person_id, "PersonName": sales_name,
                "CustID": c_id, "ProdID": item["產品編號"], "ProdName": f"{item['產品名稱']} (搭贈)", 
                "Quantity": item["搭贈數量"]
            })

    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
    conn.update(worksheet="訂單紀錄", data=updated_history)
    return raw_bill_no

# --- 快取機制 ---
@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        df_cust = conn.read(worksheet="客戶資料")
        df_prod = conn.read(worksheet="產品資料")
        df_sales = conn.read(worksheet="業務資料") 
        # 【優化：移除了全域的 df_order 讀取，前台開檔速度翻倍】
        
        for df in [df_cust, df_sales, df_prod]:
            if df is None: return None, None, None
            
        df_cust.columns = df_cust.columns.str.strip()
        df_prod.columns = df_prod.columns.str.strip()
        df_sales.columns = df_sales.columns.str.strip()
            
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "品類" not in df_prod.columns: df_prod["品類"] = "一般"
        if "國際條碼" not in df_prod.columns: df_prod["國際條碼"] = ""
        
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        
        df_prod["品類"] = df_prod["品類"].fillna("一般")
        df_prod["國際條碼"] = df_prod["國際條碼"].apply(clean_barcode)
        
        return df_cust, df_prod, df_sales
        
    except Exception as e:
        st.error(f"⚠️ 資料庫連線異常，錯誤原因：{e}")
        print(traceback.format_exc())
        return None, None, None

# 【優化：接收參數同步減少一個】
df_customers, df_products, df_salespeople = fetch_all_data()

if df_customers is None:
    st.stop()

# ★ 建立全域產品查表字典 ★
global_prod_dict = df_products.drop_duplicates(subset=["產品名稱"]).set_index("產品名稱").to_dict('index')

# --- Session State ---
if 'cart_list' not in st.session_state: st.session_state.cart_list = []
if 'input_reset_trigger' not in st.session_state: st.session_state.input_reset_trigger = 0
if 'form_reset_trigger' not in st.session_state: st.session_state.form_reset_trigger = 0

# --- 左側導航 ---
st.sidebar.title("☁️ 系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "📥 訂單匯出", "🔧 後台：資料管理"])
st.sidebar.markdown("---")

st.sidebar.markdown("### 🛒 購物車狀態")
cart_len = len(st.session_state.cart_list)
if cart_len > 0:
    st.sidebar.success(f"已加入 {cart_len} 筆商品")
    st.sidebar.dataframe(pd.DataFrame(st.session_state.cart_list)[["產品名稱","訂購數量"]], hide_index=True)
    if st.sidebar.button("🗑️ 清空購物車"):
        st.session_state.cart_list = []
        st.rerun()
else:
    st.sidebar.info("購物車是空的")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 強制更新雲端資料"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 🚀 1. 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    st.title("🚀 快速下單系統")

    form_suffix = f"_{st.session_state.form_reset_trigger}"

    # 頂部狀態小卡片
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 2, 1.5])
        with c1:
            sales_list = df_salespeople["業務名稱"].unique().tolist()
            selected_sales_name = st.selectbox(
                "👤 業務", sales_list, index=None, placeholder="選擇業務...", key=f"sales_sb{form_suffix}"
            )
        with c2:
            current_cust = []
            if selected_sales_name:
                current_cust = df_customers[df_customers["業務名稱"]==selected_sales_name]["客戶名稱"].unique().tolist()
            selected_cust_name = st.selectbox(
                "🏢 客戶", current_cust, index=None, placeholder="選擇客戶...", key=f"cust_sb{form_suffix}"
            )
        with c3:
            order_date = st.date_input("📅 日期", datetime.now())

    # 【第一步優化：抽取結帳共同核心，供雙向按鈕呼叫】
    def trigger_order_submission():
        if not selected_sales_name or not selected_cust_name:
            st.error("⚠️ 請確認最上方已正確選擇「業務」與「客戶」！")
        else:
            with st.spinner("⏳ 正在寫入雲端..."):
                generated_bill_no = submit_new_order(
                    st.session_state.cart_list, 
                    selected_sales_name, 
                    selected_cust_name, 
                    order_date, 
                    conn, 
                    df_salespeople, 
                    df_customers
                )
                st.session_state.cart_list = []
                st.session_state.input_reset_trigger += 1 
                st.session_state.form_reset_trigger += 1  
                st.cache_data.clear()
                st.balloons()
                st.success(f"🎉 訂單 {generated_bill_no} 建立成功！")
                time.sleep(2)
                st.rerun()

    # 【第一步優化：購物車動態橫條 + 雙向結帳按鈕 (第一向：頂部結帳)】
    cart_count = len(st.session_state.cart_list)
    if cart_count > 0:
        with st.container(border=True):
            cb1, cb2 = st.columns([3, 1])
            with cb1:
                st.markdown(f"### 🛒 購物車：動態累計已加入 **{cart_count}** 項商品")
            with cb2:
                if st.button("⚡ 頂部快速結帳", type="primary", use_container_width=True, key="top_checkout_btn"):
                    trigger_order_submission()

    st.divider()
    st.subheader("➕ 新增商品")
    
    # ... 現有商品篩選與加入購物車的表單程式碼 (過渡上下文保留) ...
    # ... (包含 barcode_input、selected_displays、batch_form 提交等邏輯皆未變動) ...

    st.divider()
    st.subheader(f"📋 準備送出 ({len(st.session_state.cart_list)})")

    if len(st.session_state.cart_list) > 0:
        cart_df = pd.DataFrame(st.session_state.cart_list)
        
        edited_cart = st.data_editor(
            cart_df,
            column_config={
                "產品名稱": st.column_config.TextColumn(disabled=True),
                "訂購數量": st.column_config.NumberColumn(min_value=0, step=1),
                "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1),
            },
            column_order=["產品名稱", "訂購數量", "搭贈數量"],
            use_container_width=True,
            num_rows="dynamic",
            key="final_cart_editor"
        )
        
        if not edited_cart.equals(cart_df):
            st.session_state.cart_list = edited_cart.to_dict('records')

        st.markdown("")
        col_submit_space, col_submit_btn = st.columns([1, 2])
        with col_submit_btn:
            # 【第一步優化：雙向結帳按鈕 (第二向：底部結帳)】
            if st.button("✅ 確認結帳，送出訂單", type="primary", use_container_width=True, key="bottom_checkout_btn"):
                trigger_order_submission()
    else:
        st.info("👇 請在上方篩選並加入商品")

# ==========================================
# 📥 2. 中台：訂單匯出
# ==========================================
elif page == "📥 訂單匯出":
    st.title("📥 訂單匯出與清理")
    st.info("💡 內勤人員專屬：您可在此下載完整訂單 Excel，並在處理完畢後一鍵清空雲端紀錄。")

    # 【優化：只有進到此頁面時才單獨去讀取歷史紀錄，不卡前台速度】
    with st.spinner("⏳ 正在讀取雲端訂單紀錄..."):
        df_order_history = conn.read(worksheet="訂單紀錄", ttl=0)
        if "BillNo" in df_order_history.columns:
            df_order_history["BillNo"] = df_order_history["BillNo"].astype(str).str.replace("'", "", regex=False)
        if "PersonID" in df_order_history.columns:
            df_order_history["PersonID"] = df_order_history["PersonID"].astype(str).str.replace("'", "", regex=False)

    st.subheader(f"📋 目前雲端共有 {len(df_order_history)} 筆訂單紀錄")
    st.dataframe(df_order_history, use_container_width=True, height=400)

    st.divider()
    st.subheader("⚙️ 匯出與清理操作")
    col_export, col_clear = st.columns(2, gap="large")

    with col_export:
        st.markdown("##### 1️⃣ 下載 Excel 備份")
        st.caption("將目前的訂單紀錄完整下載為 Excel 檔案。")
        
        if not df_order_history.empty:
            excel_data = generate_excel_file(df_order_history)
            download_name = f"訂單紀錄_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            st.download_button(
                label="📥 點擊下載 Excel 檔",
                data=excel_data,
                file_name=download_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
        else:
            st.button("📥 目前無資料可匯出", disabled=True, use_container_width=True)

    with col_clear:
        st.markdown("##### 2️⃣ 清除雲端紀錄")
        st.caption("⚠️ 警告：清除後將徹底刪除雲端訂單資料。請務必先執行左側下載備份！")
        confirm_clear = st.checkbox("✅ 我確認已下載 Excel 備份，同意徹底清除雲端紀錄", key="confirm_clear_cb")
        
        if st.button("🗑️ 清空所有訂單紀錄", type="primary", use_container_width=True, disabled=not confirm_clear):
            with st.spinner("正在安全刪除雲端紀錄..."):
                empty_df = pd.DataFrame(columns=df_order_history.columns)
                conn.update(worksheet="訂單紀錄", data=empty_df)
                st.cache_data.clear()
                st.success("✅ 雲端訂單紀錄已完全清空！")
                time.sleep(2)
                st.rerun()

# ==========================================
# 🔧 3. 後台：資料管理
# ==========================================
elif page == "🔧 後台：資料管理":
    st.title("🔧 後台管理")
    try:
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        st.markdown(f"👉 [開啟 Google 試算表編輯基礎資料]({sheet_url})")
    except: pass
    st.divider()
    st.info("💡 如需查看或匯出訂單，請前往左側選單的「📥 訂單匯出」頁面。")