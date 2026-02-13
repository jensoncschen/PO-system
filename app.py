import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購系統 (行動優化版)", layout="wide", page_icon="🛍️")

# --- CSS 優化 (加大輸入框與按鈕，適合手指點擊) ---
st.markdown("""
    <style>
    /* 加大數字輸入框的高度與字體 */
    div[data-testid="stNumberInput"] input {
        height: 50px;
        font-size: 20px;
        text-align: center;
    }
    /* 加大 +/- 按鈕的觸控區域 */
    button[kind="secondary"] {
        height: 50px !important;
        width: 50px !important;
    }
    /* 卡片樣式 */
    .product-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 10px;
        border: 1px solid #eee;
    }
    /* 懸浮按鈕樣式 (FAB) */
    div.stButton > button[kind="primary"] {
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: auto;
        height: auto;
        padding: 15px 30px;
        border-radius: 50px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        z-index: 9999;
        font-size: 18px !important;
        font-weight: bold !important;
        border: 2px solid white !important;
    }
    /* 底部墊高 */
    .spacer { height: 100px; }
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
        
        if "客戶名稱" not in df_cust.columns: df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns: df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns: df_prod["品牌"] = "未分類"
        if "BillNo" not in df_order.columns: df_order["BillNo"] = ""
        
        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()
        df_order["BillNo"] = df_order["BillNo"].astype(str).str.replace("'", "", regex=False)
        
        return df_cust, df_prod, df_sales, df_order
    except Exception as e:
        return None, None, None, None

# --- 載入資料 ---
df_customers, df_products, df_salespeople, df_order_history = fetch_all_data()

if df_customers is None:
    st.error("系統維護中...")
    st.stop()

# --- 初始化 Session ---
if 'cart_list' not in st.session_state: st.session_state.cart_list = []
if 'current_step' not in st.session_state: st.session_state.current_step = 1 
if 'confirmed_sales' not in st.session_state: st.session_state.confirmed_sales = ""
if 'confirmed_cust' not in st.session_state: st.session_state.confirmed_cust = ""
if 'confirmed_date' not in st.session_state: st.session_state.confirmed_date = datetime.now()
# 用來暫存卡片輸入的字典
if 'temp_inputs' not in st.session_state: st.session_state.temp_inputs = {}

# --- 側邊欄 ---
st.sidebar.title("☁️ 導航")
if st.sidebar.button("🔄 更新資料"):
    st.cache_data.clear()
    st.rerun()

# 顯示購物車狀態
cart_count = len(st.session_state.cart_list)
if cart_count > 0:
    st.sidebar.success(f"🛒 購物車：{cart_count} 筆")
    if st.session_state.current_step == 1:
        if st.sidebar.button("前往結帳 ➡️"):
            st.session_state.current_step = 2
            st.rerun()

# ==========================================
# 🛒 前台：下單作業
# ==========================================
if st.session_state.current_step == 1:
    st.title("🛒 步驟 1：選擇商品")
    
    # 1. 基本資料選單
    with st.container():
        c1, c2, c3 = st.columns(3)
        with c1:
            sales_list = df_salespeople["業務名稱"].unique().tolist()
            selected_sales_name = st.selectbox("👤 業務", sales_list, index=None, placeholder="選擇業務...", key="sb_sales")
        with c2:
            current_cust = []
            if selected_sales_name:
                current_cust = df_customers[df_customers["業務名稱"]==selected_sales_name]["客戶名稱"].unique().tolist()
            selected_cust_name = st.selectbox("🏢 客戶", current_cust, index=None, placeholder="選擇客戶...", key="sb_cust")
        with c3:
            order_date = st.date_input("📅 日期", datetime.now())

    st.divider()
    
    # 2. 搜尋與篩選
    col_brand, col_search = st.columns([1, 2])
    with col_brand:
        all_brands = df_products["品牌"].unique().tolist()
        selected_brands = st.multiselect("🏷️ 品牌篩選", all_brands)
    with col_search:
        search_kw = st.text_input("🔍 關鍵字搜尋 (輸入後按 Enter)", placeholder="例如：iphone...")

    # 3. 準備資料
    display_df = df_products.copy()
    if selected_brands:
        display_df = display_df[display_df["品牌"].isin(selected_brands)]
    if search_kw:
        display_df = display_df[display_df["產品名稱"].astype(str).str.contains(search_kw, case=False)]

    st.subheader("📦 商品清單")
    st.caption("💡 平板操作提示：直接點擊 +/- 按鈕調整數量")

    # ★★★ 重點修改：卡片式介面 (Card View) ★★★
    # 不再使用 data_editor，改用迴圈產生個別輸入框
    
    # 為了避免一次渲染太多卡片導致當機，這裡做個簡單的分頁或限制
    # 如果沒有搜尋條件，最多顯示前 20 筆 (避免手機跑不動)
    MAX_ITEMS = 50 
    if len(display_df) > MAX_ITEMS and not search_kw and not selected_brands:
        st.warning(f"商品過多，僅顯示前 {MAX_ITEMS} 筆。請使用篩選或搜尋功能縮小範圍。")
        display_df = display_df.head(MAX_ITEMS)
    
    # 檢查是否有商品
    if display_df.empty:
        st.info("沒有找到符合的商品")
    
    # 產生卡片迴圈
    for index, row in display_df.iterrows():
        p_name = row["產品名稱"]
        brand = row["品牌"]
        p_id = row["產品編號"]
        
        # 使用 container 框出一個卡片區域
        with st.container(border=True):
            # 版面配置：左邊是產品名(佔3)，右邊是數量輸入(佔2)
            c_info, c_input = st.columns([3, 2], gap="small")
            
            with c_info:
                st.markdown(f"**{p_name}**")
                st.caption(f"🏷️ {brand} | 🆔 {p_id}")
            
            with c_input:
                # 使用 session_state key 來綁定輸入值
                # key 的命名規則： qty_{產品名稱} 和 gift_{產品名稱}
                col_q, col_g = st.columns(2)
                with col_q:
                    st.number_input(
                        "訂購", 
                        min_value=0, step=1, 
                        key=f"qty_{p_name}", # 綁定唯一 KEY
                        label_visibility="collapsed" # 手機版隱藏標籤省空間，改用 placeholder 概念
                    )
                    st.caption("訂購量")
                with col_g:
                    st.number_input(
                        "搭贈", 
                        min_value=0, step=1, 
                        key=f"gift_{p_name}", 
                        label_visibility="collapsed"
                    )
                    st.caption("搭贈量")

    # 底部墊高
    st.markdown("<div class='spacer'></div>", unsafe_allow_html=True)

    # 4. 懸浮按鈕 (FAB) - 收集輸入資料
    # 我們需要遍歷 session_state，找出所有 "qty_" 開頭且大於 0 的值
    total_items = 0
    # 預先計算數量 (為了顯示在按鈕上)
    # 這裡稍微複雜一點，因為 Streamlit 的 Session State 在按鈕按下前是即時的
    # 我們做一個簡單的掃描
    
    # (FAB 邏輯維持不變，但收集資料的方式改了)
    if st.button("🛒 加入並結帳 ➡️", type="primary"):
        items_found = False
        if not selected_cust_name or not selected_sales_name:
            st.error("請先選擇業務與客戶！")
        else:
            # 遍歷所有 session state，找出輸入的數量
            for key in st.session_state:
                if key.startswith("qty_"):
                    qty_val = st.session_state[key]
                    # 取得對應的產品名稱
                    target_p_name = key.replace("qty_", "")
                    # 取得對應的搭贈數量 (如果有)
                    gift_key = f"gift_{target_p_name}"
                    gift_val = st.session_state.get(gift_key, 0)
                    
                    if qty_val > 0 or gift_val > 0:
                        items_found = True
                        # 反查產品資料
                        original_product = df_products[df_products["產品名稱"] == target_p_name].iloc[0]
                        
                        st.session_state.cart_list.append({
                            "業務名稱": selected_sales_name,
                            "客戶名稱": selected_cust_name,
                            "產品編號": original_product.get("產品編號", "N/A"),
                            "產品名稱": target_p_name,
                            "品牌": original_product.get("品牌", ""),
                            "訂購數量": qty_val,
                            "搭贈數量": gift_val
                        })
                        
                        # 清零該產品的輸入框 (透過將 session state 設回 0)
                        st.session_state[key] = 0
                        if gift_key in st.session_state:
                            st.session_state[gift_key] = 0

            if items_found:
                st.session_state.confirmed_sales = selected_sales_name
                st.session_state.confirmed_cust = selected_cust_name
                st.session_state.confirmed_date = order_date
                st.session_state.current_step = 2
                st.rerun()
            else:
                st.toast("⚠️ 請至少輸入一項商品的數量")

# ==========================================
# STEP 2: 購物車結帳頁面 (維持不變)
# ==========================================
elif st.session_state.current_step == 2:
    st.title("📋 步驟 2：確認訂單")
    
    c_sales = st.session_state.confirmed_sales
    c_cust = st.session_state.confirmed_cust
    c_date = st.session_state.confirmed_date.strftime('%Y-%m-%d')
    
    st.info(f"👤 {c_sales} | 🏢 {c_cust} | 📅 {c_date}")

    if len(st.session_state.cart_list) > 0:
        cart_df = pd.DataFrame(st.session_state.cart_list)
        
        st.markdown("##### 🛒 點擊數字可修改")
        edited_cart_df = st.data_editor(
            cart_df,
            column_config={
                "產品名稱": st.column_config.TextColumn(disabled=True),
                "訂購數量": st.column_config.NumberColumn(min_value=0, step=1),
                "搭贈數量": st.column_config.NumberColumn(min_value=0, step=1),
            },
            column_order=["產品名稱", "訂購數量", "搭贈數量"],
            use_container_width=True, num_rows="dynamic", key="cart_editor_final", height=400
        )
        
        if not edited_cart_df.equals(cart_df):
            st.session_state.cart_list = edited_cart_df.to_dict('records')
            st.rerun()

        st.divider()
        col_back, col_submit = st.columns([1, 3])
        
        with col_back:
            if st.button("⬅️ 加購商品", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
        
        with col_submit:
            if st.button("✅ 確認送出", type="primary", use_container_width=True):
                with st.spinner("傳送中..."):
                    current_history = conn.read(worksheet="訂單紀錄", ttl=0) 
                    if "BillNo" not in current_history.columns: current_history["BillNo"] = ""
                    current_history["BillNo"] = current_history["BillNo"].astype(str).str.replace("'", "", regex=False)

                    sales_row = df_salespeople[df_salespeople["業務名稱"] == c_sales]
                    if not sales_row.empty:
                        raw_val = sales_row.iloc[0]["業務編號"]
                        try:
                            val_int = int(float(raw_val))
                            s_id_2digits = f"{val_int:02d}"
                        except:
                            s_str = str(raw_val).strip()
                            s_id_2digits = s_str.zfill(2)[-2:]
                    else: s_id_2digits = "00"

                    date_str_8 = st.session_state.confirmed_date.strftime('%Y%m%d')
                    prefix = f"{s_id_2digits}{date_str_8}"
                    
                    existing_ids = current_history["BillNo"].astype(str).tolist()
                    matching_ids = [oid for oid in existing_ids if oid.startswith(prefix) and len(oid) == 13]
                    
                    if matching_ids:
                        seqs = [int(oid[-3:]) for oid in matching_ids if oid[-3:].isdigit()]
                        next_seq = max(seqs) + 1 if seqs else 1
                    else: next_seq = 1
                    
                    final_bill_no = f"'{prefix}{str(next_seq).zfill(3)}"
                    cust_row = df_customers[df_customers["客戶名稱"] == c_cust]
                    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"

                    new_rows = []
                    for item in st.session_state.cart_list:
                        if item["訂購數量"] > 0:
                            new_rows.append({
                                "BillDate": date_str_8, "BillNo": final_bill_no,
                                "PersonID": s_id_2digits, "PersonName": c_sales,
                                "CustID": c_id, "ProdID": item["產品編號"], "ProdName": item["產品名稱"],
                                "Quantity": item["訂購數量"]
                            })
                        if item["搭贈數量"] > 0:
                            new_rows.append({
                                "BillDate": date_str_8, "BillNo": final_bill_no,
                                "PersonID": s_id_2digits, "PersonName": c_sales,
                                "CustID": c_id, "ProdID": item["產品編號"], "ProdName": f"{item['產品名稱']} (搭贈)", 
                                "Quantity": item["搭贈數量"]
                            })

                    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="訂單紀錄", data=updated_history)
                    
                    st.cache_data.clear()
                    st.session_state.cart_list = []
                    st.session_state.current_step = 1
                    
                    # 清除輸入
                    if "sb_sales" in st.session_state: del st.session_state["sb_sales"]
                    if "sb_cust" in st.session_state: del st.session_state["sb_cust"]
                    
                    st.balloons()
                    st.success("訂單建立成功！")
                    time.sleep(2)
                    st.rerun()

# --- 後台管理 (保持精簡) ---
if st.sidebar.radio("隱藏選單", ["後台"], index=0, label_visibility="collapsed") == "後台":
    pass