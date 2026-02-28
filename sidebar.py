"""
sidebar.py — Menu lateral simples e direto, sem CSS customizado.
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
        st.title("🇧🇷 Macro Brasil")
        st.divider()

        for page in NAV_PAGES:
            if st.button(
                page,
                key=f"nav_{page}",
                type="primary" if st.session_state.pagina == page else "secondary",
                width="stretch",
            ):
                st.session_state.pagina = page
                st.rerun()

        st.divider()
        st.caption("Fontes: BCB/SGS · Yahoo Finance")
        st.caption("Mercados ↻60s · BCB ↻1h")
