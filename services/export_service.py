"""Excel 匯出服務。

集中管理訂單紀錄匯出 Excel 的相關邏輯。
"""

import io

import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def generate_excel_file(df: pd.DataFrame) -> bytes:
    """將訂單紀錄 DataFrame 轉成 Excel 檔案位元組。

    優先使用 xlsxwriter；若環境未安裝，則改用 openpyxl。
    """
    excel_buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="訂單紀錄")
    except Exception:
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="訂單紀錄")
    return excel_buffer.getvalue()

