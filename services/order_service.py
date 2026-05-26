import pandas as pd
import streamlit as st


def get_sales_id_3digits(sales_name, df_sales):
    """取得業務編號，並轉成 3 碼格式。"""
    if not sales_name:
        return "000"

    sales_row = df_sales[df_sales["業務名稱"] == sales_name]
    if sales_row.empty:
        return "000"

    raw_val = sales_row.iloc[0]["業務編號"]
    try:
        return f"{int(float(raw_val)):03d}"
    except Exception:
        return str(raw_val).strip().zfill(3)[-3:]


def submit_new_order(cart_list, sales_name, cust_name, order_date, conn, df_sales, df_cust):
    """將購物車內容寫入 Google Sheets 訂單紀錄。"""
    s_id_3digits = get_sales_id_3digits(sales_name, df_sales)
    s_id_2digits_for_billno = s_id_3digits[-2:]
    date_str_8 = order_date.strftime("%Y%m%d")
    prefix = f"{s_id_2digits_for_billno}{date_str_8}"

    cust_row = df_cust[df_cust["客戶名稱"] == cust_name]
    c_id = cust_row.iloc[0]["客戶編號"] if not cust_row.empty else "Unknown"

    # 結帳時即時讀取最新訂單紀錄，避免多人下單時序號重複。
    with st.spinner("正在取得最新訂單序號..."):
        current_history = conn.read(worksheet="訂單紀錄", ttl=0)

    if "BillNo" not in current_history.columns:
        current_history["BillNo"] = ""
    current_history["BillNo"] = current_history["BillNo"].astype(str).str.replace("'", "", regex=False)

    existing_ids = current_history["BillNo"].astype(str).tolist()
    matching_ids = [oid for oid in existing_ids if oid.startswith(prefix) and len(oid) == 13]
    if matching_ids:
        seqs = [int(oid[-3:]) for oid in matching_ids if oid[-3:].isdigit()]
        next_seq = max(seqs) + 1 if seqs else 1
    else:
        next_seq = 1

    raw_bill_no = f"{prefix}{str(next_seq).zfill(3)}"
    final_bill_no = f"'{raw_bill_no}"
    final_person_id = f"'{s_id_3digits}"

    new_rows = []
    for item in cart_list:
        if item["訂購數量"] > 0:
            new_rows.append({
                "BillDate": date_str_8,
                "BillNo": final_bill_no,
                "PersonID": final_person_id,
                "PersonName": sales_name,
                "CustID": c_id,
                "ProdID": item["產品編號"],
                "ProdName": item["產品名稱"],
                "Quantity": item["訂購數量"],
            })
        if item["搭贈數量"] > 0:
            new_rows.append({
                "BillDate": date_str_8,
                "BillNo": final_bill_no,
                "PersonID": final_person_id,
                "PersonName": sales_name,
                "CustID": c_id,
                "ProdID": item["產品編號"],
                "ProdName": f"{item['產品名稱']} (搭贈)",
                "Quantity": item["搭贈數量"],
            })

    updated_history = pd.concat([current_history, pd.DataFrame(new_rows)], ignore_index=True)
    conn.update(worksheet="訂單紀錄", data=updated_history)
    return raw_bill_no
