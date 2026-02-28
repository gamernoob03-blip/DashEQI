"""
pages/graficos.py — Página Gráficos
Explorador de séries completas com filtro por período e download CSV.
"""

import streamlit as st
import pandas as pd

from data import get_bcb_full, get_hist, SGS, GLOBAL
from ui   import line_fig, bar_fig, CHART_CFG


def render():
    # ── Cabeçalho ─────────────────────────────────────────────────────────
    st.markdown(
        "<div class='page-top'><h1>Gráficos</h1>"
        "<div class='ts'>Série completa · filtro por período</div></div>",
        unsafe_allow_html=True,
    )

    tab_bcb, tab_yahoo = st.tabs([
        "BCB — Indicadores Brasil",
        "Yahoo Finance — Ativos Globais",
    ])

    # ── Aba BCB ───────────────────────────────────────────────────────────
    with tab_bcb:
        col1, _ = st.columns([2, 3])
        with col1:
            ind = st.selectbox("Indicador", list(SGS.keys()), key="graf_ind")

        cod, unit, freq, tipo = SGS[ind]

        with st.spinner(f"Carregando série de {ind}..."):
            df_full = get_bcb_full(cod)

        if df_full.empty:
            st.warning("⚠️ Sem dados. A API BCB pode estar temporariamente indisponível.")
            return

        date_min      = df_full["data"].min().date()
        date_max      = df_full["data"].max().date()
        default_start = max(
            date_min,
            (df_full["data"].max() - pd.DateOffset(months=12)).date(),
        )

        # Info da série
        st.markdown(
            f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px 0'>"
            f"Disponível: <strong style='color:#374151'>{date_min.strftime('%d/%m/%Y')}</strong>"
            f" → <strong style='color:#374151'>{date_max.strftime('%d/%m/%Y')}</strong>"
            f" &nbsp;·&nbsp; {len(df_full)} obs.</div>",
            unsafe_allow_html=True,
        )

        # Filtro de datas
        c2, c3, c4 = st.columns([2, 2, 1])
        with c2:
            d_ini = st.date_input(
                "De", value=default_start,
                min_value=date_min, max_value=date_max, key="graf_ini",
            )
        with c3:
            d_fim = st.date_input(
                "Até", value=date_max,
                min_value=date_min, max_value=date_max, key="graf_fim",
            )
        with c4:
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            if st.button("Série completa", key="graf_reset"):
                st.session_state["graf_ini"] = date_min
                st.session_state["graf_fim"] = date_max
                st.rerun()

        if d_ini >= d_fim:
            st.error("⚠️ Data início deve ser anterior à data fim.")
            return

        mask = (df_full["data"].dt.date >= d_ini) & (df_full["data"].dt.date <= d_fim)
        df_g = df_full[mask].copy()

        if df_g.empty:
            st.warning("Nenhuma observação no período selecionado.")
            return

        st.success(f"✅ {len(df_g)} observações · {ind} ({unit}) · {freq}")

        fig = (
            bar_fig(df_g, f"{ind} ({unit})", suffix=f" {unit}", height=420, interactive=True)
            if tipo == "bar"
            else line_fig(df_g, f"{ind} ({unit})", "#1a2035", suffix=f" {unit}", height=420, interactive=True)
        )
        st.plotly_chart(
            fig, use_container_width=True,
            config={**CHART_CFG, "scrollZoom": True},
        )

        _download_button(df_g, f"{ind.replace(' ','_')}_{d_ini}_{d_fim}.csv")

    # ── Aba Yahoo ─────────────────────────────────────────────────────────
    with tab_yahoo:
        col1, col2 = st.columns([2, 1])
        with col1:
            ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="graf_ativo")
        with col2:
            anos = st.select_slider(
                "Período (anos)", [1, 2, 3, 5, 10], value=5, key="graf_anos"
            )

        sym, unit, _ = GLOBAL[ativo]

        with st.spinner(f"Carregando {ativo}..."):
            df_g = get_hist(sym, years=anos)

        if df_g.empty:
            st.warning("Sem dados históricos disponíveis.")
            return

        st.success(f"✅ {len(df_g)} observações · {ativo}")
        fig = line_fig(
            df_g, f"{ativo} — {anos} ano(s)", "#1a2035",
            suffix=f" {unit}", height=420, interactive=True,
        )
        st.plotly_chart(
            fig, use_container_width=True,
            config={**CHART_CFG, "scrollZoom": True},
        )
        _download_button(df_g, f"{ativo.replace(' ','_')}_{anos}a.csv")


# ─── Helper ───────────────────────────────────────────────────────────────────
def _download_button(df: pd.DataFrame, filename: str):
    """Gera botão de download CSV com dados formatados."""
    df_out = df.copy()
    df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
    csv = df_out.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        f"💾 Baixar CSV ({len(df_out)} linhas)",
        data=csv, file_name=filename, mime="text/csv",
    )
