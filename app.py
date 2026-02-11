import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購單系統 Pro", layout="wide", page_icon="📦")

# --- 1. 初始化資料 (Session State) ---

# 客戶資料 (維持原樣)
if 'df_customers' not in st.session_state:
    st.session_state.df_customers = pd.DataFrame({
        "客戶編號": ["C001", "C002", "C003", "C004", "C005"],
        "客戶名稱": ["台積電", "聯發科", "鴻海", "中華電信", "廣達"]
    })

# 產品資料 (更新：加入品牌，移除庫存)
if 'df_products' not in st.session_state:
    st.session_state.df_products = pd.DataFrame({
        "產品編號": ["P001", "P002", "P003", "P004", "P005", "P006"],
        "產品名稱": ["高階伺服器", "商用筆電", "電競滑鼠", "機械鍵盤", "AI 運算卡", "27吋螢幕"],
        "品牌": ["Dell", "HP", "Logitech", "Logitech", "NVIDIA", "Dell"],
        "單價": [200000, 35000, 1200, 3500, 500000, 6000]
    })

# 訂單暫存區 (購物車)
if 'cart_list' not in st.session_state:
    st.session_state.cart_list = []

# 歷史訂單紀錄
if 'order_history' not in st.session_state:
    st.session_state.order_history = pd.DataFrame(columns=["訂單編號", "日期", "客戶編號", "客戶名稱", "產品編號", "產品名稱", "品牌", "單價", "訂購數量", "小計"])

# --- 側邊欄導航 ---
st.sidebar.title("📦 訂單系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：業務下單", "🔧 後台：管理中心"])
st.sidebar.markdown("---")
st.sidebar.caption("v3.0 | 品牌篩選版")

# ==========================================
# 🛒 前台：業務下單頁面
# ==========================================
if page == "🛒 前台：業務下單":
    st.title("🛒 業務下單專區")
    
    # --- 區域 1: 訂單基本資訊 ---
    with st.container():
        col_cust, col_date = st.columns([1, 1])
        with col_cust:
            cust_options = st.session_state.df_customers.apply(
                lambda x: f"{x['客戶編號']} - {x['客戶名稱']}", axis=1
            )
            selected_cust_str = st.selectbox("👤 選擇客戶", cust_options)
            selected_cust_id = selected_cust_str.split(" - ")[0]
            selected_cust_name = selected_cust_str.split(" - ")[1]

        with col_date:
            order_date = st.date_input("📅 訂單日期", datetime.now())
    
    st.divider()

    # --- 區域 2: 產品篩選與選擇 ---
    st.subheader("📦 產品選擇")

    # 搜尋與篩選工具列
    col_search, col_filter = st.columns([2, 1])
    with col_search:
        search_term = st.text_input("🔍 搜尋產品 (名稱或編號)", placeholder="輸入關鍵字...")
    with col_filter:
        # 自動抓取所有品牌製作選單
        all_brands = st.session_state.df_products["品牌"].unique()
        selected_brands = st.multiselect("🏷️ 品牌篩選", all_brands)

    # 資料篩選邏輯
    display_df = st.session_state.df_products.copy()
    
    # 1. 關鍵字搜尋
    if search_term:
        display_df = display_df[
            display_df["產品名稱"].str.contains(search_term, case=False) | 
            display_df["產品編號"].str.contains(search_term, case=False)
        ]
    
    # 2. 品牌篩選
    if selected_brands:
        display_df = display_df[display_df["品牌"].isin(selected_brands)]

    # 準備顯示用的表格 (加入「訂購數量」欄位)
    display_df["訂購數量"] = 0 
    
    # 調整欄位顯示順序
    display_df = display_df[["產品編號", "品牌", "產品名稱", "單價", "訂購數量"]]

    st.caption(f"顯示 {len(display_df)} 筆產品資料")

    # 互動式表格
    edited_df = st.data_editor(
        display_df,
        column_config={
            "產品編號": st.column_config.TextColumn(disabled=True),
            "品牌": st.column_config.TextColumn(disabled=True),
            "產品名稱": st.column_config.TextColumn(disabled=True),
            "單價": st.column_config.NumberColumn(format="$%d", disabled=True),
            "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="輸入數量")
        },
        use_container_width=True,
        hide_index=True,
        key="product_selector" # 重要：給予唯一的 key
    )

    # --- 區域 3: 加入購物車邏輯 ---
    # 找出有輸入數量的項目
    items_to_add = edited_df[edited_df["訂購數量"] > 0].copy()
    
    if not items_to_add.empty:
        if st.button(f"⬇️ 將選取的 {len(items_to_add)} 項商品加入清單", type="primary"):
            for _, row in items_to_add.iterrows():
                # 計算單品小計
                subtotal = row["單價"] * row["訂購數量"]
                # 加入暫存清單
                st.session_state.cart_list.append({
                    "產品編號": row["產品編號"],
                    "產品名稱": row["產品名稱"],
                    "品牌": row["品牌"],
                    "單價": row["單價"],
                    "訂購數量": row["訂購數量"],
                    "小計": subtotal
                })
            st.success("已加入清單！你可以繼續搜尋並加入其他商品。")
            st.rerun() # 重新整理以清空輸入框，方便下一批輸入

    # --- 區域 4: 購物車與結帳 ---
    if len(st.session_state.cart_list) > 0:
        st.divider()
        st.subheader("🛒 待結帳清單")
        
        # 轉成 DataFrame 顯示
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df, use_container_width=True)
        
        total_price = cart_df["小計"].sum()
        col_t, col_b1, col_b2 = st.columns([2, 1, 1])
        
        with col_t:
            st.markdown(f"### 總金額: :red[${total_price:,.0f}]")
        
        with col_b1:
            if st.button("🗑️ 清空重選"):
                st.session_state.cart_list = []
                st.rerun()
                
        with col_b2:
            if st.button("✅ 確認送出訂單", type="primary"):
                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # 準備寫入歷史紀錄
                new_orders = []
                for item in st.session_state.cart_list:
                    new_item = item.copy()
                    new_item["訂單編號"] = order_id
                    new_item["日期"] = order_date.strftime("%Y-%m-%d")
                    new_item["客戶編號"] = selected_cust_id
                    new_item["客戶名稱"] = selected_cust_name
                    new_orders.append(new_item)
                
                # 寫入 Session State
                st.session_state.order_history = pd.concat(
                    [st.session_state.order_history, pd.DataFrame(new_orders)], 
                    ignore_index=True
                )
                
                # 清空購物車
                st.session_state.cart_list = []
                st.balloons()
                st.success(f"訂單 {order_id} 建立成功！")
                st.rerun()

# ==========================================
# 🔧 後台：管理中心頁面
# ==========================================
elif page == "🔧 後台：管理中心":
    st.title("🔧 後台管理中心")
    
    tab1, tab2 = st.tabs(["📊 訂單報表", "📁 資料庫維護"])

    # --- Tab 1: 訂單管理 ---
    with tab1:
        if not st.session_state.order_history.empty:
            st.dataframe(st.session_state.order_history, use_container_width=True)
            
            # Excel 匯出
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                st.session_state.order_history.to_excel(writer, index=False, sheet_name='訂單明細')
                
            st.download_button(
                label="📥 下載 Excel 訂單報表",
                data=buffer.getvalue(),
                file_name=f"Order_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel"
            )
        else:
            st.info("尚無訂單資料")

    # --- Tab 2: 資料庫維護 ---
    with tab2:
        st.markdown("### 批次資料更新")
        col1, col2 = st.columns(2)
        
        # === 客戶資料更新 ===
        with col1:
            st.subheader("1. 客戶資料")
            st.info("格式：A欄(編號)、B欄(名稱)")
            st.dataframe(st.session_state.df_customers, height=200, use_container_width=True)
            
            cust_file = st.file_uploader("上傳客戶 Excel", type=['xlsx'], key="up_cust")
            if cust_file:
                try:
                    df_new = pd.read_excel(cust_file)
                    df_new = df_new.iloc[:, :2] 
                    df_new.columns = ["客戶編號", "客戶名稱"]
                    if st.button("確認更新客戶"):
                        st.session_state.df_customers = df_new
                        st.success("✅ 更新成功！")
                        st.rerun()
                except Exception as e:
                    st.error(f"錯誤: {e}")

        # === 產品資料更新 (依照新需求) ===
        with col2:
            st.subheader("2. 產品資料")
            st.info("格式：A欄(編號)、B欄(名稱)、C欄(品牌)、D欄(單價)")
            st.dataframe(st.session_state.df_products, height=200, use_container_width=True)
            
            prod_file = st.file_uploader("上傳產品 Excel", type=['xlsx'], key="up_prod")
            if prod_file:
                try:
                    df_new = pd.read_excel(prod_file)
                    # 依需求抓取前 4 欄
                    df_new = df_new.iloc[:, :4]
                    # 重新命名欄位
                    df_new.columns = ["產品編號", "產品名稱", "品牌", "單價"]
                    
                    st.write("預覽：")
                    st.dataframe(df_new.head(), height=100)
                    
                    if st.button("確認更新產品"):
                        st.session_state.df_products = df_new
                        st.success("✅ 更新成功！")
                        st.rerun()
                except Exception as e:
                    st.error(f"錯誤: {e}")