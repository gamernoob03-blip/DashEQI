"""
sidebar.py — Menu lateral
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BRT = ZoneInfo("America/Sao_Paulo")
NAV_PAGES = ["Início", "Mercados Globais", "Gráficos", "Exportar"]

def now_brt() -> datetime:
    """Retorna hora atual no fuso de Brasília."""
    return datetime.now(TZ_BRT)

def init_state():
    if "pagina" not in st.session_state:
        st.session_state.pagina = "Início"

def render():
    with st.sidebar:
        st.markdown("### 🇧🇷 Macro Brasil")
        st.caption(f"🕐 {now_brt().strftime('%d/%m/%Y %H:%M')} (Brasília)")
        st.divider()

        for page in NAV_PAGES:
            is_active = st.session_state.pagina == page
            if st.button(
                page,
                key=f"nav_{page}",
                type="primary" if is_active else "secondary",
                use_container_width=True,   # CORRETO para st.button
            ):
                st.session_state.pagina = page
                st.rerun()

        st.divider()
        st.caption("Fontes: BCB/SGS · Yahoo Finance")
        st.caption("Mercados ↻60s · BCB ↻1h")
