"""
sidebar.py — Menu lateral
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

NAV_ICONS = {
    "Início":           "⌂",
    "Mercados Globais": "◎",
    "Gráficos":         "⌇",
    "Exportar":         "↓",
}
NAV_KEYS = list(NAV_ICONS.keys())


def init_state():
    if "pagina" not in st.session_state:
        st.session_state.pagina = "Início"
    if "sb_collapsed" not in st.session_state:
        st.session_state.sb_collapsed = False


def render():
    with st.sidebar:
        if st.session_state.sb_collapsed:
            _render_collapsed()
        else:
            _render_expanded()


def _nav_btn(key: str, label: str):
    is_active = st.session_state.pagina == key
    prefix    = "c" if st.session_state.sb_collapsed else "e"
    if st.button(label, key=f"nav_{prefix}_{key}",
                 type="primary" if is_active else "secondary",
                 use_container_width=True,
                 help=key if st.session_state.sb_collapsed else None):
        st.session_state.pagina = key
        st.rerun()


def _render_collapsed():
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Botão expandir
    st.markdown("<div class='sb-toggle-btn' style='display:flex;justify-content:center;padding:4px 8px'>",
                unsafe_allow_html=True)
    if st.button("›", key="sb_expand"):
        st.session_state.sb_collapsed = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:8px 6px;border-color:#e8eaed'>", unsafe_allow_html=True)

    # CSS para centralizar ícones no modo colapsado
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] .stButton > button {
        justify-content: center !important;
        padding: 9px 0 !important;
        font-size: 18px !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        padding: 9px 0 !important;
        border-left: none !important;
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    for key in NAV_KEYS:
        st.markdown("<div style='padding:0 6px'>", unsafe_allow_html=True)
        _nav_btn(key, NAV_ICONS[key])
        st.markdown("</div>", unsafe_allow_html=True)


def _render_expanded():
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    col_logo, col_btn = st.columns([5, 2])
    with col_logo:
        st.markdown(
            "<div style='padding:14px 0 8px 18px'>"
            "<div style='font-size:9px;font-weight:700;color:#d1d5db;"
            "letter-spacing:3px;text-transform:uppercase;margin-bottom:3px'>BR</div>"
            "<div style='font-size:15px;font-weight:700;color:#111827;"
            "letter-spacing:-0.3px'>Macro Brasil</div></div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sb-toggle-btn'>", unsafe_allow_html=True)
        if st.button("‹", key="sb_collapse"):
            st.session_state.sb_collapsed = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0 6px;border-color:#e8eaed'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:9px;font-weight:700;color:#9ca3af;"
        "text-transform:uppercase;letter-spacing:2px;"
        "padding:2px 18px 8px'>Navegação</div>",
        unsafe_allow_html=True,
    )

    for key in NAV_KEYS:
        st.markdown("<div style='padding:0 6px'>", unsafe_allow_html=True)
        _nav_btn(key, f"{NAV_ICONS[key]}   {key}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#e8eaed;margin-bottom:8px'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:9px;color:#d1d5db;line-height:1.9;padding:0 18px 16px'>"
        "Fontes: BCB/SGS · Yahoo Finance<br>"
        "Mercados: ↻ 60s &nbsp;|&nbsp; BCB: ↻ 1h"
        "</div>",
        unsafe_allow_html=True,
    )
