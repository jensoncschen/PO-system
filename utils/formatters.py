"""格式化與文字處理工具。

此檔案放置不依賴畫面流程的共用小工具。
"""

import html
from typing import Any


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

