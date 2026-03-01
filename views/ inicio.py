"""
pages/inicio.py — Página Início
Exibe os KPI cards principais e gráficos históricos de 12 meses.
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
TZ_BRT = ZoneInfo("America/Sao_Paulo")

from data import get_quote, get_bcb, SGS, GLOBAL
from ui   import kpi_card, line_fig, bar_fig, section_title, CHART_CFG, fmt


def render():
    # ── Cabeçalho ─────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='page-top'>"
        f"<h1>Dashboard Macro Brasil</h1>"
        f"<div class='ts'>Atualizado<br>"
        f"<strong style='color:#374151'>{datetime.now(TZ_BRT).strftime('%d/%m/%Y %H:%M')}</strong>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── Carga de dados ────────────────────────────────────────────────────
    with st.spinner("Carregando indicadores..."):
        ibov_d  = get_quote("^BVSP")
        usd_d   = get_quote("USDBRL=X")
        eur_d   = get_quote("EURBRL=X")
        df_sel  = get_bcb(432,   13)
        df_ipca = get_bcb(433,   13)
        df_ibc  = get_bcb(24363, 13)
        df_cam  = get_bcb(1,     50)
        df_pib  = get_bcb(4380,  8)
        df_des  = get_bcb(24369, 8)

    # ── Bloco 1: Mercados ─────────────────────────────────────────────────
    section_title("Indicadores de Mercado", "↻ 60s", "badge-live")

    c1, c2, c3 = st.columns(3)
    with c1:
        v = ibov_d.get("price")
        kpi_card(
            "IBOVESPA",
            fmt(v, 0) + " pts" if v else "—",
            ibov_d.get("chg_p"),
            sub=f"Var. dia: {fmt(ibov_d.get('chg_v'), 0)} pts"
                if ibov_d.get("chg_v") is not None else "—",
            d=ibov_d,
        )
    with c2:
        v = usd_d.get("price")
        kpi_card(
            "Dólar (USD/BRL)",
            f"R$ {fmt(v, 4)}" if v else "—",
            usd_d.get("chg_p"),
            sub=f"Ant.: R$ {fmt(usd_d.get('prev'), 4)}" if v else "—",
            invert=True, d=usd_d,
        )
    with c3:
        v = eur_d.get("price")
        kpi_card(
            "Euro (EUR/BRL)",
            f"R$ {fmt(v, 4)}" if v else "—",
            eur_d.get("chg_p"),
            sub=f"Ant.: R$ {fmt(eur_d.get('prev'), 4)}" if v else "—",
            invert=True, d=eur_d,
        )

    # ── Bloco 2: Indicadores econômicos ───────────────────────────────────
    section_title("Indicadores Econômicos", "↻ diário", "badge-daily")

    c4, c5, c6 = st.columns(3)
    with c4:
        if not df_sel.empty:
            v   = df_sel["valor"].iloc[-1]
            ref = df_sel["data"].iloc[-1].strftime("%b/%Y")
            kpi_card("Selic", f"{fmt(v)}% a.a.", sub=f"Ref: {ref}")
        else:
            kpi_card("Selic", "—", sub="BCB indisponível")

    with c5:
        if not df_ipca.empty:
            v     = df_ipca["valor"].iloc[-1]
            ref   = df_ipca["data"].iloc[-1].strftime("%b/%Y")
            delta = (
                float(df_ipca["valor"].iloc[-1] - df_ipca["valor"].iloc[-2])
                if len(df_ipca) >= 2 else None
            )
            kpi_card("IPCA", f"{fmt(v)}% mês", chg_p=delta, sub=f"Ref: {ref}")
        else:
            kpi_card("IPCA", "—", sub="BCB indisponível")

    with c6:
        if not df_des.empty:
            v   = df_des["valor"].iloc[-1]
            ref = df_des["data"].iloc[-1].strftime("%b/%Y")
            kpi_card("Desemprego (PNAD)", f"{fmt(v)}%", sub=f"Ref: {ref}")
        else:
            kpi_card("Desemprego (PNAD)", "—", sub="BCB indisponível")

    # ── Bloco 3: Gráficos históricos ──────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Histórico — 12 meses'
        '<span style="font-size:10px;font-weight:400;color:#9ca3af;'
        'text-transform:none;letter-spacing:0;margin-left:4px">'
        '→ série completa em Gráficos</span></div>',
        unsafe_allow_html=True,
    )

    ca, cb = st.columns(2)
    with ca:
        if not df_sel.empty:
            st.plotly_chart(
                line_fig(df_sel, "Selic (% a.a.)", "#1a2035", suffix="%"),
                width="stretch", config=CHART_CFG,
            )
        else:
            st.warning("⚠️ Selic: indisponível.")
    with cb:
        if not df_ipca.empty:
            st.plotly_chart(
                bar_fig(df_ipca, "IPCA (% ao mês)", suffix="%"),
                width="stretch", config=CHART_CFG,
            )
        else:
            st.warning("⚠️ IPCA: indisponível.")

    cc, cd = st.columns(2)
    with cc:
        df_cam30 = df_cam.tail(30) if not df_cam.empty else df_cam
        if not df_cam30.empty:
            st.plotly_chart(
                line_fig(df_cam30, "Dólar PTAX — 30 dias úteis (R$)", "#d97706", suffix=" R$"),
                width="stretch", config=CHART_CFG,
            )
        else:
            st.warning("⚠️ Dólar PTAX: indisponível.")
    with cd:
        if not df_ibc.empty:
            st.plotly_chart(
                line_fig(df_ibc, "IBC-Br", "#0891b2", fill=False),
                width="stretch", config=CHART_CFG,
            )
        else:
            st.warning("⚠️ IBC-Br: indisponível.")

    ce, cf = st.columns(2)
    with ce:
        if not df_pib.empty:
            st.plotly_chart(
                bar_fig(df_pib, "PIB — variação trimestral (%)", suffix="%"),
                width="stretch", config=CHART_CFG,
            )
        else:
            st.warning("⚠️ PIB: indisponível.")
    with cf:
        if not df_des.empty:
            st.plotly_chart(
                line_fig(df_des, "Desemprego PNAD (%)", "#dc2626", fill=True, suffix="%"),
                width="stretch", config=CHART_CFG,
            )
        else:
            st.warning("⚠️ Desemprego: indisponível.")

    st.markdown(
        "<div style='text-align:center;color:#d1d5db;font-size:10px;"
        "margin-top:20px;margin-bottom:8px'>"
        "Yahoo Finance (↻60s) • BCB/SGS (↻1h)</div>",
        unsafe_allow_html=True,
    )
