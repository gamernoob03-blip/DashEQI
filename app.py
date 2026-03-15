"""
app.py — EQI Dashboard Macro
Importa de config, data, charts e components.
Toda lógica de página fica aqui, inline.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# set_page_config DEVE ser o primeiro comando Streamlit — antes de qualquer import
# que possa chamar st.* no nível de módulo (ex: @st.cache_resource em data.py)
import streamlit as st
st.set_page_config(page_title="EQI Dashboard Macro", page_icon="🇧🇷",
                   layout="wide", initial_sidebar_state="expanded", menu_items={})

import time
import warnings
import urllib3
import pandas as pd
from datetime import datetime, timedelta, date

from settings import (
    logger, GLOBAL, SGS, SGS_PERIODOS, NUCLEO_SGS, BCB_META, BCB_TOLE,
    IPCA_GRUPOS_IDS, NAV, NAV_SLUGS, HOME_CHARTS, HOME_KPIS,
    MERCADOS_HIST, CORES_COMP, COR_IPCA_LINHA, COR_MEDIA_NUCL,
    PERIODOS_ORIGINAIS, P_ORIGINAL,
    H_MEDIUM, H_LARGE, H_XLARGE,
    SGS_DESCRICAO, GLOBAL_DESCRICAO, FOCUS_INDICADORES,
)
from data import (
    get_quote, get_hist, get_bcb_full,
    get_focus_anual, get_focus_12m,
    get_ipca_grupos, get_ipca_acum_grupo, aplicar_periodo,
)
from charts import (
    line_fig, bar_fig,
    cores_overlay_fig, acum12m_meta_fig, grupos_bar_fig, grupos_linhas_fig,
    nucleos_acum12m_fig, grupos_acum12m_fig, comparacao_fig,
)
from components import inject_css, fmt, page_header, sec_title, kpi_card, now_brt, stale_banner, render_chart

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS")

_GRUPO_IDS = [g.strip() for g in IPCA_GRUPOS_IDS.split(",")]

inject_css()

# ── Estado de sessão ──────────────────────────────────────────────────────────
if "pagina"         not in st.session_state: st.session_state.pagina         = "Início"
if "tabela_aberta"  not in st.session_state: st.session_state.tabela_aberta  = False
if "mercados_ativo" not in st.session_state: st.session_state.mercados_ativo = "IBOVESPA"

# ── Query params → session state (link direto para página/ativo) ──────────────
_NAV_SLUG_INV = {v: k for k, v in NAV_SLUGS.items()}
_qp_page = st.query_params.get("page", None)
_qp_mv   = st.query_params.get("mv",   None)
# Sincroniza sempre (não só na primeira carga) para suportar deep links
if _qp_page and _qp_page in _NAV_SLUG_INV:
    st.session_state.pagina = _NAV_SLUG_INV[_qp_page]
elif not _qp_page:
    # Mantém URL sincronizada com a página atual
    st.query_params["page"] = NAV_SLUGS.get(st.session_state.pagina, "inicio")
if _qp_mv and _qp_mv in GLOBAL:
    st.session_state.mercados_ativo = _qp_mv

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='padding:20px 4px 12px 4px'><span style='font-size:24px;font-weight:900;color:#004031;letter-spacing:-0.5px'>EQI</span></div>", unsafe_allow_html=True)
    st.divider()
    for label in NAV:
        slug = NAV_SLUGS.get(label, label.lower())
        st.markdown(f"<div class='nav-marker nav-{slug}'></div>", unsafe_allow_html=True)
        if st.button(label, key=f"nav_{label}", type="primary" if st.session_state.pagina == label else "secondary", use_container_width=True):
            st.session_state.pagina = label
            st.query_params["page"] = NAV_SLUGS.get(label, label.lower())
            st.rerun()
    st.divider()
    st.caption("Fontes: BCB/SGS · IBGE/SIDRA · Yahoo Finance")
    st.caption("Mercados ↻15min · BCB/IBGE ↻1h")

# ══════════════════════════════════════════════════════════════════════════════
# INÍCIO
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pagina == "Início":
    page_header("EQI Dashboard Macro")
    try:
        with st.spinner("Carregando..."):
            ibov = get_quote(GLOBAL["IBOVESPA"].simbolo)
            usd  = get_quote(GLOBAL["Dólar (USD/BRL)"].simbolo)
            eur  = get_quote(GLOBAL["Euro (EUR/BRL)"].simbolo)
            # Carrega séries completas de uma vez — filtro na exibição
            _home_data = {
                nome: get_bcb_full(SGS[nome].codigo)
                for nome, _ in HOME_CHARTS
            }
    except Exception as e:
        logger.error("Início: %s", e); st.error("⚠️ Erro ao carregar dados.")
        if st.button("↺ Tentar novamente"): st.cache_data.clear(); st.rerun()
        st.stop()

    sec_title("Indicadores de Mercado", "↻ 15min", "badge-live")
    c1, c2, c3 = st.columns(3)
    with c1:
        v = ibov.get("price")
        kpi_card("IBOVESPA", fmt(v,0)+" pts" if v else "—", ibov.get("chg_p"),
                 sub=f"Var. dia: {fmt(ibov.get('chg_v'),0)} pts" if ibov.get("chg_v") is not None else "", d=ibov)
    with c2:
        v = usd.get("price")
        kpi_card("Dólar (USD/BRL)", f"R$ {fmt(v,4)}" if v else "—", usd.get("chg_p"),
                 sub=f"Ant.: R$ {fmt(usd.get('prev'),4)}" if v else "", invert=True, d=usd)
    with c3:
        v = eur.get("price")
        kpi_card("Euro (EUR/BRL)", f"R$ {fmt(v,4)}" if v else "—", eur.get("chg_p"),
                 sub=f"Ant.: R$ {fmt(eur.get('prev'),4)}" if v else "", invert=True, d=eur)

    sec_title("Indicadores Econômicos", "↻ diário", "badge-daily")
    for nome, _, _ in HOME_KPIS:
        stale_banner(_home_data.get(nome, pd.DataFrame()), nome)
    kpi_cols = st.columns(len(HOME_KPIS))
    for col, (nome, label, fmt_str) in zip(kpi_cols, HOME_KPIS):
        df_k = _home_data.get(nome, pd.DataFrame())
        with col:
            if not df_k.empty:
                v  = df_k["valor"].iloc[-1]
                d2 = float(v - df_k["valor"].iloc[-2]) if len(df_k) >= 2 else None
                kpi_card(label, fmt_str.format(v=fmt(v), u=SGS[nome].unidade),
                         chg_p=d2, sub=f"Ref: {df_k['data'].iloc[-1].strftime('%b/%Y')}")
            else:
                kpi_card(label, "—", sub="BCB indisponível")

    st.markdown('<div class="sec-title">Histórico — 12 meses <span style="font-size:10px;font-weight:400;color:#9ca3af;text-transform:none;letter-spacing:0;margin-left:4px">→ análise completa em Monitor Inflação</span></div>', unsafe_allow_html=True)

    def _since(df, months):
        if df.empty: return df
        cutoff = df["data"].max() - pd.DateOffset(months=months)
        return df[df["data"] >= cutoff].reset_index(drop=True)

    # Renderiza em grade de 2 colunas, driven por HOME_CHARTS em settings.py
    _chart_pairs = list(zip(HOME_CHARTS[::2], HOME_CHARTS[1::2]))
    for (nome_a, meses_a), (nome_b, meses_b) in _chart_pairs:
        col_a, col_b = st.columns(2)
        for col, nome, meses in [(col_a, nome_a, meses_a), (col_b, nome_b, meses_b)]:
            s = SGS[nome]; cod,unit,freq,tipo,cor = s.codigo,s.unidade,s.frequencia,s.tipo,s.cor
            df = _since(_home_data.get(nome, pd.DataFrame()), meses)
            titulo = f"{nome} ({unit})"
            with col:
                if not df.empty:
                    fig = bar_fig(df, titulo, suffix=f" {unit}") if tipo == "bar" else line_fig(df, titulo, cor, suffix=f" {unit}")
                    render_chart(fig, nome.lower().replace(" ", "_"), static=True)

# ══════════════════════════════════════════════════════════════════════════════
# MONITOR INFLAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Monitor Inflação":
    page_header("Monitor de Inflação")
    try:
        with st.spinner("Carregando indicadores de inflação..."):
            df_ipca_full     = get_bcb_full(433)
            nucleo_data      = {key: (get_bcb_full(n.codigo), n.descricao, n.cor) for key, n in NUCLEO_SGS.items()}
            df_grupos_mensal = get_ipca_grupos(60)
            df_grupos_acum   = get_ipca_acum_grupo(60)
    except Exception as e:
        logger.error("Monitor Inflação: %s", e); st.error("⚠️ Erro ao carregar dados de inflação.")
        if st.button("↺ Tentar novamente"): st.cache_data.clear(); st.rerun()
        st.stop()

    hoje_ano  = datetime.today().year
    meta_bcb  = BCB_META.get(hoje_ano, 3.0)
    teto_meta = meta_bcb + BCB_TOLE
    piso_meta = meta_bcb - BCB_TOLE

    sec_title("IPCA — Inflação ao Consumidor", "↻ diário", "badge-daily")
    ipca_mensal  = df_ipca_full["valor"].iloc[-1]           if not df_ipca_full.empty else None
    ipca_ant     = df_ipca_full["valor"].iloc[-2]           if len(df_ipca_full) >= 2  else None
    ipca_acum12m = df_ipca_full["valor"].tail(12).sum()     if len(df_ipca_full) >= 12 else None
    ref_mes      = df_ipca_full["data"].iloc[-1].strftime("%b/%Y") if not df_ipca_full.empty else ""
    desvio_meta  = (ipca_acum12m - meta_bcb) if ipca_acum12m is not None else None
    var_mensal   = (ipca_mensal - ipca_ant)   if (ipca_mensal is not None and ipca_ant is not None) else None

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("IPCA Mensal", f"{fmt(ipca_mensal)}%" if ipca_mensal is not None else "—", chg_p=var_mensal, raw_delta=var_mensal, sub=f"Ref: {ref_mes}")
    with c2:
        if ipca_acum12m is not None:
            status = "✓ dentro da meta" if piso_meta <= ipca_acum12m <= teto_meta else ("↑ acima do teto" if ipca_acum12m > teto_meta else "↓ abaixo do piso")
            kpi_card("Acum. 12 Meses", f"{fmt(ipca_acum12m)}%", sub=status)
        else: kpi_card("Acum. 12 Meses", "—")
    with c3: kpi_card("Meta BCB", f"{fmt(meta_bcb,1)}%", sub=f"Banda: {fmt(piso_meta,1)}% – {fmt(teto_meta,1)}% (±{BCB_TOLE}pp)")
    with c4:
        if desvio_meta is not None: kpi_card("Desvio da Meta", f"{'+' if desvio_meta>=0 else ''}{fmt(desvio_meta)}pp", chg_p=desvio_meta, raw_delta=desvio_meta, sub=f"Meta contínua {hoje_ano}")
        else: kpi_card("Desvio da Meta", "—")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("Núcleos de Inflação — BCB", "↻ diário", "badge-daily")
    st.markdown("<div style='font-size:11px;color:#6b7280;margin:0 0 14px'>Cinco medidas calculadas pelo BCB: <b>MA-S</b> (4466) · <b>MA</b> (11426) · <b>DP</b> (4467) · <b>EX</b> (11427) · <b>P55</b> (28750)</div>", unsafe_allow_html=True)

    _xmax = df_ipca_full["data"].max() if not df_ipca_full.empty else None
    _xmin = (_xmax - pd.DateOffset(months=24)) if _xmax is not None else None
    fig_cores = cores_overlay_fig(df_ipca_full, nucleo_data, height=H_XLARGE, x_ini=_xmin, x_fim=_xmax)
    render_chart(fig_cores, "ipca_nucleos")

    tab_rows = []
    if not df_ipca_full.empty:
        ul = df_ipca_full.iloc[-1]; an = df_ipca_full.iloc[-2]["valor"] if len(df_ipca_full) >= 2 else None
        tab_rows.append({"Medida":"IPCA (headline)","Cód. SGS":433,"Último valor":f"{fmt(ul['valor'])}%","Ref.":ul["data"].strftime("%b/%Y"),"Var. s/ ant.":f"{'+' if an and ul['valor']>=an else ''}{fmt(ul['valor']-an)}pp" if an else "—"})
    for key, (df_n, label, _) in nucleo_data.items():
        if not df_n.empty:
            ul = df_n.iloc[-1]; an = df_n.iloc[-2]["valor"] if len(df_n) >= 2 else None
            tab_rows.append({"Medida":f"{key} — {label}","Cód. SGS":NUCLEO_SGS[key].codigo,"Último valor":f"{fmt(ul['valor'])}%","Ref.":ul["data"].strftime("%b/%Y"),"Var. s/ ant.":f"{'+' if an and ul['valor']>=an else ''}{fmt(ul['valor']-an)}pp" if an else "—"})
    if tab_rows:
        st.dataframe(pd.DataFrame(tab_rows), hide_index=True, use_container_width=True, height=46+len(tab_rows)*35)
        # Downloads dos núcleos
        _dl_cols = st.columns(len(nucleo_data) + 1)
        with _dl_cols[0]:
            if not df_ipca_full.empty:
                _dlo_ipca = df_ipca_full.copy(); _dlo_ipca["data"] = _dlo_ipca["data"].dt.strftime("%d/%m/%Y")
                st.download_button("💾 IPCA", data=_dlo_ipca.to_csv(index=False).encode("utf-8-sig"), file_name="ipca.csv", mime="text/csv", use_container_width=True)
        for i, (key, (df_n, label, _)) in enumerate(nucleo_data.items()):
            with _dl_cols[i + 1]:
                if not df_n.empty:
                    _dlo_n = df_n.copy(); _dlo_n["data"] = _dlo_n["data"].dt.strftime("%d/%m/%Y")
                    st.download_button(f"💾 {key}", data=_dlo_n.to_csv(index=False).encode("utf-8-sig"), file_name=f"nucleo_{key.lower()}.csv", mime="text/csv", use_container_width=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("Média dos Núcleos — Acumulado 12 Meses", "↻ diário", "badge-daily")
    _series = [df_n.set_index("data")["valor"].rename(key) for key, (df_n, _, _) in nucleo_data.items() if not df_n.empty]
    if _series:
        _df_all = pd.concat(_series, axis=1).sort_index()
        _keys   = [k for k in NUCLEO_SGS if k in _df_all.columns]
        _acols  = [f"{k}_a12" for k in _keys]
        for k in _keys: _df_all[f"{k}_a12"] = _df_all[k].rolling(12).sum()
        _df_all["media_a12"] = _df_all[_acols].mean(axis=1)
        _df_all = _df_all.dropna(subset=["media_a12"]).reset_index()
        _ipca_a12 = pd.DataFrame()
        if not df_ipca_full.empty:
            _tmp = df_ipca_full.copy().sort_values("data").set_index("data")
            _tmp["acum12m"] = _tmp["valor"].rolling(12).sum()
            _ipca_a12 = _tmp.dropna(subset=["acum12m"]).reset_index()
        _xmax_m = _df_all["data"].max(); _xmin_m = _xmax_m - pd.DateOffset(months=24)
        if not _df_all.empty:
            fig_media = nucleos_acum12m_fig(_df_all, nucleo_data, _ipca_a12,
                                            meta_bcb, x_ini=_xmin_m, x_fim=_xmax_m)
            render_chart(fig_media, "nucleos_acum12m")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("Acumulado 12 Meses vs Meta BCB", "↻ diário", "badge-daily")
    if not df_ipca_full.empty:
        _xmax_a = df_ipca_full["data"].max()
        _xmin_a = _xmax_a - pd.DateOffset(months=24)
        fig_acum = acum12m_meta_fig(df_ipca_full, meta_val=meta_bcb, x_ini=_xmin_a, x_fim=_xmax_a)
        render_chart(fig_acum, "ipca_acum12m_meta")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("IPCA por Grupos — IBGE SIDRA", "↻ diário", "badge-daily")
    if df_grupos_mensal.empty:
        st.warning("⚠️ API IBGE/SIDRA temporariamente indisponível.")
    else:
        datas_disp = sorted(df_grupos_mensal["data"].unique())
        dmin_g = datas_disp[0].date(); dmax_g = datas_disp[-1].date()
        _d24g  = datas_disp[-24].date() if len(datas_disp) >= 24 else dmin_g
        st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:0 0 12px'>Disponível: <strong>{dmin_g.strftime('%b/%Y')}</strong> → <strong>{dmax_g.strftime('%b/%Y')}</strong> · {len(datas_disp)} meses · <em>Série completa carregada</em></div>", unsafe_allow_html=True)
        cg1, cg2 = st.columns(2)
        with cg1: g_ini = st.date_input("Exibir de",  value=_d24g,  min_value=dmin_g, max_value=dmax_g, key="g_ini")
        with cg2: g_fim = st.date_input("Exibir até", value=dmax_g, min_value=dmin_g, max_value=dmax_g, key="g_fim")
        ultimo_mes = df_grupos_mensal[df_grupos_mensal["data"] <= pd.Timestamp(g_fim)]["data"].max()
        if pd.isna(ultimo_mes):
            st.warning("Nenhum dado no intervalo selecionado.")
        else:
            st.success(f"✅ Exibindo {g_ini.strftime('%b/%Y')} → {g_fim.strftime('%b/%Y')} · Ref: {ultimo_mes.strftime('%b/%Y')}")
            df_ult = df_grupos_mensal[(df_grupos_mensal["data"]==ultimo_mes) & df_grupos_mensal["grupo_id"].isin(_GRUPO_IDS)].copy().sort_values("valor",ascending=False)

            def _mini_card(grupo, valor):
                cor = "#dc2626" if valor >= 0 else "#16a34a"; sinal = "▲" if valor >= 0 else "▼"
                st.markdown(f"<div style='background:#fff;border:1px solid #e2e5e9;border-radius:10px;padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between'><span style='font-size:12px;font-weight:500;color:#374151'>{grupo}</span><span style='font-size:14px;font-weight:700;color:{cor}'>{sinal} {abs(valor):.2f}%</span></div>", unsafe_allow_html=True)

            ga, gb = st.columns([1.2,1])
            with ga: render_chart(grupos_bar_fig(df_grupos_mensal,ultimo_mes), "ipca_grupos_mensal", static=True)
            with gb:
                st.markdown(f"<div style='font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px'>Maiores altas — {ultimo_mes.strftime('%b/%Y')}</div>", unsafe_allow_html=True)
                for _,row in df_ult.head(3).iterrows(): _mini_card(row["grupo"],row["valor"])
                st.markdown(f"<div style='font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:1.5px;margin:14px 0 8px'>Menores variações — {ultimo_mes.strftime('%b/%Y')}</div>", unsafe_allow_html=True)
                for _,row in df_ult.tail(3).iterrows(): _mini_card(row["grupo"],row["valor"])

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            render_chart(grupos_linhas_fig(df_grupos_mensal,d_ini=g_ini,d_fim=g_fim,height=H_LARGE), "ipca_grupos_evolucao")

            if not df_grupos_acum.empty:
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                sec_title("Acumulado 12 Meses por Grupo — IBGE", "↻ diário", "badge-daily")
                ult_acum  = df_grupos_acum[df_grupos_acum["data"] <= pd.Timestamp(g_fim)]["data"].max()
                df_acum_u = df_grupos_acum[(df_grupos_acum["data"]==ult_acum) & df_grupos_acum["grupo_id"].isin(_GRUPO_IDS)].copy().sort_values("valor",ascending=True)
                if not df_acum_u.empty:
                    render_chart(grupos_acum12m_fig(df_acum_u, ult_acum, meta_bcb), "ipca_grupos_acum12m", static=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            dlo_g = df_grupos_mensal[(df_grupos_mensal["data"]>=pd.Timestamp(g_ini))&(df_grupos_mensal["data"]<=pd.Timestamp(g_fim))].copy()
            dlo_g["data"] = dlo_g["data"].dt.strftime("%Y-%m")
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1: st.download_button(f"💾 Baixar CSV — var. mensal por grupo ({len(dlo_g)} linhas)",data=dlo_g.to_csv(index=False).encode("utf-8-sig"),file_name="ipca_grupos_mensal.csv",mime="text/csv")
            with col_dl2:
                if not df_grupos_acum.empty:
                    dlo_acum = df_grupos_acum[(df_grupos_acum["data"]>=pd.Timestamp(g_ini))&(df_grupos_acum["data"]<=pd.Timestamp(g_fim))].copy()
                    dlo_acum["data"] = dlo_acum["data"].dt.strftime("%Y-%m")
                    st.download_button(f"💾 Baixar CSV — acum. 12M por grupo ({len(dlo_acum)} linhas)",data=dlo_acum.to_csv(index=False).encode("utf-8-sig"),file_name="ipca_grupos_acum12m.csv",mime="text/csv")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    sec_title("Metodologia dos Núcleos de Inflação — BCB", "", "badge-daily")
    st.markdown("""<div style='background:#fff;border:1px solid #e2e5e9;border-radius:12px;padding:20px 24px;font-size:12px;color:#374151;line-height:1.8'>
<p style='margin:0 0 12px'>Os núcleos capturam a <strong>tendência subjacente da inflação</strong>, removendo componentes voláteis. O BCB publica cinco medidas no <em>Relatório de Inflação</em>:</p>
<table style='width:100%;border-collapse:collapse;font-size:11.5px'><thead><tr style='border-bottom:2px solid #e2e5e9'>
<th style='text-align:left;padding:6px 10px;color:#6b7280;font-size:10px;text-transform:uppercase'>Sigla</th>
<th style='text-align:left;padding:6px 10px;color:#6b7280;font-size:10px;text-transform:uppercase'>Nome</th>
<th style='text-align:left;padding:6px 10px;color:#6b7280;font-size:10px;text-transform:uppercase'>SGS</th>
<th style='text-align:left;padding:6px 10px;color:#6b7280;font-size:10px;text-transform:uppercase'>Como é calculado</th>
</tr></thead><tbody>
<tr style='border-bottom:1px solid #f1f5f9'><td style='padding:8px 10px;font-weight:700;color:#0891b2'>MA-S</td><td style='padding:8px 10px'>Médias Aparadas c/ Suavização</td><td style='padding:8px 10px;color:#6b7280'>4466</td><td style='padding:8px 10px'>Apara 20% dos extremos e suaviza monitorados/sazonais ao longo de 12 meses. Mais usada pelo Copom.</td></tr>
<tr style='border-bottom:1px solid #f1f5f9'><td style='padding:8px 10px;font-weight:700;color:#06b6d4'>MA</td><td style='padding:8px 10px'>Médias Aparadas s/ Suavização</td><td style='padding:8px 10px;color:#6b7280'>11426</td><td style='padding:8px 10px'>Igual ao MA-S sem suavização. Mais sensível a choques pontuais.</td></tr>
<tr style='border-bottom:1px solid #f1f5f9'><td style='padding:8px 10px;font-weight:700;color:#16a34a'>DP</td><td style='padding:8px 10px'>Dupla Ponderação</td><td style='padding:8px 10px;color:#6b7280'>4467</td><td style='padding:8px 10px'>Repesa cada item pela inversa da volatilidade histórica. Itens mais voláteis recebem peso menor.</td></tr>
<tr style='border-bottom:1px solid #f1f5f9'><td style='padding:8px 10px;font-weight:700;color:#d97706'>EX</td><td style='padding:8px 10px'>Exclusão</td><td style='padding:8px 10px;color:#6b7280'>11427</td><td style='padding:8px 10px'>Exclui alimentação no domicílio e administrados. Mede a inflação de mercado livre.</td></tr>
<tr><td style='padding:8px 10px;font-weight:700;color:#7c3aed'>P55</td><td style='padding:8px 10px'>Percentil 55</td><td style='padding:8px 10px;color:#6b7280'>28750</td><td style='padding:8px 10px'>Usa o percentil 55 da distribuição ponderada. Robusto a outliers sem regras de exclusão.</td></tr>
</tbody></table>
<p style='margin:14px 0 0;font-size:11px;color:#9ca3af'>Fonte: BCB/SGS. Variação mensal e acumulado 12 meses. Atualização mensal após divulgação do IPCA pelo IBGE.</p>
</div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MERCADOS GLOBAIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Mercados Globais":
    page_header("Mercados Globais")
    st.markdown("""<style>
    .terminal-cat{font-size:9px;font-weight:800;color:#6b7280;text-transform:uppercase;letter-spacing:2.5px;margin:0 0 8px 2px;display:block}
    .tile{border-radius:6px;padding:10px 12px 9px}
    .tile-name{font-size:9px;font-weight:800;color:rgba(255,255,255,.55);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tile-price{font-size:20px;font-weight:700;color:#fff;line-height:1.1;margin-bottom:6px;white-space:nowrap}
    .tile-hl{font-size:9.5px;font-weight:500;display:flex;justify-content:space-between;margin-bottom:2px}
    .tile-chg{font-size:9.5px;font-weight:700;display:flex;justify-content:space-between}
    .up{background:#14522c} .dn{background:#7f1d1d} .neu{background:#1e2535}
    .up .tile-hl,.up .tile-chg{color:#86efac} .dn .tile-hl,.dn .tile-chg{color:#fca5a5} .neu .tile-hl,.neu .tile-chg{color:#94a3b8}
    .tile-closed{font-size:8px;background:rgba(0,0,0,.3);border-radius:3px;padding:1px 5px;color:rgba(255,255,255,.45);margin-left:5px;font-weight:600;vertical-align:middle}
    </style>""", unsafe_allow_html=True)

    def _tfmt(v, unit):
        if v is None: return "—"
        if unit == "pts": return f"{v:,.0f}".replace(",",".") if v >= 10000 else f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        return f"{v:,.{4 if unit=='R$' else 2}f}".replace(",","X").replace(".",",").replace("X",".")

    def _tile(nome, d, unit):
        p=d.get("price"); cp=d.get("chg_p"); cv=d.get("chg_v"); dh=d.get("day_high"); dl=d.get("day_low"); cl=d.get("is_closed",False)
        if p is None: return f"<div class='tile neu'><div class='tile-name'>{nome}</div><div class='tile-price' style='opacity:.4'>—</div></div>"
        cls="up" if (cp or 0)>=0 else "dn"; arr="▲" if (cp or 0)>=0 else "▼"
        px="R$ " if unit=="R$" else ("US$ " if "US$" in unit else "")
        return (f"<div class='tile {cls}'><div class='tile-name'>{nome}{'<span class=\"tile-closed\">FEC</span>' if cl else ''}</div>"
                f"<div class='tile-price'>{px}{_tfmt(p,unit)}</div>"
                f"<div class='tile-hl'><span>H {_tfmt(dh,unit) if dh else '—'}</span><span>{('+' if cv>=0 else '')+_tfmt(cv,unit) if cv is not None else '—'} {arr}</span></div>"
                f"<div class='tile-chg'><span>L {_tfmt(dl,unit) if dl else '—'}</span><span>{('+' if cp>=0 else '')+f'{cp:.2f}%'.replace('.',',') if cp is not None else '—'}</span></div></div>")

    def _group(label, lst):
        st.markdown(f"<span class='terminal-cat'>{label}</span>", unsafe_allow_html=True)
        cols = st.columns(len(lst))
        for col, nome in zip(cols, lst):
            g = GLOBAL[nome]; sym,unit,cor = g.simbolo,g.unidade,g.cor
            with col: st.markdown(_tile(nome, get_quote(sym), unit), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Fragment: tiles atualizam a cada 15min (cache do servidor) ───────────
    @st.fragment(run_every=900)
    def _cotacoes():
        try:
            _group("Índices", ["IBOVESPA","S&P 500","Nasdaq 100","Dow Jones","FTSE 100","DAX"])
            c_en, c_me = st.columns([2,3])
            with c_en: _group("Energia", ["Petróleo Brent","Petróleo WTI"])
            with c_me: _group("Metais",  ["Ouro","Prata","Cobre"])
            c_fx, c_cr = st.columns([2,2])
            with c_fx: _group("Câmbio", ["Dólar (USD/BRL)","Euro (EUR/BRL)"])
            with c_cr: _group("Cripto", ["Bitcoin","Ethereum"])
            st.markdown(f"<div style='text-align:right;font-size:10px;color:#6b7280;margin-top:4px'>Atualizado: {now_brt().strftime('%d/%m/%Y %H:%M:%S')} BRT &nbsp;·&nbsp; ↻ 15min</div>", unsafe_allow_html=True)
        except Exception as e:
            logger.error("Mercados: %s", e)
            st.error("⚠️ Erro ao carregar cotações.")
            if st.button("↺ Tentar novamente"): st.cache_data.clear(); st.rerun()

    _cotacoes()

    # ── Gráficos históricos — fora do fragment, não piscam ───────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    sec_title("Histórico Interativo", "2 anos", "badge-daily")
    _hist_tabs = {nome: GLOBAL[nome] for nome in MERCADOS_HIST}
    for tab, (nome_h, (sym_h, unit_h, _, cor_h)) in zip(st.tabs(list(_hist_tabs.keys())), _hist_tabs.items()):
        with tab:
            dfh = get_hist(sym_h, 2)
            if not dfh.empty:
                _xmax_h = dfh["data"].max()
                _xmin_h = _xmax_h - pd.DateOffset(years=2)
                fig_h = line_fig(dfh, f"{nome_h} — 2 anos", cor_h, suffix=f" {unit_h}", height=H_MEDIUM, inter=True, x_ini=_xmin_h, x_fim=_xmax_h)
                render_chart(fig_h, nome_h)

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Gráficos":
    page_header("Gráficos")
    t1, t2, t3 = st.tabs(["BCB — Indicadores Brasil", "Yahoo Finance — Ativos Globais", "Comparar Séries"])
    with t1:
        col1,col2 = st.columns([2,2])
        with col1: ind = st.selectbox("Indicador", list(SGS.keys()), key="gind",
            help=SGS_DESCRICAO.get(st.session_state.get("gind", list(SGS.keys())[0]), ""))
        opts = SGS_PERIODOS.get(ind, [P_ORIGINAL])
        with col2: periodo = st.selectbox("Período / Transformação",opts,key="gperiodo") if len(opts)>1 else opts[0]
        s = SGS[ind]; cod,unit,freq,tipo,cor = s.codigo,s.unidade,s.frequencia,s.tipo,s.cor
        try:
            with st.spinner(f"Carregando {ind}..."): df_f = get_bcb_full(cod)
        except Exception as e:
            logger.error("Gráficos BCB: %s", e); df_f = pd.DataFrame(columns=["data","valor"])
        if df_f.empty:
            col_e,col_b = st.columns([6,1])
            with col_e: st.warning(f"⚠️ Série {ind} indisponível.")
            with col_b:
                if st.button("↺",key="retry_bcb"): st.cache_data.clear(); st.rerun()
        else:
            df_t,unit_t = aplicar_periodo(df_f,periodo,ind)
            if not unit_t: unit_t = unit
            label_t = f"{ind} — {periodo}" if periodo not in PERIODOS_ORIGINAIS else f"{ind} ({unit_t})"
            dmin = df_t["data"].min().date(); dmax = df_t["data"].max().date()
            st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px'>Disponível: <strong>{dmin.strftime('%d/%m/%Y')}</strong> → <strong>{dmax.strftime('%d/%m/%Y')}</strong> · {len(df_t)} obs.</div>",unsafe_allow_html=True)
            _d24 = max(dmin,date(dmax.year-2,dmax.month,dmax.day))
            c2,c3 = st.columns(2)
            with c2: d_ini = st.date_input("Exibir de",value=_d24,min_value=dmin,max_value=dmax,key="gini")
            with c3: d_fim = st.date_input("Exibir até",value=dmax,min_value=dmin,max_value=dmax,key="gfim")
            if d_ini < d_fim:
                st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:4px 0 8px'>{len(df_t)} obs. · {label_t} · {freq}</div>", unsafe_allow_html=True)
                use_bar = (tipo=="bar") and (periodo in PERIODOS_ORIGINAIS)
                fig = bar_fig(df_t, label_t, suffix=f" {unit_t}", height=H_LARGE, inter=True, x_ini=d_ini, x_fim=d_fim) if use_bar \
                    else line_fig(df_t, label_t, cor, suffix=f" {unit_t}", height=H_LARGE, inter=True, x_ini=d_ini, x_fim=d_fim)
                render_chart(fig, f"{ind}_{periodo}")
                # ── Tabela de estatísticas ────────────────────────────────────
                _dv = df_t[(df_t["data"] >= pd.Timestamp(d_ini)) & (df_t["data"] <= pd.Timestamp(d_fim))]["valor"].dropna()
                if not _dv.empty:
                    _sc1,_sc2,_sc3,_sc4,_sc5 = st.columns(5)
                    for _col, _lbl, _val in zip(
                        [_sc1,_sc2,_sc3,_sc4,_sc5],
                        ["Último","Média","Mín","Máx","Desvio padrão"],
                        [_dv.iloc[-1], _dv.mean(), _dv.min(), _dv.max(), _dv.std()]
                    ):
                        _col.metric(_lbl, f"{_val:,.2f}".replace(",",".").replace(".",",",1) if _val == _val else "—")
                dlo = df_t.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                st.download_button(f"💾 Baixar CSV ({len(dlo)} linhas)",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=f"{ind.replace(' ','_')}_{periodo.replace(' ','_')}.csv",mime="text/csv")
    with t2:
        co1,_ = st.columns([2,3])
        with co1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="gativo",
            help=GLOBAL_DESCRICAO.get(st.session_state.get("gativo", list(GLOBAL.keys())[0]), ""))
        g = GLOBAL[ativo]; sym,unit,cor = g.simbolo,g.unidade,g.cor
        try:
            with st.spinner(f"Carregando {ativo}..."): dfg = get_hist(sym,years=10)
        except Exception as e:
            logger.error("Gráficos Yahoo: %s", e); dfg = pd.DataFrame(columns=["data","valor"])
        if not dfg.empty:
            dmin_y=dfg["data"].min().date(); dmax_y=dfg["data"].max().date()
            _d24y = max(dmin_y,date(dmax_y.year-2,dmax_y.month,dmax_y.day))
            st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px'>Disponível: <strong>{dmin_y.strftime('%d/%m/%Y')}</strong> → <strong>{dmax_y.strftime('%d/%m/%Y')}</strong> · {len(dfg)} obs.</div>",unsafe_allow_html=True)
            cy1,cy2 = st.columns(2)
            with cy1: dy_ini = st.date_input("Exibir de",value=_d24y,min_value=dmin_y,max_value=dmax_y,key="gyini")
            with cy2: dy_fim = st.date_input("Exibir até",value=dmax_y,min_value=dmin_y,max_value=dmax_y,key="gyfim")
            if dy_ini < dy_fim:
                st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:4px 0 8px'>{len(dfg)} obs. · {ativo}</div>", unsafe_allow_html=True)
                fig_y = line_fig(dfg, f"{ativo}", cor, suffix=f" {unit}", height=H_LARGE, inter=True, x_ini=dy_ini, x_fim=dy_fim)
                render_chart(fig_y, ativo)
                # ── Tabela de estatísticas ────────────────────────────────────
                _dvy = dfg[(dfg["data"] >= pd.Timestamp(dy_ini)) & (dfg["data"] <= pd.Timestamp(dy_fim))]["valor"].dropna()
                if not _dvy.empty:
                    _yc1,_yc2,_yc3,_yc4,_yc5 = st.columns(5)
                    for _col, _lbl, _val in zip(
                        [_yc1,_yc2,_yc3,_yc4,_yc5],
                        ["Último","Média","Mín","Máx","Desvio padrão"],
                        [_dvy.iloc[-1], _dvy.mean(), _dvy.min(), _dvy.max(), _dvy.std()]
                    ):
                        _col.metric(_lbl, f"{_val:,.2f}".replace(",",".").replace(".",",",1) if _val == _val else "—")
                dlo = dfg.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                st.download_button(f"💾 Baixar CSV completo ({len(dlo)} linhas)",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=f"{ativo.replace(' ','_')}_completo.csv",mime="text/csv")
        else:
            col_e,col_b = st.columns([6,1])
            with col_e: st.warning(f"⚠️ Histórico de {ativo} indisponível.")
            with col_b:
                if st.button("↺",key="retry_yf"): st.cache_data.clear(); st.rerun()

    # ── Aba Comparar Séries ───────────────────────────────────────────────────
    with t3:
        # cores from settings.py
        st.markdown("<div style='font-size:12px;color:#6b7280;margin:0 0 14px'>Selecione 2 ou 3 indicadores BCB para comparar no mesmo gráfico. Séries com unidades diferentes usam eixo Y duplo.</div>", unsafe_allow_html=True)

        _ind_lista = list(SGS.keys())
        cc1, cc2, cc3 = st.columns(3)
        with cc1: cind1 = st.selectbox("Indicador 1", _ind_lista, index=0, key="cind1")
        with cc2: cind2 = st.selectbox("Indicador 2", _ind_lista, index=1, key="cind2")
        with cc3: cind3 = st.selectbox("Indicador 3 (opcional)", ["—"] + _ind_lista, index=0, key="cind3")

        _selecionados = [cind1, cind2] + ([cind3] if cind3 != "—" else [])

        # Carrega séries
        _series_comp = {}
        for _nome in _selecionados:
            s = SGS[_nome]; _cod,_unit,_freq = s.codigo,s.unidade,s.frequencia
            try:
                with st.spinner(f"Carregando {_nome}..."): _df_c = get_bcb_full(_cod)
            except Exception as e:
                logger.error("Comparação: %s — %s", _cod, e); _df_c = pd.DataFrame(columns=["data","valor"])
            stale_banner(_df_c, _nome)
            _series_comp[_nome] = (_df_c, _unit)

        # Janela de datas — baseada na menor série disponível
        _dfs_validas = [df for df, _ in _series_comp.values() if not df.empty]
        if len(_dfs_validas) < 2:
            st.warning("⚠️ Não foi possível carregar dados suficientes para comparar.")
        else:
            _dmin_c = max(df["data"].min() for df in _dfs_validas).date()
            _dmax_c = min(df["data"].max() for df in _dfs_validas).date()
            _d24c   = max(_dmin_c, date(_dmax_c.year - 2, _dmax_c.month, _dmax_c.day))
            cd1, cd2 = st.columns(2)
            with cd1: dc_ini = st.date_input("Exibir de",  value=_d24c,  min_value=_dmin_c, max_value=_dmax_c, key="cini")
            with cd2: dc_fim = st.date_input("Exibir até", value=_dmax_c, min_value=_dmin_c, max_value=_dmax_c, key="cfim")

            if dc_ini < dc_fim:
                fig_comp = comparacao_fig(_series_comp, _selecionados,
                                          x_ini=dc_ini, x_fim=dc_fim)
                render_chart(fig_comp, "comparacao_series")

                # Download combinado
                _dfs_merged = []
                for _nome, (_df_c, _unit) in _series_comp.items():
                    if not _df_c.empty:
                        _tmp = _df_c[(_df_c["data"] >= pd.Timestamp(dc_ini)) & (_df_c["data"] <= pd.Timestamp(dc_fim))].copy()
                        _tmp = _tmp.rename(columns={"valor": f"{_nome} ({_unit})"})
                        _dfs_merged.append(_tmp.set_index("data"))
                if _dfs_merged:
                    _df_export = pd.concat(_dfs_merged, axis=1).reset_index()
                    _df_export["data"] = _df_export["data"].dt.strftime("%d/%m/%Y")
                    st.download_button("💾 Baixar CSV comparação",
                        data=_df_export.to_csv(index=False).encode("utf-8-sig"),
                        file_name="comparacao_series.csv", mime="text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# EXPECTATIVAS DE MERCADO (Boletim Focus)
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Expectativas":
    page_header("Expectativas de Mercado")
    st.markdown(
        "<div style='font-size:12px;color:#6b7280;margin:0 0 18px'>"
        "Medianas do <b>Boletim Focus</b> — pesquisa semanal do BCB com ~130 instituições financeiras. "
        "Atualizado toda segunda-feira."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Seleção de indicador e prazo ─────────────────────────────────────────
    fe1, fe2 = st.columns([2, 2])
    with fe1:
        ind_focus = st.selectbox(
            "Indicador", FOCUS_INDICADORES, key="find",
            help="Indicador econômico monitorado pelas instituições do Focus"
        )
    with fe2:
        _suporta_12m = ind_focus in {"IPCA", "IPCA-15", "IGP-M", "IGP-DI", "IPC-Fipe"}
        _opcoes_prazo = ["Próximos 12 meses", "Expectativas anuais"] if _suporta_12m else ["Ano corrente (proxy)", "Expectativas anuais"]
        prazo_focus = st.selectbox(
            "Prazo", _opcoes_prazo, key="fprazo",
            help="'Próximos 12 meses' disponível apenas para indicadores de inflação"
        )

    # ── Busca e exibe ─────────────────────────────────────────────────────────
    with st.spinner(f"Carregando Focus — {ind_focus}..."):
        if prazo_focus == "Próximos 12 meses":
            df_focus = get_focus_12m(ind_focus, anos=3)
        else:
            df_focus = get_focus_anual(ind_focus, anos=5)

    if df_focus.empty:
        st.warning("⚠️ Dados do Boletim Focus indisponíveis para este indicador.")
    else:
        # KPIs — última leitura
        _ult  = df_focus.iloc[-1]
        _ant  = df_focus.iloc[-2] if len(df_focus) >= 2 else _ult
        _delta = float(_ult["mediana"] - _ant["mediana"])
        _ref   = f"Ref: {_ult['data'].strftime('%d/%m/%Y')}"
        kc1, kc2, kc3, kc4 = st.columns(4)
        with kc1: kpi_card("Mediana (última)", f"{fmt(_ult['mediana'])}%", chg_p=_delta*100/_ant['mediana'] if _ant['mediana'] else None, sub=_ref)
        with kc2: kpi_card("Mínimo (última)",  f"{fmt(_ult['minimo'])}%"  if pd.notna(_ult.get('minimo')) else "—", sub=_ref)
        with kc3: kpi_card("Máximo (última)",  f"{fmt(_ult['maximo'])}%"  if pd.notna(_ult.get('maximo')) else "—", sub=_ref)
        with kc4: kpi_card("Desvio padrão",    f"{fmt(_ult['desvio'])}%"  if pd.notna(_ult.get('desvio')) else "—", sub="Dispersão das expectativas")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Gráfico da mediana ao longo do tempo
        _df_plot = df_focus[["data","mediana"]].rename(columns={"mediana":"valor"})
        _xmax_f = _df_plot["data"].max()
        _xmin_f = _xmax_f - pd.DateOffset(years=2)
        _titulo = f"Focus — {ind_focus} ({prazo_focus})"
        fig_focus = line_fig(_df_plot, _titulo, "#1a2035", suffix="%", height=H_LARGE, inter=True, x_ini=_xmin_f, x_fim=_xmax_f)
        render_chart(fig_focus, f"focus_{ind_focus.lower().replace(' ','_')}")

        # Tabela de expectativas anuais (só para modo anual)
        if prazo_focus == "Expectativas anuais":
            _anos_disp = sorted(df_focus["ano_ref"].unique(), reverse=True)
            sec_title("Expectativas por Ano de Referência")
            _pivot = []
            for _ano in _anos_disp[:5]:  # últimos 5 anos
                _df_ano = df_focus[df_focus["ano_ref"] == _ano].sort_values("data")
                if not _df_ano.empty:
                    _last = _df_ano.iloc[-1]
                    _pivot.append({
                        "Ano": _ano,
                        "Mediana": f"{fmt(_last['mediana'])}%",
                        "Mínimo":  f"{fmt(_last['minimo'])}%"  if pd.notna(_last.get('minimo'))  else "—",
                        "Máximo":  f"{fmt(_last['maximo'])}%"  if pd.notna(_last.get('maximo'))  else "—",
                        "Desvio":  f"{fmt(_last['desvio'])}%"  if pd.notna(_last.get('desvio'))  else "—",
                        "Ref. data": _last["data"].strftime("%d/%m/%Y"),
                    })
            if _pivot:
                st.dataframe(pd.DataFrame(_pivot), hide_index=True, use_container_width=True)

        # Download
        _dlo_f = df_focus.copy()
        _dlo_f["data"] = _dlo_f["data"].dt.strftime("%d/%m/%Y")
        st.download_button(
            f"💾 Baixar CSV ({len(_dlo_f)} linhas)",
            data=_dlo_f.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"focus_{ind_focus.replace(' ','_').replace('/','-')}_{prazo_focus[:5]}.csv",
            mime="text/csv",
        )

# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ══════════════════════════════════════════════════════════════════════════════
else:
    page_header("Exportar Dados")
    fonte = st.radio("Fonte:",["BCB/SGS — Brasil","Yahoo Finance — Globais"],horizontal=True)
    st.markdown("<div style='height:10px'></div>",unsafe_allow_html=True)
    if fonte == "BCB/SGS — Brasil":
        c1,c2 = st.columns([2,2])
        with c1: ind = st.selectbox("Indicador",list(SGS.keys()),index=1,key="eind")
        opts_e = SGS_PERIODOS.get(ind, [P_ORIGINAL])
        with c2: periodo_e = st.selectbox("Período / Transformação",opts_e,key="eperiodo") if len(opts_e)>1 else opts_e[0]
        c3,c4 = st.columns(2)
        with c3: d_ini = st.date_input("De",value=datetime.today()-timedelta(days=365*5),key="eini")
        with c4: d_fim = st.date_input("Até",value=datetime.today(),key="efim")
        modo = st.radio("Dados:",["Filtrar pelo intervalo acima","Série completa desde o início"],horizontal=True,key="emodo")
        if st.button("Gerar CSV",type="primary",key="ebtn"):
            s = SGS[ind]; cod,unit,freq = s.codigo,s.unidade,s.frequencia
            try:
                with st.spinner(f"Carregando {ind}..."):
                    # Sempre busca série completa — filtra em memória se necessário
                    dfe = get_bcb_full(cod)
                    if "completa" not in modo and not dfe.empty:
                        dfe = dfe[(dfe["data"] >= pd.Timestamp(d_ini)) &
                                  (dfe["data"] <= pd.Timestamp(d_fim))].reset_index(drop=True)
            except Exception as e:
                logger.error("Exportar BCB: %s",e); dfe = pd.DataFrame(columns=["data","valor"])
            if dfe.empty:
                col_e,col_b=st.columns([6,1])
                with col_e: st.warning(f"⚠️ Nenhum dado para {ind}.")
                with col_b:
                    if st.button("↺",key="retry_exp_bcb"): st.cache_data.clear(); st.rerun()
            else:
                dfe2,unit_t = aplicar_periodo(dfe,periodo_e,ind)
                if not unit_t: unit_t = unit
                if dfe2.empty: st.warning("Transformação resultou em série vazia.")
                else:
                    label_e = f"{ind} — {periodo_e}" if periodo_e not in PERIODOS_ORIGINAIS else ind
                    dlo = dfe2.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                    st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:4px 0 8px'>{len(dlo)} registros exportados</div>", unsafe_allow_html=True)
                    st.dataframe(dlo.rename(columns={"data":"Data","valor":f"Valor ({unit_t})"}),use_container_width=True,height=min(400,46+len(dlo)*35))
                    nome = f"{ind.replace(' ','_')}_{periodo_e.replace(' ','_').replace('/','')}.csv"
                    st.download_button(f"💾 Baixar {nome}",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=nome,mime="text/csv")
    else:
        co1,co2 = st.columns([2,1])
        with co1: ativo = st.selectbox("Ativo",list(GLOBAL.keys()),key="eativo")
        with co2: anos = st.select_slider("Período (anos)",[1,2,3,5,10],value=5,key="eanos")
        if st.button("Gerar CSV",type="primary",key="ebtn2"):
            g = GLOBAL[ativo]; sym,unit,cor = g.simbolo,g.unidade,g.cor
            try:
                with st.spinner(f"Buscando {ativo}..."): dfe = get_hist(sym,anos)
            except Exception as e:
                logger.error("Exportar Yahoo: %s",e); dfe = pd.DataFrame(columns=["data","valor"])
            if dfe.empty:
                col_e,col_b=st.columns([6,1])
                with col_e: st.warning(f"⚠️ Histórico de {ativo} indisponível.")
                with col_b:
                    if st.button("↺",key="retry_exp_yf"): st.cache_data.clear(); st.rerun()
            else:
                dlo = dfe.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:4px 0 8px'>{len(dlo)} registros exportados</div>", unsafe_allow_html=True)
                st.dataframe(dlo.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),use_container_width=True,height=min(400,46+len(dlo)*35))
                nome = f"{ativo.replace(' ','_')}_{anos}anos.csv"
                st.download_button(f"💾 Baixar {nome}",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=nome,mime="text/csv")

    st.markdown("<div style='height:24px'></div>",unsafe_allow_html=True)
    lbl = "▲  Ocultar indicadores e ativos" if st.session_state.tabela_aberta else "▼  Ver todos os indicadores e ativos disponíveis"
    if st.button(lbl,key="btn_tabela",use_container_width=False): st.session_state.tabela_aberta = not st.session_state.tabela_aberta; st.rerun()
    if st.session_state.tabela_aberta:
        st.markdown("<div style='background:#fff;border:1px solid #e2e5e9;border-radius:12px;padding:20px 24px;margin-top:4px'>",unsafe_allow_html=True)
        st.markdown("**BCB/SGS — Indicadores Brasil**")
        df_sgs = pd.DataFrame([{"Indicador":k,"Cód. SGS":v.codigo,"Unidade":v.unidade,"Freq.":v.frequencia,"Transformações":", ".join(SGS_PERIODOS.get(k,[P_ORIGINAL]))} for k,v in SGS.items()])
        st.dataframe(df_sgs,hide_index=True,use_container_width=True,height=46+len(df_sgs)*35)
        st.markdown("<div style='height:16px'></div>",unsafe_allow_html=True)
        st.markdown("**Yahoo Finance — Ativos Globais**")
        df_yf = pd.DataFrame([{
            "Ativo":   k,
            "Símbolo": v.simbolo,
            "Unidade": v.unidade,
            "Tipo":    ("Câmbio"    if k in ("Dólar (USD/BRL)", "Euro (EUR/BRL)") else
                        "Índice"    if k in ("IBOVESPA", "S&P 500", "Nasdaq 100", "Dow Jones", "FTSE 100", "DAX") else
                        "Commodity" if k in ("Petróleo Brent", "Petróleo WTI", "Ouro", "Prata", "Cobre") else
                        "Cripto"),
        } for k, v in GLOBAL.items()])
        st.dataframe(df_yf,hide_index=True,use_container_width=True,height=46+len(df_yf)*35)
        st.markdown("</div>",unsafe_allow_html=True)
