import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
import traceback

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (專家重構版)", layout="wide", page_icon="🛍️")

# --- CSS 優化 ---
st.markdown("""
    <style>
    div[data-testid="stNumberInput"] input {
        font-size: 20px !important;
        height: 50px !important;
        text-align: center !important;
        font-weight: bold;
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
    </style>
    """, unsafe_allow_html=True)

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 🛠️ 核心輔助函式 (Helpers)
# ==========================================
def get_sales_id_2digits(sales_name, df_sales):
    if not sales_name: return "00"
    sales_row = df_sales[df_sales["業務名稱"] == sales_name]
    if sales_row.empty: return "00"
    
    raw_val = sales_row.iloc[0]["業務編號"]
    try:
        return f"{int(float(raw_val)):02d}"
    except:
        return str(raw_val).strip().zfill(2)[-2:]

# --- 快取機制 ---
@st.cache_data(ttl=300) 
def fetch_all_data():
    try:
        df_cust = conn.read(worksheet="客戶資料")
        df_prod = conn.read(worksheet="產品資料")
        df_sales = conn.read(worksheet="業務資料") 
        df_order = conn.read(worksheet="訂單紀錄")
        
        for df in [df_cust, df_sales, df_prod, df_order]:
            if df is None: return None, None, None, None
            
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "品類" not in df_prod.columns: df_prod["品類"] = "一般"
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        df_order["BillNo"] = df_order["BillNo"].astype(str).str.replace("'", "", regex=False)
        df_prod["品類"] = df_prod["品類"].fillna("一般")
        
        return df_cust, df_prod, df_sales, df_order
        
    except Exception as e:
        st.error(f"⚠️ 資料庫連線異常，錯誤原因：{e}")
        print(traceback.format_exc())
        return None, None, None, None

# --- 載入資料 ---
df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.stop()

# --- Session State 初始化 ---
if 'cart_list' not in st.session_state: st.session_state.cart_list = []
if 'input_reset_trigger' not in st.session_state: st.session_state.input_reset_trigger = 0
if 'form_reset_trigger' not in st.session_state: st.session_state.form_reset_trigger = 0

# --- 側邊欄 ---
st.sidebar.title("🛒 購物車")
cart_len = len(st.session_state.cart_list)
if cart_len > 0:
    st.sidebar.success(f"已加入 {cart_len} 筆商品")
    st.sidebar.dataframe(pd.DataFrame(st.session_state.cart_list)[["產品名稱","訂購數量"]], hide_index=True)
    if st.sidebar.button("🗑️ 清空購物車"):
        st.session_state.cart_list = []
        st.rerun()
else:
    st.sidebar.info("購物車是空的")

if st.sidebar.button("🔄 更新資料庫"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 🚀 主畫面
# ==========================================
st.title("🚀 快速下單系統")

form_suffix = f"_{st.session_state.form_reset_trigger}"

with st.container(border=True):
    c1, c2 = st.columns(2)
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
    
    order_date = st.date_input("📅 日期", datetime.now())

st.divider()

st.subheader("➕ 批次新增商品")

input_suffix = f"_{st.session_state.input_reset_trigger}"
col_filter_brand, col_filter_cat = st.columns(2)

# --- 第一層：品牌 ---
with col_filter_brand:
    brand_options = ["全部"] + df_products["品牌"].unique().tolist()
    selected_brand_filter = st.selectbox("1️⃣ 品牌篩選", brand_options, key=f"brand{input_suffix}")

# --- 第二層：品類 ---
with col_filter_cat:
    df_step1 = df_products.copy()
    if selected_brand_filter != "全部":
        df_step1 = df_step1[df_step1["品牌"] == selected_brand_filter]
    
    cat_options = ["全部"] + df_step1["品類"].unique().tolist()
    selected_cat_filter = st.selectbox("2️⃣ 品類篩選", cat_options, key=f"cat{input_suffix}")

# --- 第三層：產品多選 ---
df_step2 = df_step1.copy()
if selected_cat_filter != "全部":
    df_step2 = df_step2[df_step2["品類"] == selected_cat_filter]

product_list = df_step2["產品名稱"].unique().tolist()

selected_products_batch = st.multiselect(
    "3️⃣ 選擇商品 (可多選，最多20樣)", 
    product_list, 
    max_selections=20,
    placeholder="請點選加入多項商品...",
    key=f"prod_multi{input_suffix}"
)

# --- 批次輸入表單 ---
if selected_products_batch:
    st.info(f"👇 您已選擇 {len(selected_products_batch)} 項商品，請輸入數量後一次送出")
    
    with st.form(key=f"batch_form{input_suffix}"):
        
        # ★★★ 修復點：加上 drop_duplicates 確保產品名稱唯一，避免報錯 ★★★
        prod_dict = df_products.drop_duplicates(subset=["產品名稱"]).set_index("產品名稱").to_dict('index')
        
        for p_name in selected_products_batch:
            p_info = prod_dict.get(p_name, {})
            p_cat = p_info.get('品類', '一般')
            
            st.markdown(f"**{p_name}** <span style='color:gray; font-size:0.8em'>({p_cat})</span>", unsafe_allow_html=True)
            
            c_q, c_g = st.columns(2)
            with c_q:
                st.number_input("訂購", min_value=0, step=1, key=f"q_{p_name}", label_visibility="collapsed")
            with c_g:
                st.number_input("搭贈", min_value=0, step=1, key=f"g_{p_name}", label_visibility="collapsed")
            st.divider()

        submitted = st.form_submit_button("⬇️ 全部加入購物車", type="primary", use_container_width=True)
        
        if submitted:
            if not selected_sales_name or not selected_cust_name:
                st.error("⚠️ 請先在最上方選擇「業務」與「客戶」！")
            else:
                items_added_count = 0
                keys_to_clear = [] 
                
                for p_name in selected_products_batch:
                    q_key = f"q_{p_name}"
                    g_key = f"g_{p_name}"
                    
                    q_val = st.session_state.get(q_key, 0)
                    g_val = st.session_state.get(g_key, 0)
                    
                    if q_val > 0 or g_val > 0:
                        p_info = prod_dict.get(p_name, {})
                        
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
                    
                    keys_to_clear.extend([q_key, g_key])
                
                if items_added_count > 0:
                    for k in keys_to_clear:
                        if k in st.session_state:
                            del st.session_state[k]
                            
                    st.session_state.input_reset_trigger += 1 
                    st.toast(f"✅ 成功加入 {items_added_count} 項商品！")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("⚠️ 所有商品的數量都是 0，未加入任何項目")

# 3. 購物車清單與結帳
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
        st.rerun()

    st.markdown("")
    col_submit_space, col_submit_btn = st.columns([1, 2])
    with col_submit_btn:
        if st.button("✅ 確認結帳，送出訂單", type="primary", use_container_width=True):
            with st.spinner("⏳ 正在寫入雲端..."):
                
                s_id_2digits = get_sales_id_2digits(selected_sales_name, df_salespeople)
                date_str_8 = order_date.strftime('%Y%m%d')
                prefix = f"{s_id_2digits}{date_str_8}"
                
                cust_row = df_customers[df_customers["客戶名稱"] == selected_cust_name]
                c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"
                
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
                
                new_rows = []
                for item in st.session_state.cart_list:
                    if item["訂購數量"] > 0:
                        new_rows.append({
                            "BillDate": date_str_8, "BillNo": final_bill_no,
                            "PersonID": s_id_2digits, "PersonName": selected_sales_name,
                            "CustID": c_id, "ProdID": item["產品編號"], "ProdName": item["產品名稱"],
                            "Quantity": item["訂購數量"]
                        })
                    if item["搭贈數量"] > 0:
                        new_rows.append({
                            "BillDate": date_str_8, "BillNo": final_bill_no,
                            "PersonID": s_id_2digits, "PersonName": selected_sales_name,
                            "CustID": c_id, "ProdID": item["產品編號"], "ProdName": f"{item['產品名稱']} (搭贈)", 
                            "Quantity": item["搭贈數量"]
                        })

                updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                conn.update(worksheet="訂單紀錄", data=updated_history)
                
                st.session_state.cart_list = []
                st.session_state.input_reset_trigger += 1 
                st.session_state.form_reset_trigger += 1  
                
                st.cache_data.clear()
                
                st.balloons()
                st.success(f"🎉 訂單 {raw_bill_no} 建立成功！")
                time.sleep(2)
                st.rerun()
else:
    st.info("👇 請在上方篩選並加入商品")