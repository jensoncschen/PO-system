import streamlit as st

from ui.components import render_page_header, render_section_header
from utils.formatters import safe_html


def render_admin_page() -> None:
    render_page_header(
        "後台管理",
        "管理基礎資料來源。產品、客戶與業務資料仍以 Google Sheets 為主要編輯入口。",
        ["客戶資料", "產品資料", "業務資料"],
    )

    render_section_header(
        "1",
        "基礎資料編輯",
        "目前後台資料仍直接在 Google 試算表維護，修改後可用左側重新整理雲端資料。",
        "資料來源",
    )

    with st.container(border=True):
        try:
            sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
            st.markdown(f"""
                <a class='admin-link-card' href='{safe_html(sheet_url)}' target='_blank'>
                    <div class='admin-link-title'>開啟 Google 試算表</div>
                    <div class='admin-link-desc'>前往試算表編輯客戶資料、產品資料與業務資料。</div>
                    <div class='admin-link-url'>在新分頁開啟 →</div>
                </a>
            """, unsafe_allow_html=True)
        except Exception:
            st.warning("目前無法讀取 Google 試算表連結，請確認 secrets 設定。")

    render_section_header(
        "2",
        "使用提醒",
        "這裡先保留為輕量後台，避免過早把資料管理做得太複雜。",
        "說明",
    )

    with st.container(border=True):
        st.markdown("""
            <div class='operation-title'>資料更新流程</div>
            <div class='operation-desc'>
                1. 到 Google 試算表修改基礎資料。<br>
                2. 回到系統左側點選「重新整理雲端資料」。<br>
                3. 回前台下單頁確認新資料是否出現。<br><br>
                訂單匯出與清除請前往「訂單匯出」分頁處理。
            </div>
        """, unsafe_allow_html=True)
