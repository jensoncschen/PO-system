import hashlib
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from services.order_service import submit_new_order
from ui.components import render_page_header, render_section_header, render_sticky_cart_bar
from utils.formatters import safe_html


BRAND_FILTER_STATE_KEY = "selected_brand_filters"
CATEGORY_FILTER_STATE_KEY = "selected_category_filters"
PRODUCT_SELECTION_STATE_KEY = "selected_product_names"


def _make_filter_key(prefix: str, value: str) -> str:
    """產生穩定 key，避免品牌、品類或商品名稱含特殊字元時影響 session_state。"""
    digest = hashlib.md5(str(value).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _make_token(value: str) -> str:
    """產生用於 HTML 連結的穩定 token。"""
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()[:12]


def _get_unique_options(series: pd.Series) -> list[str]:
    """取得乾淨且穩定排序的篩選選項。"""
    values = series.dropna().astype(str).str.strip()
    values = [value for value in values.unique().tolist() if value and value.lower() not in ["nan", "none"]]
    return sorted(values)


def _ensure_list_state(key: str) -> list[str]:
    """確保 session_state 裡的多選狀態是 list。"""
    if key not in st.session_state or not isinstance(st.session_state[key], list):
        st.session_state[key] = []
    return st.session_state[key]


def _toggle_list_value(state_key: str, value: str, max_items: int | None = None) -> None:
    """切換 list 狀態中的選取值。"""
    selected_values = _ensure_list_state(state_key)
    if value in selected_values:
        selected_values.remove(value)
    else:
        if max_items is None or len(selected_values) < max_items:
            selected_values.append(value)
    st.session_state[state_key] = selected_values


def _consume_query_toggle(param_name: str, options: list[str], state_key: str, max_items: int | None = None) -> None:
    """讀取 HTML 連結帶回的 query param，更新選取狀態後清除 URL。"""
    if param_name not in st.query_params:
        return

    token = st.query_params.get(param_name)
    token_to_value = {_make_token(option): option for option in options}
    if token in token_to_value:
        _toggle_list_value(state_key, token_to_value[token], max_items=max_items)

    st.query_params.clear()
    st.rerun()


def _clear_filter_states() -> None:
    """清除品牌與品類篩選狀態，並兼容清除舊 checkbox key。"""
    st.session_state[BRAND_FILTER_STATE_KEY] = []
    st.session_state[CATEGORY_FILTER_STATE_KEY] = []
    for key in list(st.session_state.keys()):
        if key.startswith("filter_brand_") or key.startswith("filter_category_"):
            st.session_state[key] = False


def _render_link_grid(
    title: str,
    options: list[str],
    state_key: str,
    param_name: str,
    grid_class: str = "filter-option-grid",
    max_items: int | None = None,
    empty_text: str = "目前沒有可選項目",
) -> list[str]:
    """以 HTML + CSS Grid 呈現選項，避免手機版 Streamlit columns 自動堆疊。"""
    selected_values = _ensure_list_state(state_key)
    valid_options = set(options)
    selected_values = [value for value in selected_values if value in valid_options]
    st.session_state[state_key] = selected_values

    st.markdown(f"<div class='filter-group-title'>{safe_html(title)}</div>", unsafe_allow_html=True)

    if not options:
        st.markdown(f"<div class='filter-empty'>{safe_html(empty_text)}</div>", unsafe_allow_html=True)
        return []

    if max_items is not None and len(selected_values) >= max_items:
        st.markdown(
            f"<div class='filter-subnote'>已達最多 {max_items} 項，可取消已選商品後再新增。</div>",
            unsafe_allow_html=True,
        )

    cards: list[str] = []
    for option in options:
        selected_class = " is-selected" if option in selected_values else ""
        token = _make_token(option)
        label = safe_html(option)
        cards.append(
            f"<a class='grid-choice{selected_class}' href='?{param_name}={token}' title='{label}'>"
            f"<span>{label}</span>"
            "</a>"
        )

    st.markdown(
        f"<div class='option-grid {grid_class}'>" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )
    return selected_values


def _render_product_grid(options: list[str], max_items: int = 20) -> list[str]:
    """呈現兩欄起跳的產品卡片清單。"""
    return _render_link_grid(
        title="產品",
        options=options,
        state_key=PRODUCT_SELECTION_STATE_KEY,
        param_name="toggle_product",
        grid_class="product-option-grid",
        max_items=max_items,
        empty_text="目前沒有符合的商品",
    )


def render_order_page(conn, df_customers, df_products, df_salespeople, global_prod_dict) -> None:
    render_page_header(
        "快速下單",
        "手機優先的訂單建立流程。單手操作、先加商品、最後一次確認送出。",
        ["1 訂單資訊", "2 新增商品", "3 購物車確認"],
    )

    form_suffix = f"_{st.session_state.form_reset_trigger}"

    # 區塊 1：訂單資訊
    render_section_header(
        "1",
        "訂單資訊",
        "先確認業務、客戶與日期。這三項會帶入本次訂單。",
        "必填",
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.25, 1.75, 1], gap="medium")
        with c1:
            sales_list = df_salespeople["業務名稱"].unique().tolist()
            selected_sales_name = st.selectbox(
                "業務", sales_list, index=None, placeholder="選擇業務", key=f"sales_sb{form_suffix}"
            )
        with c2:
            current_cust = []
            if selected_sales_name:
                current_cust = df_customers[df_customers["業務名稱"] == selected_sales_name]["客戶名稱"].unique().tolist()
            selected_cust_name = st.selectbox(
                "客戶", current_cust, index=None, placeholder="選擇客戶", key=f"cust_sb{form_suffix}"
            )
        with c3:
            order_date = st.date_input("日期", datetime.now())

    # 統一結帳動作，保留原本訂單邏輯
    def trigger_order_submission():
        if not selected_sales_name or not selected_cust_name:
            st.error("請確認已選擇業務與客戶。")
        elif len(st.session_state.cart_list) == 0:
            st.warning("購物車目前是空的，請先加入商品。")
        else:
            with st.spinner("正在寫入雲端..."):
                generated_bill_no = submit_new_order(
                    st.session_state.cart_list,
                    selected_sales_name,
                    selected_cust_name,
                    order_date,
                    conn,
                    df_salespeople,
                    df_customers,
                )
                st.session_state.cart_list = []
                st.session_state[PRODUCT_SELECTION_STATE_KEY] = []
                st.session_state.input_reset_trigger += 1
                st.session_state.form_reset_trigger += 1
                st.cache_data.clear()
                st.success(f"訂單 {generated_bill_no} 建立成功。")
                time.sleep(1.2)
                st.rerun()

    cart_count = len(st.session_state.cart_list)
    total_quantity = sum(int(item.get("訂購數量", 0) or 0) for item in st.session_state.cart_list)
    total_gift = sum(int(item.get("搭贈數量", 0) or 0) for item in st.session_state.cart_list)
    if cart_count > 0:
        render_sticky_cart_bar(cart_count, total_quantity, total_gift)

    # 區塊 2：新增商品
    render_section_header(
        "2",
        "新增商品",
        "先用條碼或名稱搜尋；需要瀏覽時再用品牌與品類縮小範圍。",
        "可重複加入",
    )

    input_suffix = f"_{st.session_state.input_reset_trigger}"

    with st.container(border=True):
        st.markdown("<div class='mini-label'>SEARCH</div>", unsafe_allow_html=True)
        st.markdown("<div class='subsection-title'>商品搜尋</div>", unsafe_allow_html=True)
        barcode_input = st.text_input(
            "條碼或商品名稱",
            placeholder="掃描條碼，或輸入商品名稱關鍵字",
            key=f"barcode_scan{input_suffix}",
        )

        st.markdown("<div class='subsection-title'>商品篩選</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='subsection-caption'>品牌、品類與產品清單可分別展開；手機版使用兩欄卡片，減少下滑距離。</div>",
            unsafe_allow_html=True,
        )

        brand_options = _get_unique_options(df_products["品牌"])
        _consume_query_toggle("toggle_brand", brand_options, BRAND_FILTER_STATE_KEY)
        selected_brand_filters = _ensure_list_state(BRAND_FILTER_STATE_KEY)

        st.markdown(
            "<div class='filter-panel-note'>建議先展開品牌篩選，再依品牌縮小後的品類繼續篩選。若沒有選取，代表不限制該條件；輸入條碼或商品名稱時，搜尋會優先於篩選。</div>",
            unsafe_allow_html=True,
        )

        with st.expander(f"1. 品牌篩選（已選 {len(selected_brand_filters)} 個）", expanded=False):
            selected_brand_filters = _render_link_grid(
                "品牌",
                brand_options,
                BRAND_FILTER_STATE_KEY,
                "toggle_brand",
                grid_class="filter-option-grid",
            )

        df_after_brand_filter = df_products.copy()
        if selected_brand_filters:
            df_after_brand_filter = df_after_brand_filter[
                df_after_brand_filter["品牌"].astype(str).isin(selected_brand_filters)
            ]

        category_options = _get_unique_options(df_after_brand_filter["品類"])
        _consume_query_toggle("toggle_category", category_options, CATEGORY_FILTER_STATE_KEY)
        selected_category_filters = _ensure_list_state(CATEGORY_FILTER_STATE_KEY)

        with st.expander(f"2. 品類篩選（已選 {len(selected_category_filters)} 個）", expanded=False):
            st.markdown("<div class='filter-subnote'>品類選項會依目前已選品牌自動更新。</div>", unsafe_allow_html=True)
            selected_category_filters = _render_link_grid(
                "品類",
                category_options,
                CATEGORY_FILTER_STATE_KEY,
                "toggle_category",
                grid_class="filter-option-grid",
            )

        selected_brand_count = len(selected_brand_filters)
        selected_category_count = len(selected_category_filters)
        if selected_brand_count or selected_category_count:
            st.markdown(
                f"<div class='filter-compact-summary'>已選條件｜品牌 {selected_brand_count} 個｜品類 {selected_category_count} 個</div>",
                unsafe_allow_html=True,
            )
            st.button(
                "清除篩選",
                use_container_width=True,
                key="clear_product_filters",
                on_click=_clear_filter_states,
            )

        df_step1 = df_after_brand_filter.copy()
        if selected_category_filters:
            df_step1 = df_step1[df_step1["品類"].astype(str).isin(selected_category_filters)]

        selected_filter_parts = []
        if selected_brand_filters:
            selected_filter_parts.append("品牌：" + "、".join(selected_brand_filters))
        if selected_category_filters:
            selected_filter_parts.append("品類：" + "、".join(selected_category_filters))

        if barcode_input:
            clean_input = barcode_input.strip()
            if clean_input.isdigit() and len(clean_input) >= 4:
                mask_barcode = df_products["國際條碼"].astype(str) == clean_input
            else:
                mask_barcode = pd.Series(False, index=df_products.index)

            mask_name = df_products["產品名稱"].astype(str).str.contains(clean_input, case=False, na=False)
            df_step2 = df_products[mask_barcode | mask_name]

            if df_step2.empty:
                st.error(f"找不到包含「{clean_input}」的條碼或商品名稱。")

            if selected_filter_parts:
                st.markdown(
                    "<div class='filter-summary filter-summary-search'>搜尋模式｜搜尋會優先於篩選｜符合 " + str(len(df_step2)) + " 項商品</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='filter-summary'>搜尋結果｜符合 {len(df_step2)} 項商品</div>",
                    unsafe_allow_html=True,
                )
        else:
            df_step2 = df_step1.copy()
            if selected_filter_parts:
                st.markdown(
                    "<div class='filter-summary'>目前篩選｜" + safe_html("｜".join(selected_filter_parts)) + f"｜符合 {len(df_step2)} 項商品</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='filter-summary filter-summary-muted'>目前未套用篩選｜共 {len(df_step2)} 項商品</div>",
                    unsafe_allow_html=True,
                )

        if df_step2.empty and not barcode_input:
            st.warning("目前篩選條件沒有符合的商品，請調整品牌或品類。")

        product_names = []
        for _, row in df_step2.iterrows():
            p_name = str(row["產品名稱"]).strip()
            if p_name and p_name not in product_names:
                product_names.append(p_name)

        # 條碼或關鍵字只命中一項時，自動選入待填數量區，保留原本快速搜尋體驗。
        selected_product_names = _ensure_list_state(PRODUCT_SELECTION_STATE_KEY)
        if barcode_input and len(product_names) == 1 and product_names[0] not in selected_product_names:
            selected_product_names.append(product_names[0])
            st.session_state[PRODUCT_SELECTION_STATE_KEY] = selected_product_names

        # 產品清單使用 HTML Grid 顯示，手機兩欄、桌機依寬度自動增加。
        display_limit = 30
        product_options_to_show = product_names[:display_limit]
        _consume_query_toggle("toggle_product", product_options_to_show, PRODUCT_SELECTION_STATE_KEY, max_items=20)

        with st.expander(f"3. 產品清單（符合 {len(product_names)} 項）", expanded=bool(barcode_input or selected_filter_parts)):
            if len(product_names) > display_limit:
                st.markdown(
                    f"<div class='filter-subnote'>符合 {len(product_names)} 項商品，先顯示前 {display_limit} 項；可輸入更多關鍵字縮小範圍。</div>",
                    unsafe_allow_html=True,
                )
            elif not product_names:
                st.markdown("<div class='filter-empty'>目前沒有符合的商品</div>", unsafe_allow_html=True)

            if product_options_to_show:
                _render_product_grid(product_options_to_show, max_items=20)

        selected_products_batch = [
            p_name for p_name in _ensure_list_state(PRODUCT_SELECTION_STATE_KEY) if p_name in global_prod_dict
        ]
        st.session_state[PRODUCT_SELECTION_STATE_KEY] = selected_products_batch

        st.markdown("<div class='subsection-title'>已選商品</div>", unsafe_allow_html=True)
        if selected_products_batch:
            st.markdown(f"<div class='product-count-chip'>已選擇 {len(selected_products_batch)} 項商品</div>", unsafe_allow_html=True)
            st.markdown("<div class='action-hint'>請輸入訂購數或搭贈數後加入購物車。商品名稱較長時，產品清單會自動省略顯示。</div>", unsafe_allow_html=True)

            with st.form(key=f"batch_form{input_suffix}"):
                for p_name in selected_products_batch:
                    p_info = global_prod_dict.get(p_name, {})
                    p_cat = p_info.get("品類", "一般")
                    p_brand = p_info.get("品牌", "")
                    p_barcode = p_info.get("國際條碼", "")
                    meta_parts = [x for x in [p_brand, p_cat, f"條碼 {p_barcode}" if p_barcode else ""] if x]
                    meta_text = "｜".join(meta_parts)

                    with st.container(border=True):
                        st.markdown(f"<div class='product-title'>{safe_html(p_name)}</div>", unsafe_allow_html=True)
                        if meta_text:
                            st.markdown(f"<div class='product-meta'>{safe_html(meta_text)}</div>", unsafe_allow_html=True)
                        qty_col, gift_col = st.columns(2, gap="medium")
                        with qty_col:
                            st.number_input("訂購數", min_value=0, step=1, value=None, placeholder="0", key=f"q_{p_name}")
                        with gift_col:
                            st.number_input("搭贈數", min_value=0, step=1, value=None, placeholder="0", key=f"g_{p_name}")

                submitted = st.form_submit_button("加入購物車", use_container_width=True)

                if submitted:
                    if not selected_sales_name or not selected_cust_name:
                        st.error("請先在訂單資訊區選擇業務與客戶。")
                    else:
                        items_added_count = 0
                        keys_to_clear = []

                        for p_name in selected_products_batch:
                            q_raw = st.session_state.get(f"q_{p_name}")
                            g_raw = st.session_state.get(f"g_{p_name}")

                            q_val = int(q_raw) if q_raw is not None else 0
                            g_val = int(g_raw) if g_raw is not None else 0

                            if q_val > 0 or g_val > 0:
                                p_info = global_prod_dict.get(p_name, {})
                                st.session_state.cart_list.insert(0, {
                                    "業務名稱": selected_sales_name,
                                    "客戶名稱": selected_cust_name,
                                    "產品編號": p_info.get("產品編號", "N/A"),
                                    "產品名稱": p_name,
                                    "品牌": p_info.get("品牌", ""),
                                    "品類": p_info.get("品類", ""),
                                    "訂購數量": q_val,
                                    "搭贈數量": g_val,
                                })
                                items_added_count += 1

                            keys_to_clear.extend([f"q_{p_name}", f"g_{p_name}"])

                        if items_added_count > 0:
                            for k in keys_to_clear:
                                if k in st.session_state:
                                    del st.session_state[k]

                            st.session_state[PRODUCT_SELECTION_STATE_KEY] = []
                            st.session_state.input_reset_trigger += 1
                            st.toast(f"成功加入 {items_added_count} 項商品")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning("所有商品的數量皆未輸入，未加入任何項目。")
        else:
            st.markdown("<div class='mobile-edit-note'>請先從產品清單點選商品。</div>", unsafe_allow_html=True)

    # 區塊 3：購物車
    render_section_header(
        "3",
        "購物車",
        "送出前請確認商品、訂購數與搭贈數。表格內可直接修改數量。",
        "最後確認",
    )

    with st.container(border=True):
        if len(st.session_state.cart_list) > 0:
            cart_df = pd.DataFrame(st.session_state.cart_list)
            total_quantity = int(cart_df["訂購數量"].fillna(0).sum()) if "訂購數量" in cart_df.columns else 0
            total_gift = int(cart_df["搭贈數量"].fillna(0).sum()) if "搭贈數量" in cart_df.columns else 0
            st.markdown(f"""
                <div class='cart-summary'>
                    <div class='summary-card'>
                        <div class='summary-label'>商品項目</div>
                        <div class='summary-value'>{len(cart_df)}</div>
                    </div>
                    <div class='summary-card'>
                        <div class='summary-label'>訂購數量</div>
                        <div class='summary-value'>{total_quantity}</div>
                    </div>
                    <div class='summary-card'>
                        <div class='summary-label'>搭贈數量</div>
                        <div class='summary-value'>{total_gift}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown(
                "<div class='mobile-edit-note'>請在下方表格確認商品與數量；需要修改時可直接調整數字，刪除商品可使用表格列操作。</div>",
                unsafe_allow_html=True,
            )

            edited_cart = st.data_editor(
                cart_df,
                column_config={
                    "產品名稱": st.column_config.TextColumn("商品", disabled=True, width="large"),
                    "訂購數量": st.column_config.NumberColumn("訂購", min_value=0, step=1, width="small"),
                    "搭贈數量": st.column_config.NumberColumn("搭贈", min_value=0, step=1, width="small"),
                },
                column_order=["產品名稱", "訂購數量", "搭贈數量"],
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="final_cart_editor",
            )

            if not edited_cart.equals(cart_df):
                st.session_state.cart_list = edited_cart.to_dict("records")

            final_sales_label = safe_html(selected_sales_name) if selected_sales_name else "尚未選擇業務"
            final_cust_label = safe_html(selected_cust_name) if selected_cust_name else "尚未選擇客戶"
            st.markdown(f"""
                <div class='cart-final-panel'>
                    <div class='cart-final-title'>送出前確認</div>
                    <div class='cart-final-value'>{final_sales_label} → {final_cust_label}</div>
                    <div class='cart-final-title' style='margin-top:0.45rem;'>本次合計</div>
                    <div class='cart-final-value'>{len(st.session_state.cart_list)} 項商品｜訂購 {total_quantity}｜搭贈 {total_gift}</div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("")
            col_clear, col_submit = st.columns([1, 2], gap="medium")
            with col_clear:
                if st.button("清空購物車", use_container_width=True, key="clear_cart_main_btn"):
                    st.session_state.cart_list = []
                    st.rerun()
            with col_submit:
                if st.button("送出訂單", type="primary", use_container_width=True, key="bottom_checkout_btn"):
                    trigger_order_submission()
        else:
            st.info("購物車目前是空的。請先在新增商品區加入商品。")
