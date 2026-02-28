"""
sidebar.py — Menu lateral (versão robusta com st.sidebar.radio)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

NAV_PAGES = ["Início", "Mercados Globais", "Gráficos", "Exportar"]

def init_state():
    if "pagina" not in st.session_state:
        st.session_state.pagina = "Início"

def render():
    with st.sidebar:
        st.markdown(
            "<div style='padding:18px 8px 4px 8px'>"
            "<div style='font-size:9px;font-weight:700;color:#aaa;"
            "letter-spacing:3px;text-transform:uppercase;margin-bottom:4px'>BR</div>"
            "<div style='font-size:17px;font-weight:700;color:#111827;"
            "letter-spacing:-0.3px;margin-bottom:16px'>Macro Brasil</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        pagina = st.radio(
            "Navegação",
            NAV_PAGES,
            index=NAV_PAGES.index(st.session_state.pagina),
            label_visibility="collapsed",
        )

        if pagina != st.session_state.pagina:
            st.session_state.pagina = pagina
            st.rerun()

        st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
        st.caption("Fontes: BCB/SGS · Yahoo Finance")
        st.caption("Mercados ↻60s · BCB ↻1h")
