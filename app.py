import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 頁面設定 ---
st.set_page_config(page_title="雲端訂購單系統 Pro", layout="wide", page_icon="📦")

# --- 1. 初始化資料 (Session State) ---
# 這些資料存在記憶體中，重新整理網頁會重置。若要永久儲存需串接資料庫。

if 'df_customers' not in st.session_state:
    st.session_state.df_customers = pd.DataFrame({"客戶名稱": ["台積電", "聯發科", "鴻海", "中華電信", "廣達"]})

if 'df_products' not in st.session_state:
    st.session_state.df_products = pd.DataFrame({
        "產品名稱": ["高階伺服器", "工業電腦", "AI 晶片模組", "散熱風扇", "電源供應器"],
        "單價": [200000, 35000, 50000, 1200, 4500],
        "庫存": [50, 100, 200, 500, 300]
    })

if 'order_history' not in st.session_state:
    st.session_state.order_history = pd.DataFrame(columns=["訂單編號", "日期", "客戶", "產品", "單價", "數量", "小計"])

# --- 側邊欄導航 ---
st.sidebar.title("📦 訂單系統導航")
page = st.sidebar.radio("前往區塊", ["🛒 前台：業務下單", "🔧 後台：管理中心"])

st.sidebar.markdown("---")
st.sidebar.caption("v2.0 | 清單式下單版")

# ==========================================
# 🛒 前台：業務下單頁面
# ==========================================
if page == "🛒 前台：業務下單":
    st.title("🛒 業務下單專區")
    st.markdown("請選擇客戶，並在下方清單直接輸入購買數量。")

    # 1. 選擇客戶
    col_cust, col_date = st.columns([1, 1])
    with col_cust:
        selected_customer = st.selectbox("👤 選擇客戶", st.session_state.df_customers["客戶名稱"])
    with col_date:
        order_date = st.date_input("📅 訂單日期", datetime.now())

    st.divider()

    # 2. 產品清單式選單 (核心修改)
    st.subheader("📦 產品選擇")
    
    # 準備一個用於顯示的 DataFrame，新增「購買數量」欄位預設為 0
    display_df = st.session_state.df_products.copy()
    if "購買數量" not in display_df.columns:
        display_df.insert(2, "購買數量", 0) # 在第2欄插入

    # 使用 data_editor 讓使用者直接編輯表格
    edited_df = st.data_editor(
        display_df,
        column_config={
            "單價": st.column_config.NumberColumn(format="$%d"),
            "購買數量": st.column_config.NumberColumn(min_value=0, step=1, help="請輸入欲購買的數量"),
            "庫存": st.column_config.NumberColumn(disabled=True) # 禁止修改庫存
        },
        disabled=["產品名稱", "單價"], # 鎖定這兩欄不可編輯
        use_container_width=True,
        hide_index=True,
        key="product_editor"
    )

    # 3. 即時計算購物車內容
    # 篩選出數量 > 0 的項目
    cart_items = edited_df[edited_df["購買數量"] > 0].copy()
    
    if not cart_items.empty:
        cart_items["小計"] = cart_items["單價"] * cart_items["購買數量"]
        total_amount = cart_items["小計"].sum()

        st.info(f"已選擇 {len(cart_items)} 項產品")
        
        # 顯示購物車預覽
        st.dataframe(cart_items[["產品名稱", "單價", "購買數量", "小計"]], use_container_width=True)
        
        col_total, col_btn = st.columns([3, 1])
        with col_total:
            st.markdown(f"### 總金額: :red[${total_amount:,.0f}]")
        
        with col_btn:
            if st.button("✅ 確認送出訂單", type="primary", use_container_width=True):
                # 產生訂單編號
                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # 準備寫入歷史紀錄
                new_orders = []
                for index, row in cart_items.iterrows():
                    new_orders.append({
                        "訂單編號": order_id,
                        "日期": order_date.strftime("%Y-%m-%d"),
                        "客戶": selected_customer,
                        "產品": row["產品名稱"],
                        "單價": row["單價"],
                        "數量": row["購買數量"],
                        "小計": row["小計"]
                    })
                
                # 更新 Session State
                st.session_state.order_history = pd.concat(
                    [st.session_state.order_history, pd.DataFrame(new_orders)], 
                    ignore_index=True
                )
                
                st.success(f"訂單 {order_id} 已建立成功！")
                st.balloons()
                # 這裡不需要 rerun，因為 data_editor 會保留狀態，使用者可以手動歸零或繼續下單
    else:
        st.write("👈 請在上方表格輸入數量以開始下單")

# ==========================================
# 🔧 後台：管理中心頁面
# ==========================================
elif page == "🔧 後台：管理中心":
    st.title("🔧 後台管理中心")
    
    tab1, tab2 = st.tabs(["📊 訂單管理 & 匯出", "📁 資料庫維護"])

    # --- Tab 1: 訂單管理 ---
    with tab1:
        st.subheader("歷史訂單總覽")
        
        if not st.session_state.order_history.empty:
            # 顯示訂單
            df_hist = st.session_state.order_history
            
            # 簡單的篩選器
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                search_cust = st.text_input("🔍 搜尋客戶名稱")
            
            if search_cust:
                df_hist = df_hist[df_hist["客戶"].str.contains(search_cust, case=False)]

            st.dataframe(
                df_hist, 
                use_container_width=True,
                column_config={
                    "單價": st.column_config.NumberColumn(format="$%d"),
                    "小計": st.column_config.NumberColumn(format="$%d"),
                }
            )

            st.markdown(f"**總銷售額:** :green[${df_hist['小計'].sum():,.0f}]")

            # Excel 匯出
            st.write("---")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_hist.to_excel(writer, index=False, sheet_name='訂單明細')
                
            st.download_button(
                label="📥 匯出 Excel 報表",
                data=buffer.getvalue(),
                file_name=f"Order_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )
        else:
            st.info("目前尚無訂單資料。")

    # --- Tab 2: 資料庫維護 ---
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👥 客戶資料設定")
            st.dataframe(st.session_state.df_customers, use_container_width=True)
            
            # 上傳更新
            cust_file = st.file_uploader("更新客戶清單 (Excel/CSV)", type=['xlsx', 'csv'], key="up_cust")
            if cust_file:
                if st.button("確認更新客戶資料"):
                    if cust_file.name.endswith('.csv'):
                        st.session_state.df_customers = pd.read_csv(cust_file)
                    else:
                        st.session_state.df_customers = pd.read_excel(cust_file)
                    st.success("客戶資料已更新！")
                    st.rerun()

        with col2:
            st.subheader("📦 產品資料設定")
            st.dataframe(st.session_state.df_products, use_container_width=True)
            
            # 上傳更新
            prod_file = st.file_uploader("更新產品清單 (Excel/CSV)", type=['xlsx', 'csv'], key="up_prod")
            if prod_file:
                if st.button("確認更新產品資料"):
                    if prod_file.name.endswith('.csv'):
                        st.session_state.df_products = pd.read_csv(prod_file)
                    else:
                        st.session_state.df_products = pd.read_excel(prod_file)
                    st.success("產品資料已更新！")
                    st.rerun()