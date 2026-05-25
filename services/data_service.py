import traceback

import pandas as pd
import streamlit as st

from utils.formatters import clean_barcode


@st.cache_data(ttl=300)
def fetch_all_data(_conn):
    """從 Google Sheets 讀取客戶、產品、業務資料，並做基本清理。

    參數名稱使用 `_conn`，是為了讓 Streamlit cache 不嘗試 hash 連線物件。
    """
    try:
        df_cust = _conn.read(worksheet="客戶資料")
        df_prod = _conn.read(worksheet="產品資料")
        df_sales = _conn.read(worksheet="業務資料")

        for df in [df_cust, df_sales, df_prod]:
            if df is None:
                return None, None, None

        df_cust.columns = df_cust.columns.str.strip()
        df_prod.columns = df_prod.columns.str.strip()
        df_sales.columns = df_sales.columns.str.strip()

        if "客戶名稱" not in df_cust.columns:
            df_cust["客戶名稱"] = ""
        if "業務名稱" not in df_sales.columns:
            df_sales["業務名稱"] = ""
        if "品牌" not in df_prod.columns:
            df_prod["品牌"] = "未分類"
        if "品類" not in df_prod.columns:
            df_prod["品類"] = "一般"
        if "國際條碼" not in df_prod.columns:
            df_prod["國際條碼"] = ""

        df_cust["業務名稱"] = df_cust["業務名稱"].astype(str).str.strip()
        df_sales["業務名稱"] = df_sales["業務名稱"].astype(str).str.strip()

        df_prod["品類"] = df_prod["品類"].fillna("一般")
        df_prod["國際條碼"] = df_prod["國際條碼"].apply(clean_barcode)

        return df_cust, df_prod, df_sales

    except Exception as e:
        st.error(f"資料庫連線異常，錯誤原因：{e}")
        print(traceback.format_exc())
        return None, None, None
