import time
from datetime import datetime

import pandas as pd
import streamlit as st

from services.export_service import generate_excel_file
from ui.components import render_page_header, render_section_header


def render_export_page(conn) -> None:
    render_page_header(
        "訂單匯出",
        "內勤人員使用。下載雲端訂單紀錄，確認備份後再清除已處理資料。",
        ["1 查看紀錄", "2 下載 Excel", "3 清除雲端紀錄"],
    )

    # 【優化：只有進到此頁面時才單獨去讀取歷史紀錄，不卡前台速度】
    with st.spinner("正在讀取雲端訂單紀錄..."):
        df_order_history = conn.read(worksheet="訂單紀錄", ttl=0)
        if "BillNo" in df_order_history.columns:
            df_order_history["BillNo"] = df_order_history["BillNo"].astype(str).str.replace("'", "", regex=False)
        if "PersonID" in df_order_history.columns:
            df_order_history["PersonID"] = df_order_history["PersonID"].astype(str).str.replace("'", "", regex=False)

    render_section_header(
        "1",
        "雲端訂單紀錄",
        "這裡顯示目前等待匯出的訂單資料。",
        "查看",
    )

    with st.container(border=True):
        order_count = len(df_order_history)
        st.markdown(f"""
            <div class='cart-summary'>
                <div class='summary-card'>
                    <div class='summary-label'>目前筆數</div>
                    <div class='summary-value'>{order_count}</div>
                </div>
                <div class='summary-card'>
                    <div class='summary-label'>資料來源</div>
                    <div class='summary-value'>Google Sheets</div>
                </div>
                <div class='summary-card'>
                    <div class='summary-label'>用途</div>
                    <div class='summary-value'>ERP 匯入</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if df_order_history.empty:
            st.markdown("<div class='empty-state-card'>目前沒有可匯出的訂單紀錄。</div>", unsafe_allow_html=True)
        else:
            st.dataframe(df_order_history, use_container_width=True, height=420)

    render_section_header(
        "2",
        "匯出與清理",
        "建議先下載 Excel 備份，確認檔案正常後再清除雲端紀錄。",
        "操作",
    )

    col_export, col_clear = st.columns(2, gap="large")

    with col_export:
        with st.container(border=True):
            st.markdown("""
                <div class='operation-title'>下載 Excel 備份</div>
                <div class='operation-desc'>將目前雲端訂單紀錄下載為 Excel 檔，供後續匯入 ERP 或留存備份。</div>
            """, unsafe_allow_html=True)

            if not df_order_history.empty:
                excel_data = generate_excel_file(df_order_history)
                download_name = f"訂單紀錄_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button(
                    label="下載 Excel",
                    data=excel_data,
                    file_name=download_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.button("目前無資料可匯出", disabled=True, use_container_width=True)

    with col_clear:
        with st.container(border=True):
            st.markdown("""
                <div class='operation-title'>清除雲端紀錄</div>
                <div class='operation-desc'>只在已下載並確認備份後使用。清除後，雲端訂單紀錄會變成空白。</div>
                <div class='warning-card'>
                    <div class='warning-title'>操作前提醒</div>
                    <div class='warning-text'>請先確認 Excel 已下載且可開啟，再勾選確認並清除資料。</div>
                </div>
            """, unsafe_allow_html=True)
            confirm_clear = st.checkbox("我已下載並確認 Excel 備份", key="confirm_clear_cb")

            if st.button("清空訂單紀錄", type="primary", use_container_width=True, disabled=not confirm_clear):
                with st.spinner("正在清除雲端訂單紀錄..."):
                    empty_df = pd.DataFrame(columns=df_order_history.columns)
                    conn.update(worksheet="訂單紀錄", data=empty_df)
                    st.cache_data.clear()
                    st.success("雲端訂單紀錄已清空。")
                    time.sleep(2)
                    st.rerun()

    # ==========================================
    # 3. 後台：資料管理
    # ==========================================
