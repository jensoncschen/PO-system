from pathlib import Path
from typing import Iterable

import streamlit as st


def load_css(file_path: str) -> None:
    """Load an external CSS file into the Streamlit page."""
    css_path = Path(file_path)
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    else:
        st.warning(f"找不到樣式檔案：{file_path}")


def render_sidebar() -> str:
    """Render the sidebar navigation and return the selected page name."""
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-title">雲端訂購</div>
            <div class="sidebar-subtitle">快速建立訂單與匯出資料</div>
        </div>
        <div class="sidebar-section-label">功能</div>
        """,
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio(
        "功能選單",
        ["前台下單", "訂單匯出", "後台管理"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("<div class='sidebar-section-label'>資料</div>", unsafe_allow_html=True)
    if st.sidebar.button("重新整理雲端資料"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown(
        "<div class='sidebar-note'>購物車操作已整合到前台主畫面，避免手機版重複操作。</div>",
        unsafe_allow_html=True,
    )
    return page


def render_page_header(title: str, subtitle: str, steps: Iterable[str]) -> None:
    """Render the shared hero header used by each main page."""
    step_html = "".join(f"<span class='hero-pill'>{step}</span>" for step in steps)
    st.markdown(
        f"""
        <div class='hero-card'>
            <div class='page-title'>{title}</div>
            <div class='page-subtitle'>{subtitle}</div>
            <div class='hero-steps'>{step_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(index: str, title: str, note: str, tag: str) -> None:
    """Render the shared section header block."""
    st.markdown(
        f"""
        <div class='section-header'>
            <div class='section-title-wrap'>
                <span class='section-index'>{index}</span>
                <div>
                    <div class='section-title-text'>{title}</div>
                    <div class='section-note'>{note}</div>
                </div>
            </div>
            <span class='section-tag'>{tag}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sticky_cart_bar(cart_count: int, total_quantity: int, total_gift: int) -> None:
    """Render the bottom floating cart status bar."""
    if cart_count <= 0:
        return

    st.markdown(
        f"""
        <div class="sticky-cart-bar">
            <div class="sticky-cart-content">
                <span>購物車｜{cart_count} 項｜訂購 {total_quantity}｜搭贈 {total_gift}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
