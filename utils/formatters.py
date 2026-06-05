"""格式化與文字處理工具。

此檔案放置不依賴畫面流程的共用小工具。
"""

import html
from typing import Any

import pandas as pd


def clean_barcode(value: Any) -> str:
    """清理商品條碼欄位，避免 Google Sheets 數字被讀成 12345.0。"""
    barcode = str(value).strip()
    if barcode.endswith(".0"):
        barcode = barcode[:-2]
    if barcode.lower() in ["nan", "none", ""]:
        return ""
    return barcode


def safe_html(value: Any) -> str:
    """轉義文字，避免商品名稱或網址中的特殊字元影響 HTML 顯示。"""
    return html.escape(str(value))

def safe_int(value: Any, default: int = 0) -> int:
    """將訂購數 / 搭贈數安全轉成整數，避免空值、NaN 或字串造成送出訂單失敗。"""
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        text_value = str(value).strip()
        if text_value == "":
            return default
        return int(float(text_value))
    except (TypeError, ValueError):
        return default

