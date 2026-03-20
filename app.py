import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
import traceback
import io 

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (精緻排版版)", layout="wide", page_icon="🛍️")

# --- CSS 優化 (★ 更新：縮小輸入框，優化排版) ---
st.markdown("""
    <style>
    /* 將輸入框高度與字體稍微縮小，看起來更精緻 */
    div[data-testid="stNumberInput"] input {
        font-size: 16px !important;
        height: 40px !important;
        text-align: center !important;
        font-weight: bold;
    }
    /* Placeholder 顏色調淡 */
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
    
    /* 左側標籤的垂直置中對齊魔法 */
    .input-label {
        display: flex; 
        align-items: center; 
        justify-content: flex-end; 
        height: 40px; 
        font-weight: bold;
        color: #555;
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
    if s.endswith('.0'): 
        s = s[:-2]
    if s.lower() in ['nan', 'none', '']:
        return ''
    return s

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
            
        df_cust.columns = df_cust.columns.str.strip()
        df_prod.columns = df_prod.columns.str.strip()
        df_sales.columns = df_sales.columns.str.strip()
        df_order.columns = df_order.columns.str.strip()
            
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "品類" not in df_prod.columns: df_prod["品類"] = "一般"
        if "國際條碼" not in df_prod.columns: df_prod["國際條碼"] = ""
        
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        if "PersonID" not in df_order.columns: df_order["PersonID"] = ""
        
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        df_order["BillNo"] = df_order["BillNo"].astype(str).str.replace("'", "", regex=False)
        df_order["PersonID"] = df_order["PersonID"].astype(str).str.replace("'", "", regex=False)
        
        df_prod["品類"] = df_prod["品類"].fillna("一般")
        df_prod["國際條碼"] = df_prod["國際條碼"].apply(clean_barcode)
        
        return df_cust, df_prod, df_sales, df_order
        
    except Exception as e:
        st.error(f"⚠️ 資料庫連線異常，錯誤原因：{e}")
        print(traceback.format_exc())
        return None, None, None, None

df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.stop()

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

    st.subheader("➕ 新增商品")
    input_suffix = f"_{st.session_state.input_reset_trigger}"

    st.markdown("#### 📷 步驟一：條碼快搜 (支援條碼槍或輸入部分數字)")
    barcode_input = st.text_input(
        "輸入部分條碼、完整條碼，或商品名稱關鍵字後按 Enter", 
        placeholder="例如輸入 12345 尋找條碼，或輸入 iPhone...",
        key=f"barcode_scan{input_suffix}"
    )

    st.markdown("#### 👆 步驟二：無條碼時的手動篩選")
    col_filter_brand, col_filter_cat = st.columns(2)

    with col_filter_brand:
        brand_options = ["全部"] + df_products["品牌"].unique().tolist()
        selected_brand_filter = st.selectbox("1️⃣ 品牌篩選", brand_options, key=f"brand{input_suffix}")

    with col_filter_cat:
        df_step1 = df_products.copy()
        if selected_brand_filter != "全部":
            df_step1 = df_step1[df_step1["品牌"] == selected_brand_filter]
        
        cat_options = ["全部"] + df_step1["品類"].unique().tolist()
        selected_cat_filter = st.selectbox("2️⃣ 品類篩選", cat_options, key=f"cat{input_suffix}")

    if barcode_input:
        clean_input = barcode_input.strip()
        mask_barcode = df_products["國際條碼"].astype(str).str.contains(clean_input, case=False, na=False)
        mask_name = df_products["產品名稱"].astype(str).str.contains(clean_input, case=False, na=False)
        df_step2 = df_products[mask_barcode | mask_name]
        
        if df_step2.empty:
            st.error(f"❌ 找不到包含「{clean_input}」的條碼或商品名稱！")
    else:
        df_step2 = df_step1.copy()
        if selected_cat_filter != "全部":
            df_step2 = df_step2[df_step2["品類"] == selected_cat_filter]

    display_to_name = {}
    for _, row in df_step2.iterrows():
        p_name = row["產品名稱"]
        barcode = str(row["國際條碼"]).strip()
        if barcode:
            display_str = f"{p_name} ［條碼: {barcode}］"
        else:
            display_str = p_name
        display_to_name[display_str] = p_name

    display_options = list(display_to_name.keys())

    if barcode_input and len(display_options) == 1:
        default_selections = display_options
    else:
        default_selections = []

    selected_displays = st.multiselect(
        "3️⃣ 選擇商品 (可手動點選，最多20樣)", 
        options=display_options, 
        default=default_selections, 
        max_selections=20,
        placeholder="請點選加入多項商品...",
        key=f"prod_multi{input_suffix}"
    )

    selected_products_batch = [display_to_name[disp] for disp in selected_displays]

    if selected_products_batch:
        st.info(f"👇 您已選擇 {len(selected_products_batch)} 項商品，請輸入數量後一次送出")
        
        with st.form(key=f"batch_form{input_suffix}"):
            prod_dict = df_products.drop_duplicates(subset=["產品名稱"]).set_index("產品名稱").to_dict('index')
            
            for p_name in selected_products_batch:
                p_info = prod_dict.get(p_name, {})
                p_cat = p_info.get('品類', '一般')
                p_barcode = p_info.get('國際條碼', '')
                barcode_text = f" | 條碼: {p_barcode}" if p_barcode else ""
                
                st.markdown(f"**{p_name}** <span style='color:gray; font-size:0.8em'>({p_cat}{barcode_text})</span>", unsafe_allow_html=True)
                
                # ★★★ 視覺微調：改用 4 個 Column 來排版標籤與輸入框 ★★★
                # [ 標籤1(窄) | 輸入1(寬) | 標籤2(窄) | 輸入2(寬) ]
                c_label_q, c_input_q, c_label_g, c_input_g = st.columns([1.2, 2.5, 1.2, 2.5], gap="small")
                
                with c_label_q:
                    st.markdown("<div class='input-label'>訂購數</div>", unsafe_allow_html=True)
                with c_input_q:
                    st.number_input("訂購", min_value=0, step=1, value=None, placeholder="0", key=f"q_{p_name}", label_visibility="collapsed")
                
                with c_label_g:
                    st.markdown("<div class='input-label'>搭贈數</div>", unsafe_allow_html=True)
                with c_input_g:
                    st.number_input("搭贈", min_value=0, step=1, value=None, placeholder="0", key=f"g_{p_name}", label_visibility="collapsed")
                    
                st.divider()

            submitted = st.form_submit_button("⬇️ 全部加入購物車", type="primary", use_container_width=True)
            
            if submitted:
                if not selected_sales_name or not selected_cust_name:
                    st.error("⚠️ 請先在最上方選擇「業務」與「客戶」！")
                else:
                    items_added_count = 0
                    keys_to_clear = [] 
                    
                    for p_name in selected_products_batch:
                        q_raw = st.session_state.get(f"q_{p_name}")
                        g_raw = st.session_state.get(f"g_{p_name}")
                        
                        q_val = int(q_raw) if q_raw is not None else 0
                        g_val = int(g_raw) if g_raw is not None else 0
                        
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
                        
                        keys_to_clear.extend([f"q_{p_name}", f"g_{p_name}"])
                    
                    if items_added_count > 0:
                        for k in keys_to_clear:
                            if k in st.session_state:
                                del st.session_state[k]
                                
                        st.session_state.input_reset_trigger += 1 
                        st.toast(f"✅ 成功加入 {items_added_count} 項商品！")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("⚠️ 所有商品的數量皆未輸入，未加入任何項目")

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
                    
                    s_id_3digits = get_sales_id_3digits(selected_sales_name, df_salespeople)
                    s_id_2digits_for_billno = s_id_3digits[-2:]
                    date_str_8 = order_date.strftime('%Y%m%d')
                    prefix = f"{s_id_2digits_for_billno}{date_str_8}"
                    
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
                    final_person_id = f"'{s_id_3digits}"
                    
                    new_rows = []
                    for item in st.session_state.cart_list:
                        if item["訂購數量"] > 0:
                            new_rows.append({
                                "BillDate": date_str_8, "BillNo": final_bill_no,
                                "PersonID": final_person_id, "PersonName": selected_sales_name,
                                "CustID": c_id, "ProdID": item["產品編號"], "ProdName": item["產品名稱"],
                                "Quantity": item["訂購數量"]
                            })
                        if item["搭贈數量"] > 0:
                            new_rows.append({
                                "BillDate": date_str_8, "BillNo": final_bill_no,
                                "PersonID": final_person_id, "PersonName": selected_sales_name,
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

# ==========================================
# 📥 2. 中台：訂單匯出
# ==========================================
elif page == "📥 訂單匯出":
    st.title("📥 訂單匯出與清理")
    st.info("💡 內勤人員專屬：您可在此下載完整訂單 Excel，並在處理完畢後一鍵清空雲端紀錄。")

    st.subheader(f"📋 目前雲端共有 {len(df_order_history)} 筆訂單紀錄")
    st.dataframe(df_order_history, use_container_width=True, height=400)

    st.divider()
    st.subheader("⚙️ 匯出與清理操作")
    col_export, col_clear = st.columns(2, gap="large")

    with col_export:
        st.markdown("##### 1️⃣ 下載 Excel 備份")
        st.caption("將目前的訂單紀錄完整下載為 Excel 檔案。")
        
        if not df_order_history.empty:
            excel_buffer = io.BytesIO()
            try:
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df_order_history.to_excel(writer, index=False, sheet_name='訂單紀錄')
            except:
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_order_history.to_excel(writer, index=False, sheet_name='訂單紀錄')
            
            download_name = f"訂單紀錄_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            st.download_button(
                label="📥 點擊下載 Excel 檔",
                data=excel_buffer.getvalue(),
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