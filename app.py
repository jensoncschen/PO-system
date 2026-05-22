import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
import traceback
import io
import html

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統", layout="wide", page_icon="🛍️")

# --- CSS：Phase 1 極簡清晰介面（手機優先、少量覆蓋） ---
st.markdown("""
    <style>
    :root {
        --app-bg: #f6f7f9;
        --surface: #ffffff;
        --surface-soft: #f9fafb;
        --text-main: #111827;
        --text-muted: #6b7280;
        --text-soft: #9ca3af;
        --border: #e5e7eb;
        --border-strong: #d1d5db;
        --primary: #2563eb;
        --primary-hover: #1d4ed8;
        --success: #16a34a;
        --danger: #dc2626;
        --radius: 18px;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.06), transparent 28rem),
            var(--app-bg);
        color: var(--text-main);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", sans-serif;
    }

    .main .block-container {
        max-width: 1120px;
        padding-top: 1.25rem;
        padding-bottom: 7.5rem;
    }

    h1, h2, h3, .stMarkdown p, label, span {
        color: var(--text-main);
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: var(--text-main) !important;
    }

    .hero-card {
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid var(--border);
        border-radius: 24px;
        padding: 1.25rem 1.35rem;
        margin-bottom: 1.15rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
    }

    .page-title {
        font-size: 2.15rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.15;
        margin-bottom: 0.35rem;
    }

    .page-subtitle {
        color: var(--text-muted);
        font-size: 0.98rem;
        line-height: 1.6;
        margin-bottom: 0.7rem;
    }

    .hero-steps {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.75rem;
    }

    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.32rem 0.65rem;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--surface-soft);
        color: var(--text-muted);
        font-size: 0.82rem;
        font-weight: 650;
    }

    .section-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        margin: 1.15rem 0 0.65rem 0;
    }

    .section-title-wrap {
        display: flex;
        gap: 0.75rem;
        align-items: flex-start;
    }

    .section-index {
        flex: 0 0 auto;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 34px;
        height: 34px;
        border-radius: 12px;
        background: #111827;
        color: #ffffff !important;
        font-size: 0.92rem;
        font-weight: 800;
        box-shadow: 0 6px 14px rgba(17, 24, 39, 0.12);
    }

    .section-title-text {
        font-size: 1.18rem;
        font-weight: 800;
        letter-spacing: -0.015em;
        margin-top: 0.05rem;
    }

    .section-note {
        color: var(--text-muted);
        font-size: 0.9rem;
        line-height: 1.5;
        margin-top: 0.15rem;
    }

    .section-tag {
        padding: 0.3rem 0.62rem;
        border-radius: 999px;
        background: #eef2ff;
        color: #3730a3 !important;
        font-size: 0.78rem;
        font-weight: 750;
        white-space: nowrap;
    }

    .mini-label {
        color: var(--text-muted);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }

    .subsection-title {
        font-size: 0.98rem;
        font-weight: 800;
        margin: 0.25rem 0 0.2rem;
        color: var(--text-main);
    }

    .subsection-caption {
        color: var(--text-muted);
        font-size: 0.88rem;
        margin: 0 0 0.7rem 0;
    }

    .product-title {
        font-size: 1rem;
        font-weight: 800;
        color: var(--text-main);
        margin-bottom: 0.2rem;
    }

    .product-meta {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        color: var(--text-muted);
        background: var(--surface-soft);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 0.2rem 0.55rem;
        font-size: 0.8rem;
        margin-bottom: 0.55rem;
    }

    .cart-summary {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.65rem;
        margin-bottom: 0.75rem;
    }

    .summary-card {
        background: var(--surface-soft);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 0.75rem;
    }

    .summary-label {
        color: var(--text-muted);
        font-size: 0.78rem;
        font-weight: 650;
        margin-bottom: 0.25rem;
    }

    .summary-value {
        color: var(--text-main);
        font-size: 1.35rem;
        line-height: 1;
        font-weight: 850;
        letter-spacing: -0.03em;
    }

    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.96) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 0.1rem;
    }

    input, textarea, select {
        font-size: 16px !important;
        color: var(--text-main) !important;
        -webkit-text-fill-color: var(--text-main) !important;
    }

    div[data-baseweb="input"],
    div[data-baseweb="select"],
    div[data-baseweb="base-input"] {
        border-radius: 14px !important;
        border-color: var(--border-strong) !important;
        background: #ffffff !important;
        min-height: 46px;
        box-shadow: none !important;
    }

    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="base-input"]:focus-within,
    div[data-baseweb="select"]:focus-within {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        min-height: 44px;
    }

    button,
    div.stButton > button,
    button[data-testid="stFormSubmitButton"],
    div[data-testid="stDownloadButton"] button {
        min-height: 46px !important;
        border-radius: 14px !important;
        font-weight: 750 !important;
        border: 1px solid var(--border-strong) !important;
        box-shadow: none !important;
        background: #ffffff !important;
        color: var(--text-main) !important;
        -webkit-text-fill-color: var(--text-main) !important;
    }

    button *,
    div.stButton > button *,
    button[data-testid="stFormSubmitButton"] *,
    div[data-testid="stDownloadButton"] button * {
        color: var(--text-main) !important;
        -webkit-text-fill-color: var(--text-main) !important;
    }

    div.stButton > button[kind="primary"],
    button[data-testid="stFormSubmitButton"],
    div[data-testid="stDownloadButton"] button[kind="primary"] {
        background: var(--primary) !important;
        border-color: var(--primary) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    div.stButton > button[kind="primary"] *,
    button[data-testid="stFormSubmitButton"] *,
    div[data-testid="stDownloadButton"] button[kind="primary"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    div.stButton > button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        border-color: var(--text-soft) !important;
        background: var(--surface-soft) !important;
    }

    div.stButton > button[kind="primary"]:hover,
    button[data-testid="stFormSubmitButton"]:hover,
    div[data-testid="stDownloadButton"] button[kind="primary"]:hover {
        background: var(--primary-hover) !important;
        border-color: var(--primary-hover) !important;
    }

    .stAlert {
        border-radius: 16px !important;
    }

    .sticky-cart-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        min-height: 64px;
        background: rgba(255, 255, 255, 0.94);
        border-top: 1px solid var(--border);
        box-shadow: 0 -12px 28px rgba(15, 23, 42, 0.08);
        z-index: 999992;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 0 1rem;
        backdrop-filter: blur(10px);
    }

    .sticky-cart-content {
        width: min(1040px, 100%);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        color: var(--text-main) !important;
        font-weight: 800;
    }

    .sticky-cart-muted {
        color: var(--text-muted) !important;
        font-size: 0.88rem;
        font-weight: 650;
    }

    hr {
        margin-top: 0.75rem;
        margin-bottom: 0.75rem;
        border-color: var(--border);
    }



    .mobile-status-card {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        align-items: center;
        background: #f8fafc;
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 0.8rem 0.9rem;
        margin-top: 0.55rem;
    }

    .mobile-status-title {
        color: var(--text-muted) !important;
        font-size: 0.78rem;
        font-weight: 750;
        margin-bottom: 0.15rem;
    }

    .mobile-status-value {
        color: var(--text-main) !important;
        font-size: 0.95rem;
        font-weight: 800;
        line-height: 1.35;
    }

    .action-hint {
        display: flex;
        align-items: flex-start;
        gap: 0.55rem;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a !important;
        border-radius: 16px;
        padding: 0.75rem 0.85rem;
        font-size: 0.88rem;
        line-height: 1.45;
        font-weight: 650;
        margin: 0.55rem 0 0.75rem;
    }

    .product-count-chip {
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--border);
        background: #ffffff;
        color: var(--text-muted) !important;
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-size: 0.8rem;
        font-weight: 750;
        margin: 0.2rem 0 0.6rem;
    }

    .cart-review-list {
        display: grid;
        gap: 0.55rem;
        margin: 0.75rem 0 0.75rem;
    }

    .cart-review-item {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        align-items: flex-start;
        background: #ffffff;
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 0.75rem 0.85rem;
    }

    .cart-review-name {
        color: var(--text-main) !important;
        font-size: 0.94rem;
        font-weight: 800;
        line-height: 1.35;
    }

    .cart-review-meta {
        color: var(--text-muted) !important;
        font-size: 0.82rem;
        font-weight: 650;
        margin-top: 0.18rem;
    }

    .cart-review-qty {
        flex: 0 0 auto;
        color: var(--text-main) !important;
        background: var(--surface-soft);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 0.28rem 0.55rem;
        font-size: 0.82rem;
        font-weight: 800;
        white-space: nowrap;
    }

    .cart-final-panel {
        background: #111827;
        color: #ffffff !important;
        border-radius: 18px;
        padding: 0.9rem 1rem;
        margin: 0.85rem 0;
    }

    .cart-final-panel * {
        color: #ffffff !important;
    }

    .cart-final-title {
        font-size: 0.82rem;
        font-weight: 700;
        opacity: 0.72;
        margin-bottom: 0.25rem;
    }

    .cart-final-value {
        font-size: 1rem;
        font-weight: 850;
        line-height: 1.4;
    }

    .mobile-edit-note {
        color: var(--text-muted) !important;
        font-size: 0.82rem;
        font-weight: 650;
        margin: 0.35rem 0 0.55rem;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding: 0.85rem 0.85rem 7.25rem 0.85rem;
        }



        [data-testid="stSidebar"] {
            border-right: none;
        }

        .hero-steps {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.4rem;
        }

        .hero-pill {
            justify-content: center;
            padding: 0.48rem 0.65rem;
        }

        .section-header {
            gap: 0.55rem;
        }

        .section-index {
            width: 32px;
            height: 32px;
            border-radius: 11px;
        }

        .mobile-status-card {
            display: block;
            padding: 0.85rem;
        }

        .mobile-status-card > div + div {
            margin-top: 0.7rem;
            padding-top: 0.7rem;
            border-top: 1px solid var(--border);
        }

        div[data-testid="column"] {
            min-width: 100% !important;
        }

        /* 手機版：一般欄位維持單欄，但表單內的「訂購數／搭贈數」維持左右並排，減少長單滑動距離。 */
        div[data-testid="stForm"] div[data-testid="column"] {
            min-width: 0 !important;
            flex: 1 1 0 !important;
        }

        div[data-testid="stForm"] div[data-testid="column"] > div {
            width: 100% !important;
        }

        div[data-baseweb="input"],
        div[data-baseweb="select"],
        div[data-baseweb="base-input"],
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input {
            min-height: 50px !important;
        }

        button,
        div.stButton > button,
        button[data-testid="stFormSubmitButton"],
        div[data-testid="stDownloadButton"] button {
            min-height: 50px !important;
            font-size: 0.98rem !important;
        }

        .product-meta {
            display: flex;
            width: fit-content;
            max-width: 100%;
            white-space: normal;
            line-height: 1.35;
        }

        .cart-review-item {
            display: block;
        }

        .cart-review-qty {
            display: inline-flex;
            margin-top: 0.55rem;
        }

        .cart-final-panel {
            padding: 0.85rem;
        }

        .sticky-cart-bar {
            min-height: calc(70px + env(safe-area-inset-bottom));
            padding-bottom: env(safe-area-inset-bottom);
        }


        .hero-card {
            padding: 1rem;
            border-radius: 20px;
        }

        .page-title {
            font-size: 1.7rem;
        }

        .page-subtitle {
            font-size: 0.92rem;
        }

        .section-header {
            align-items: flex-start;
            margin-top: 1rem;
        }

        .section-title-text {
            font-size: 1.08rem;
        }

        .section-tag {
            display: none;
        }

        .cart-summary {
            grid-template-columns: 1fr;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {
            font-size: 0.84rem;
        }

        .sticky-cart-content {
            flex-direction: column;
            align-items: flex-start;
            gap: 0.15rem;
        }
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

def safe_html(value):
    return html.escape(str(value))

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
st.sidebar.title("雲端訂購")
page = st.sidebar.radio("前往區塊", ["🛒 前台：下單作業", "📥 訂單匯出", "🔧 後台：資料管理"])
st.sidebar.markdown("---")

st.sidebar.markdown("### 購物車")
cart_len = len(st.session_state.cart_list)
if cart_len > 0:
    st.sidebar.success(f"{cart_len} 筆商品")
    st.sidebar.dataframe(pd.DataFrame(st.session_state.cart_list)[["產品名稱","訂購數量"]], hide_index=True)
    if st.sidebar.button("清空購物車"):
        st.session_state.cart_list = []
        st.rerun()
else:
    st.sidebar.info("購物車是空的")

st.sidebar.markdown("---")
if st.sidebar.button("更新雲端資料"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 🚀 1. 🛒 前台：下單作業
# ==========================================
if page == "🛒 前台：下單作業":
    st.markdown("""
        <div class='hero-card'>
            <div class='page-title'>快速下單</div>
            <div class='page-subtitle'>手機優先的訂單建立流程。單手操作、先加商品、最後一次確認送出。</div>
            <div class='hero-steps'>
                <span class='hero-pill'>1 訂單資訊</span>
                <span class='hero-pill'>2 新增商品</span>
                <span class='hero-pill'>3 購物車確認</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    form_suffix = f"_{st.session_state.form_reset_trigger}"

    # 區塊 1：訂單資訊
    st.markdown("""
        <div class='section-header'>
            <div class='section-title-wrap'>
                <span class='section-index'>1</span>
                <div>
                    <div class='section-title-text'>訂單資訊</div>
                    <div class='section-note'>先確認業務、客戶與日期。這三項會帶入本次訂單。</div>
                </div>
            </div>
            <span class='section-tag'>必填</span>
        </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.25, 1.75, 1], gap="medium")
        with c1:
            sales_list = df_salespeople["業務名稱"].unique().tolist()
            selected_sales_name = st.selectbox(
                "業務", sales_list, index=None, placeholder="選擇業務", key=f"sales_sb{form_suffix}"
            )
        with c2:
            current_cust = []
            if selected_sales_name:
                current_cust = df_customers[df_customers["業務名稱"]==selected_sales_name]["客戶名稱"].unique().tolist()
            selected_cust_name = st.selectbox(
                "客戶", current_cust, index=None, placeholder="選擇客戶", key=f"cust_sb{form_suffix}"
            )
        with c3:
            order_date = st.date_input("日期", datetime.now())

    # 統一結帳動作，保留原本訂單邏輯
    def trigger_order_submission():
        if not selected_sales_name or not selected_cust_name:
            st.error("請確認已選擇業務與客戶。")
        elif len(st.session_state.cart_list) == 0:
            st.warning("購物車目前是空的，請先加入商品。")
        else:
            with st.spinner("正在寫入雲端..."):
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
                st.success(f"訂單 {generated_bill_no} 建立成功。")
                time.sleep(1.2)
                st.rerun()

    cart_count = len(st.session_state.cart_list)
    total_quantity = sum(int(item.get("訂購數量", 0) or 0) for item in st.session_state.cart_list)
    total_gift = sum(int(item.get("搭贈數量", 0) or 0) for item in st.session_state.cart_list)
    if cart_count > 0:
        st.markdown(f"""
            <div class="sticky-cart-bar">
                <div class="sticky-cart-content">
                    <span>{cart_count} 項商品｜訂購 {total_quantity}｜搭贈 {total_gift}</span>
                    <span class="sticky-cart-muted">請到購物車區確認後送出</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # 區塊 2：新增商品
    st.markdown("""
        <div class='section-header'>
            <div class='section-title-wrap'>
                <span class='section-index'>2</span>
                <div>
                    <div class='section-title-text'>新增商品</div>
                    <div class='section-note'>先用條碼或名稱搜尋；需要瀏覽時再用品牌與品類縮小範圍。</div>
                </div>
            </div>
            <span class='section-tag'>可重複加入</span>
        </div>
    """, unsafe_allow_html=True)

    input_suffix = f"_{st.session_state.input_reset_trigger}"

    with st.container(border=True):
        st.markdown("<div class='mini-label'>SEARCH</div>", unsafe_allow_html=True)
        st.markdown("<div class='subsection-title'>商品搜尋</div>", unsafe_allow_html=True)
        barcode_input = st.text_input(
            "條碼或商品名稱", 
            placeholder="掃描條碼，或輸入商品名稱關鍵字",
            key=f"barcode_scan{input_suffix}"
        )

        st.markdown("<div class='subsection-title'>商品篩選</div>", unsafe_allow_html=True)
        st.markdown("<div class='subsection-caption'>沒有搜尋關鍵字時，可用品牌與品類瀏覽商品。</div>", unsafe_allow_html=True)
        col_filter_brand, col_filter_cat = st.columns(2, gap="medium")

        with col_filter_brand:
            brand_options = ["全部"] + df_products["品牌"].unique().tolist()
            selected_brand_filter = st.selectbox("品牌", brand_options, key=f"brand{input_suffix}")

        with col_filter_cat:
            df_step1 = df_products.copy()
            if selected_brand_filter != "全部":
                df_step1 = df_step1[df_step1["品牌"] == selected_brand_filter]
            
            cat_options = ["全部"] + df_step1["品類"].unique().tolist()
            selected_cat_filter = st.selectbox("品類", cat_options, key=f"cat{input_suffix}")

        if barcode_input:
            clean_input = barcode_input.strip()
            if clean_input.isdigit() and len(clean_input) >= 4:
                mask_barcode = df_products["國際條碼"].astype(str) == clean_input
            else:
                mask_barcode = pd.Series(False, index=df_products.index)
                
            mask_name = df_products["產品名稱"].astype(str).str.contains(clean_input, case=False, na=False)
            df_step2 = df_products[mask_barcode | mask_name]
            
            if df_step2.empty:
                st.error(f"找不到包含「{clean_input}」的條碼或商品名稱。")
        else:
            df_step2 = df_step1.copy()
            if selected_cat_filter != "全部":
                df_step2 = df_step2[df_step2["品類"] == selected_cat_filter]

        display_to_name = {}
        for _, row in df_step2.iterrows():
            p_name = row["產品名稱"]
            barcode = str(row["國際條碼"]).strip()
            if barcode:
                display_str = f"{p_name} ｜ 條碼 {barcode}"
            else:
                display_str = p_name
            display_to_name[display_str] = p_name

        display_options = list(display_to_name.keys())
        default_selections = display_options if barcode_input and len(display_options) == 1 else []

        st.markdown("<div class='subsection-title'>選擇商品</div>", unsafe_allow_html=True)
        selected_displays = st.multiselect(
            "選擇商品", 
            options=display_options, 
            default=default_selections, 
            max_selections=20,
            placeholder="選擇一項或多項商品",
            key=f"prod_multi{input_suffix}",
            label_visibility="collapsed"
        )

        selected_products_batch = [display_to_name[disp] for disp in selected_displays]

        if selected_products_batch:
            st.markdown(f"<div class='product-count-chip'>已選擇 {len(selected_products_batch)} 項商品</div>", unsafe_allow_html=True)
            st.markdown("<div class='action-hint'>手機操作建議：數量與搭贈數已左右並排；一次加入多項商品時，請送出前到購物車確認。</div>", unsafe_allow_html=True)
            
            with st.form(key=f"batch_form{input_suffix}"):
                for p_name in selected_products_batch:
                    p_info = global_prod_dict.get(p_name, {})
                    p_cat = p_info.get('品類', '一般')
                    p_brand = p_info.get('品牌', '')
                    p_barcode = p_info.get('國際條碼', '')
                    meta_parts = [x for x in [p_brand, p_cat, f"條碼 {p_barcode}" if p_barcode else ""] if x]
                    meta_text = "｜".join(meta_parts)
                    
                    with st.container(border=True):
                        st.markdown(f"<div class='product-title'>{safe_html(p_name)}</div>", unsafe_allow_html=True)
                        if meta_text:
                            st.markdown(f"<div class='product-meta'>{safe_html(meta_text)}</div>", unsafe_allow_html=True)
                        qty_col, gift_col = st.columns(2, gap="medium")
                        with qty_col:
                            st.number_input("訂購數", min_value=0, step=1, value=None, placeholder="0", key=f"q_{p_name}")
                        with gift_col:
                            st.number_input("搭贈數", min_value=0, step=1, value=None, placeholder="0", key=f"g_{p_name}")

                submitted = st.form_submit_button("加入購物車", use_container_width=True)
                
                if submitted:
                    if not selected_sales_name or not selected_cust_name:
                        st.error("請先在訂單資訊區選擇業務與客戶。")
                    else:
                        items_added_count = 0
                        keys_to_clear = [] 
                        
                        for p_name in selected_products_batch:
                            q_raw = st.session_state.get(f"q_{p_name}")
                            g_raw = st.session_state.get(f"g_{p_name}")
                            
                            q_val = int(q_raw) if q_raw is not None else 0
                            g_val = int(g_raw) if g_raw is not None else 0
                            
                            if q_val > 0 or g_val > 0:
                                p_info = global_prod_dict.get(p_name, {})
                                st.session_state.cart_list.insert(0, {
                                    "業務名稱": selected_sales_name,
                                    "客戶名稱": selected_cust_name,
                                    "產品編號": p_info.get("產品編號", "N/A"),
                                    "產品名稱": p_name,
                                    "品牌": p_info.get("品牌", ""),
                                    "品類": p_info.get("品類", ""),
                                    "訂購數量": q_val,
                                    "搭贈數量": g_val
                                })
                                items_added_count += 1
                            
                            keys_to_clear.extend([f"q_{p_name}", f"g_{p_name}"])
                        
                        if items_added_count > 0:
                            for k in keys_to_clear:
                                if k in st.session_state:
                                    del st.session_state[k]
                                    
                            st.session_state.input_reset_trigger += 1 
                            st.toast(f"成功加入 {items_added_count} 項商品")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning("所有商品的數量皆未輸入，未加入任何項目。")

    # 區塊 3：購物車
    st.markdown("""
        <div class='section-header'>
            <div class='section-title-wrap'>
                <span class='section-index'>3</span>
                <div>
                    <div class='section-title-text'>購物車</div>
                    <div class='section-note'>送出前請確認商品、訂購數與搭贈數。表格內可直接修改數量。</div>
                </div>
            </div>
            <span class='section-tag'>最後確認</span>
        </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        if len(st.session_state.cart_list) > 0:
            cart_df = pd.DataFrame(st.session_state.cart_list)
            total_quantity = int(cart_df["訂購數量"].fillna(0).sum()) if "訂購數量" in cart_df.columns else 0
            total_gift = int(cart_df["搭贈數量"].fillna(0).sum()) if "搭贈數量" in cart_df.columns else 0
            st.markdown(f"""
                <div class='cart-summary'>
                    <div class='summary-card'>
                        <div class='summary-label'>商品項目</div>
                        <div class='summary-value'>{len(cart_df)}</div>
                    </div>
                    <div class='summary-card'>
                        <div class='summary-label'>訂購數量</div>
                        <div class='summary-value'>{total_quantity}</div>
                    </div>
                    <div class='summary-card'>
                        <div class='summary-label'>搭贈數量</div>
                        <div class='summary-value'>{total_gift}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown(
                "<div class='mobile-edit-note'>請在下方表格確認商品與數量；需要修改時可直接調整數字，刪除商品可使用表格列操作。</div>",
                unsafe_allow_html=True
            )
            
            edited_cart = st.data_editor(
                cart_df,
                column_config={
                    "產品名稱": st.column_config.TextColumn("商品", disabled=True, width="large"),
                    "訂購數量": st.column_config.NumberColumn("訂購", min_value=0, step=1, width="small"),
                    "搭贈數量": st.column_config.NumberColumn("搭贈", min_value=0, step=1, width="small"),
                },
                column_order=["產品名稱", "訂購數量", "搭贈數量"],
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="final_cart_editor"
            )
            
            if not edited_cart.equals(cart_df):
                st.session_state.cart_list = edited_cart.to_dict('records')

            final_sales_label = safe_html(selected_sales_name) if selected_sales_name else "尚未選擇業務"
            final_cust_label = safe_html(selected_cust_name) if selected_cust_name else "尚未選擇客戶"
            st.markdown(f"""
                <div class='cart-final-panel'>
                    <div class='cart-final-title'>送出前確認</div>
                    <div class='cart-final-value'>{final_sales_label} → {final_cust_label}</div>
                    <div class='cart-final-title' style='margin-top:0.45rem;'>本次合計</div>
                    <div class='cart-final-value'>{len(st.session_state.cart_list)} 項商品｜訂購 {total_quantity}｜搭贈 {total_gift}</div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("")
            col_clear, col_submit = st.columns([1, 2], gap="medium")
            with col_clear:
                if st.button("清空購物車", use_container_width=True, key="clear_cart_main_btn"):
                    st.session_state.cart_list = []
                    st.rerun()
            with col_submit:
                if st.button("送出訂單", type="primary", use_container_width=True, key="bottom_checkout_btn"):
                    trigger_order_submission()
        else:
            st.info("購物車目前是空的。請先在新增商品區加入商品。")

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