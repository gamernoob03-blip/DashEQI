"""
pages/mercados.py — Página Mercados Globais
Cotações em tempo real e histórico de 2 anos para ativos internacionais.
"""

import streamlit as st
import time
from datetime import datetime

from data import get_quote, get_hist, GLOBAL
from ui   import kpi_card, line_fig, section_title, CHART_CFG, fmt


# Agrupamento visual dos ativos
GRUPOS = {
    "Brasil":       ["IBOVESPA", "Dólar (USD/BRL)", "Euro (EUR/BRL)"],
    "Índices EUA":  ["S&P 500", "Nasdaq 100", "Dow Jones"],
    "Europa":       ["FTSE 100", "DAX"],
    "Energia":      ["Petróleo Brent", "Petróleo WTI"],
    "Metais":       ["Ouro", "Prata", "Cobre"],
    "Cripto":       ["Bitcoin", "Ethereum"],
}

DESTAQUES_HIST = [
    ("IBOVESPA",       "^BVSP",  "#1a2035", "pts"),
    ("S&P 500",        "^GSPC",  "#0891b2", "pts"),
    ("Petróleo Brent", "BZ=F",   "#d97706", "US$"),
    ("Ouro",           "GC=F",   "#b45309", "US$"),
]


def render():
    # ── Cabeçalho ─────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='page-top'><h1>Mercados Globais</h1>"
        f"<div class='ts'>Atualizado<br>"
        f"<strong style='color:#374151'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── Cards por grupo ───────────────────────────────────────────────────
    for grupo, ativos in GRUPOS.items():
        section_title(grupo, "↻ 60s", "badge-live")
        cols = st.columns(len(ativos))
        for i, nome in enumerate(ativos):
            sym, unit, inv = GLOBAL[nome]
            d = get_quote(sym)
            with cols[i]:
                v      = d.get("price")
                prefix = "R$ " if unit == "R$" else ("US$ " if "US$" in unit else "")
                dec    = 0 if unit == "pts" else 2
                val_str = f"{prefix}{fmt(v, dec)}" if v else "—"
                kpi_card(
                    nome, val_str,
                    d.get("chg_p"),
                    sub=f"Ant.: {prefix}{fmt(d.get('prev'), dec)}" if v else "",
                    invert=inv, d=d,
                )
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Histórico 2 anos ──────────────────────────────────────────────────
    section_title("Histórico — 2 anos")

    g1, g2 = st.columns(2)
    g3, g4 = st.columns(2)
    for col, (nome, sym, cor, unit) in zip([g1, g2, g3, g4], DESTAQUES_HIST):
        with col:
            df_h = get_hist(sym, years=2)
            if not df_h.empty:
                st.plotly_chart(
                    line_fig(df_h, f"{nome} — 2 anos", cor, fill=True, suffix=f" {unit}"),
                    use_container_width=True, config=CHART_CFG,
                )
            else:
                st.info(f"{nome}: sem dados.")

    # ── Auto-refresh a cada 60s ───────────────────────────────────────────
    time.sleep(60)
    st.rerun()
