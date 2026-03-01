"""
sidebar.py — Menu lateral com ícones
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BRT = ZoneInfo("America/Sao_Paulo")

# (ícone, label, chave)
NAV_ITEMS = [
    ("⌂",  "Início",           "Início"),
    ("◎",  "Mercados Globais", "Mercados Globais"),
    ("⌇",  "Gráficos",        "Gráficos"),
    ("↓",  "Exportar",        "Exportar"),
]

def init_state():
    if "pagina" not in st.session_state:
        st.session_state.pagina = "Início"

def render():
    with st.sidebar:
        # Logo e horário
        st.markdown(
            "<div style='padding:16px 0 4px 4px'>"
            "<span style='font-size:9px;font-weight:700;color:#aaa;letter-spacing:3px'>BR</span>"
            "<span style='font-size:16px;font-weight:700;color:#111827;margin-left:6px'>Macro Brasil</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"🕐 {datetime.now(TZ_BRT).strftime('%d/%m/%Y  %H:%M')} (Brasília)")
        st.divider()

        # Botões de navegação com ícone
        for icon, label, key in NAV_ITEMS:
            is_active = st.session_state.pagina == key
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state.pagina = key
                st.rerun()

        st.divider()
        st.caption("Fontes: BCB/SGS · Yahoo Finance")
        st.caption("Mercados ↻60s · BCB ↻1h")
