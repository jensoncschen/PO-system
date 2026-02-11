import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購單系統 Pro", layout="wide", page_icon="📦")

# --- 1. 初始化資料 (Session State) ---
# 預設資料現在包含「編號」欄位
if 'df_customers' not in st.session_state:
    st.session_state.df_customers = pd.DataFrame({
        "客戶編號": ["C001", "C002", "C003", "C004", "C005"],
        "客戶名稱": ["台積電", "聯發科", "鴻海", "中華電信", "廣達"]
    })

if 'df_products' not in st.session_state:
    st.session_state.df_products = pd.DataFrame({
        "產品編號": ["P001", "P002", "P003", "P004", "P005"],
        "產品名稱": ["高階伺服器", "工業電腦", "AI 晶片模組", "散熱風扇", "電源供應器"],
        "數量": [50, 100, 200, 500, 300], # 這裡的數量視為庫存
        "單價": [200000, 35000, 50000, 1200, 4500]
    })

if 'order_history' not in st.session_state:
    st.session_state.order_history = pd.DataFrame(columns=["訂單編號", "日期", "客戶編號", "客戶名稱", "產品編號", "產品名稱", "單價", "訂購數量", "小計"])

# --- 側邊欄導航 ---
st.sidebar.title("📦 訂單系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：業務下單", "🔧 後台：管理中心"])
st.sidebar.markdown("---")
st.sidebar.caption("v2.1 | 自訂資料格式版")

# ==========================================
# 🛒 前台：業務下單頁面
# ==========================================
if page == "🛒 前台：業務下單":
    st.title("🛒 業務下單專區")
    
    # 1. 選擇客戶 (顯示編號與名稱)
    col_cust, col_date = st.columns([1, 1])
    with col_cust:
        # 製作下拉選單的顯示格式： C001 - 台積電
        cust_options = st.session_state.df_customers.apply(
            lambda x: f"{x['客戶編號']} - {x['客戶名稱']}", axis=1
        )
        selected_cust_str = st.selectbox("👤 選擇客戶", cust_options)
        # 解析回原本的客戶資料
        selected_cust_id = selected_cust_str.split(" - ")[0]
        selected_cust_name = selected_cust_str.split(" - ")[1]

    with col_date:
        order_date = st.date_input("📅 訂單日期", datetime.now())

    st.divider()

    # 2. 產品清單式選單
    st.subheader("📦 產品選擇")
    
    # 準備顯示資料，新增「訂購數量」欄位供編輯
    display_df = st.session_state.df_products.copy()
    display_df["訂購數量"] = 0 # 預設訂購 0
    
    # 調整欄位順序讓「訂購數量」好按一點
    display_df = display_df[["產品編號", "產品名稱", "數量", "單價", "訂購數量"]]
    
    # 使用 data_editor
    edited_df = st.data_editor(
        display_df,
        column_config={
            "產品編號": st.column_config.TextColumn(disabled=True),
            "產品名稱": st.column_config.TextColumn(disabled=True),
            "數量": st.column_config.NumberColumn("目前庫存", disabled=True), # 顯示為目前庫存
            "單價": st.column_config.NumberColumn(format="$%d", disabled=True),
            "訂購數量": st.column_config.NumberColumn(min_value=0, step=1, help="請輸入欲購買的數量")
        },
        use_container_width=True,
        hide_index=True,
        key="order_editor"
    )

    # 3. 購物車計算與送出
    cart_items = edited_df[edited_df["訂購數量"] > 0].copy()
    
    if not cart_items.empty:
        cart_items["小計"] = cart_items["單價"] * cart_items["訂購數量"]
        total_amount = cart_items["小計"].sum()

        st.info(f"已選擇 {len(cart_items)} 項產品")
        st.dataframe(cart_items[["產品名稱", "單價", "訂購數量", "小計"]], use_container_width=True)
        
        col_total, col_btn = st.columns([3, 1])
        with col_total:
            st.markdown(f"### 總金額: :red[${total_amount:,.0f}]")
        
        with col_btn:
            if st.button("✅ 確認送出訂單", type="primary", use_container_width=True):
                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                new_orders = []
                for _, row in cart_items.iterrows():
                    new_orders.append({
                        "訂單編號": order_id,
                        "日期": order_date.strftime("%Y-%m-%d"),
                        "客戶編號": selected_cust_id,
                        "客戶名稱": selected_cust_name,
                        "產品編號": row["產品編號"],
                        "產品名稱": row["產品名稱"],
                        "單價": row["單價"],
                        "訂購數量": row["訂購數量"],
                        "小計": row["小計"]
                    })
                
                # 寫入歷史紀錄
                st.session_state.order_history = pd.concat(
                    [st.session_state.order_history, pd.DataFrame(new_orders)], 
                    ignore_index=True
                )
                
                # (選用功能) 扣庫存邏輯可寫在這裡
                
                st.success(f"訂單 {order_id} 建立成功！")
                st.balloons()

# ==========================================
# 🔧 後台：管理中心頁面
# ==========================================
elif page == "🔧 後台：管理中心":
    st.title("🔧 後台管理中心")
    
    tab1, tab2 = st.tabs(["📊 訂單報表", "📁 資料庫維護 (Excel匯入)"])

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
        st.markdown("請依照指定格式準備 Excel 檔案 (.xlsx) 並上傳。")

        col1, col2 = st.columns(2)
        
        # === 1. 客戶資料更新 ===
        with col1:
            st.subheader("1. 客戶資料")
            st.info("格式要求：\n1. 欄位一：客戶編號\n2. 欄位二：客戶名稱")
            
            # 顯示目前資料
            st.caption("目前資料預覽：")
            st.dataframe(st.session_state.df_customers, height=200, use_container_width=True)
            
            cust_file = st.file_uploader("上傳客戶 Excel", type=['xlsx'], key="up_cust")
            if cust_file:
                try:
                    df_new = pd.read_excel(cust_file)
                    # 強制取前兩欄，並重新命名，確保格式統一
                    df_new = df_new.iloc[:, :2] 
                    df_new.columns = ["客戶編號", "客戶名稱"]
                    
                    st.write("預覽上傳內容：")
                    st.dataframe(df_new.head(), height=100)
                    
                    if st.button("確認更新客戶資料"):
                        st.session_state.df_customers = df_new
                        st.success("✅ 更新成功！")
                        st.rerun()
                except Exception as e:
                    st.error(f"檔案格式錯誤: {e}")

        # === 2. 產品資料更新 ===
        with col2:
            st.subheader("2. 產品資料")
            st.info("格式要求：\n1. 欄位一：產品編號\n2. 欄位二：產品名稱\n3. 欄位三：數量 (庫存)\n4. 欄位四：單價")
            
            # 顯示目前資料
            st.caption("目前資料預覽：")
            st.dataframe(st.session_state.df_products, height=200, use_container_width=True)
            
            prod_file = st.file_uploader("上傳產品 Excel", type=['xlsx'], key="up_prod")
            if prod_file:
                try:
                    df_new = pd.read_excel(prod_file)
                    # 強制取前四欄，並重新命名
                    df_new = df_new.iloc[:, :4]
                    df_new.columns = ["