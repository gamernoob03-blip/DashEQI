"""
pages/exportar.py — Página Exportar
Permite ao usuário selecionar indicadores e baixar CSVs com as séries completas.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from data import get_bcb_full, get_bcb_range, get_hist, SGS, GLOBAL


def render():
    # ── Cabeçalho ─────────────────────────────────────────────────────────
    st.markdown(
        "<div class='page-top'><h1>Exportar dados</h1>"
        "<div class='ts'>BCB/SGS (Brasil) · Yahoo Finance (globais)</div></div>",
        unsafe_allow_html=True,
    )

    fonte = st.radio(
        "Fonte:",
        ["BCB/SGS — Brasil", "Yahoo Finance — Globais"],
        horizontal=True,
    )
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if fonte == "BCB/SGS — Brasil":
        _export_bcb()
    else:
        _export_yahoo()

    # ── Catálogo de indicadores ───────────────────────────────────────────
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    with st.expander("Ver todos os indicadores e ativos disponíveis"):
        st.markdown("**BCB/SGS — Indicadores Brasil**")
        st.dataframe(
            pd.DataFrame([
                {"Indicador": k, "Cód. SGS": v[0], "Unidade": v[1], "Freq.": v[2]}
                for k, v in SGS.items()
            ]),
            hide_index=True, use_container_width=False,
        )
        st.markdown("<br>**Yahoo Finance — Ativos Globais**", unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame([
                {"Ativo": k, "Símbolo": v[0], "Unidade": v[1]}
                for k, v in GLOBAL.items()
            ]),
            hide_index=True, use_container_width=False,
        )


# ─── Sub-seções ───────────────────────────────────────────────────────────────
def _export_bcb():
    """Formulário de exportação para séries BCB/SGS."""
    col1, col2, col3 = st.columns([2, 1.5, 1.5])
    with col1:
        ind = st.selectbox("Indicador", list(SGS.keys()), index=1, key="exp_ind")
    with col2:
        d_ini = st.date_input(
            "De", value=datetime.today() - timedelta(days=365), key="exp_ini"
        )
    with col3:
        d_fim = st.date_input("Até", value=datetime.today(), key="exp_fim")

    modo = st.radio(
        "Período:",
        ["Usar datas acima", "Série completa desde o início"],
        horizontal=True,
        key="exp_modo",
    )

    if st.button("Gerar CSV", type="primary", key="exp_bcb_btn"):
        cod, unit, freq, _ = SGS[ind]

        with st.spinner(f"Buscando {ind}..."):
            if "completa" in modo:
                df_exp = get_bcb_full(cod)
            else:
                if d_ini >= d_fim:
                    st.error("Data início deve ser anterior à data fim.")
                    return
                df_exp = get_bcb_range(
                    cod,
                    d_ini.strftime("%d/%m/%Y"),
                    d_fim.strftime("%d/%m/%Y"),
                )

        if df_exp.empty:
            st.warning("Nenhum dado encontrado. Verifique a disponibilidade da API BCB.")
            return

        df_out = df_exp.copy()
        df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
        st.success(f"✅ **{len(df_out)} registros** — {ind} ({unit}) · {freq}")
        st.dataframe(
            df_out.rename(columns={"data": "Data", "valor": f"Valor ({unit})"}),

            height=min(380, 46 + len(df_out) * 35),
        )
        suf  = "completo" if "completa" in modo else f"{d_ini}_{d_fim}"
        nome = f"{ind.replace(' ', '_')}_{suf}.csv"
        csv  = df_out.to_csv(index=False).encode("utf-8-sig")
        st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")


def _export_yahoo():
    """Formulário de exportação para ativos Yahoo Finance."""
    col1, col2 = st.columns([2, 1])
    with col1:
        ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="exp_ativo")
    with col2:
        anos = st.select_slider(
            "Período (anos)", [1, 2, 3, 5, 10], value=5, key="exp_anos"
        )

    if st.button("Gerar CSV", type="primary", key="exp_yahoo_btn"):
        sym, unit, _ = GLOBAL[ativo]

        with st.spinner(f"Buscando {ativo}..."):
            df_exp = get_hist(sym, years=anos)

        if df_exp.empty:
            st.warning("Sem dados disponíveis.")
            return

        df_out = df_exp.copy()
        df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
        st.success(f"✅ **{len(df_out)} registros** — {ativo}")
        st.dataframe(
            df_out.rename(columns={"data": "Data", "valor": f"Valor ({unit})"}),

            height=min(380, 46 + len(df_out) * 35),
        )
        nome = f"{ativo.replace(' ', '_')}_{anos}anos.csv"
        csv  = df_out.to_csv(index=False).encode("utf-8-sig")
        st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")
