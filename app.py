"""
EQI Dashboard Macro — arquivo único, sem dependências locais
"""
import sys, os, warnings, time
import requests, urllib3
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS")

st.set_page_config(page_title="EQI Dashboard Macro", page_icon="🇧🇷",
                   layout="wide", initial_sidebar_state="expanded",
                   menu_items={})

TZ_BRT = ZoneInfo("America/Sao_Paulo")
def now_brt(): return datetime.now(TZ_BRT)

# ── Constantes ────────────────────────────────────────────────────────────────
BCB_BASE      = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{c}/dados"
YAHOO_SNAP    = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range=5d"
YAHOO_HIST    = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range={y}y"
IBGE_SIDRA    = "https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos/{periodos}/variaveis/{var}?localidades=N1[all]&classificacao={cls}"
HDRS          = {"User-Agent":"Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36","Accept":"application/json"}
CHART_CFG     = {"displayModeBar": False, "scrollZoom": False, "staticPlot": False, "responsive": True}
CHART_CFG_INT = {"displayModeBar": True, "scrollZoom": True,
                 "modeBarButtonsToRemove": ["select2d","lasso2d","autoScale2d","resetScale2d"],
                 "modeBarButtonsToAdd": ["zoomIn2d","zoomOut2d"],
                 "displaylogo": False,
                 "toImageButtonOptions": {"format":"png","scale":2}}

SGS = {
    "Selic":       (432,   "% a.a.",  "Mensal",     "line"),
    "IPCA":        (433,   "% mês",   "Mensal",     "bar"),
    "IBC-Br":      (24363, "índice",  "Mensal",     "line"),
    "Dólar PTAX":  (1,     "R$",      "Diário",     "line"),
    "PIB":         (4380,  "% trim.", "Trimestral", "bar"),
    "Desemprego":  (24369, "%",       "Trimestral", "line"),
    "IGP-M":       (189,   "% mês",   "Mensal",     "bar"),
    "IPCA-15":     (7478,  "% mês",   "Mensal",     "bar"),
    "Exportações": (2257,  "US$ mi",  "Mensal",     "bar"),
    "Importações": (2258,  "US$ mi",  "Mensal",     "bar"),
    "Dívida/PIB":  (4513,  "%",       "Mensal",     "line"),
}
GLOBAL = {
    "IBOVESPA":        ("^BVSP",    "pts",    False),
    "Dólar (USD/BRL)": ("USDBRL=X", "R$",     True),
    "Euro (EUR/BRL)":  ("EURBRL=X", "R$",     True),
    "S&P 500":         ("^GSPC",    "pts",    False),
    "Nasdaq 100":      ("^NDX",     "pts",    False),
    "Dow Jones":       ("^DJI",     "pts",    False),
    "FTSE 100":        ("^FTSE",    "pts",    False),
    "DAX":             ("^GDAXI",   "pts",    False),
    "Petróleo Brent":  ("BZ=F",     "US$",    True),
    "Petróleo WTI":    ("CL=F",     "US$",    True),
    "Ouro":            ("GC=F",     "US$",    False),
    "Prata":           ("SI=F",     "US$",    False),
    "Cobre":           ("HG=F",     "US$/lb", True),
    "Bitcoin":         ("BTC-USD",  "US$",    False),
    "Ethereum":        ("ETH-USD",  "US$",    False),
}

# ── Núcleos de Inflação BCB (SGS) ─────────────────────────────────────────────
# Metodologias oficiais publicadas pelo BCB no Relatório de Inflação
NUCLEO_SGS = {
    "MA-S":  (4466,  "Médias Aparadas c/ Suavização",   "#0891b2"),
    "MA":    (11426, "Médias Aparadas s/ Suavização",   "#06b6d4"),
    "DP":    (4467,  "Dupla Ponderação",                "#16a34a"),
    "EX":    (11427, "Exclusão",                        "#d97706"),
    "P55":   (28750, "Percentil 55",                    "#7c3aed"),
}

# ── Metas BCB ─────────────────────────────────────────────────────────────────
BCB_META  = {2020:4.0, 2021:3.75, 2022:3.5, 2023:3.25, 2024:3.0, 2025:3.0, 2026:3.0}
BCB_TOLE  = 1.5   # ± 1,5 pp

# ── Grupos IPCA (IBGE SIDRA) ──────────────────────────────────────────────────
# IDs da classificação 315, tabela 7060 — 9 grupos principais + índice geral
IPCA_GRUPOS_IDS = "7169,7170,7445,7486,7625,7626,7627,7628,7629,7630"

# Mapeamento ID → nome padronizado (fonte: IBGE SIDRA)
IPCA_ID_NOME = {
    "7169": "Índice Geral",
    "7170": "Alimentação e bebidas",
    "7445": "Habitação",
    "7486": "Artigos de residência",
    "7625": "Vestuário",
    "7626": "Transportes",
    "7627": "Saúde e cuidados pessoais",
    "7628": "Despesas pessoais",
    "7629": "Educação",
    "7630": "Comunicação",
}

IPCA_GRUPOS_CORES = {
    "Alimentação e bebidas":       "#d97706",
    "Habitação":                   "#0891b2",
    "Artigos de residência":       "#64748b",
    "Vestuário":                   "#ec4899",
    "Transportes":                 "#7c3aed",
    "Saúde e cuidados pessoais":   "#16a34a",
    "Despesas pessoais":           "#f59e0b",
    "Educação":                    "#dc2626",
    "Comunicação":                 "#0ea5e9",
}

NAV = ["Início", "Monitor Inflação", "Mercados Globais", "Gráficos", "Exportar"]

# ── Session state ─────────────────────────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state.pagina = "Início"
if "tabela_aberta" not in st.session_state:
    st.session_state.tabela_aberta = False
if "mercados_ativo" not in st.session_state:
    st.session_state.mercados_ativo = "IBOVESPA"

# Sync query param → session state (tile click sets ?mv=NomeAtivo)
_qp = st.query_params.get("mv", None)
if _qp and _qp in GLOBAL:
    st.session_state.mercados_ativo = _qp

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*,[class*="css"]{font-family:'Inter',sans-serif!important}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f0f2f5!important}
.main .block-container{padding-top:0!important;padding-bottom:2rem;max-width:1400px}
footer,#MainMenu,header{visibility:hidden!important}
[data-testid="stToolbar"]{display:none!important}
[data-testid="stCaptionContainer"] p{font-size:10px!important;color:#9ca3af!important;text-align:center!important;margin:0!important}
.page-top{background:#fff;border-bottom:1px solid #e8eaed;padding:15px 28px;margin:0 -3rem 22px -3rem;display:flex;align-items:center;justify-content:space-between}
.page-top h1{font-size:16px;font-weight:600;color:#111827;margin:0}
.page-top .ts{font-size:11px;color:#6b7280;text-align:right;line-height:1.5}
.sec-title{font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin:20px 0 12px;padding-bottom:8px;border-bottom:1px solid #e2e5e9;display:flex;align-items:center;gap:8px}
.badge-live{display:inline-block;background:#f0fdf4;border:1px solid #bbf7d0;color:#16a34a;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px}
.badge-daily{display:inline-block;background:#f5f3ff;border:1px solid #ddd6fe;color:#7c3aed;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px}
.main .stButton>button{background:#1a2035!important;color:#fff!important;border:none!important;border-radius:7px!important;font-weight:600!important;font-size:13px!important;padding:8px 18px!important}
.main .stButton>button:hover{background:#2d3a56!important}
section[data-testid="stSidebar"]{min-width:260px!important;max-width:260px!important;width:260px!important}
[data-testid="stSidebarResizer"]{display:none!important}
[data-testid="stSidebarCollapseButton"]{display:none!important}
[data-testid="stSidebarCollapsedControl"]{display:none!important}
section[data-testid="stSidebar"] .stButton button{text-align:left!important;padding:8px 14px 8px 38px!important;min-height:0!important;height:36px!important;line-height:1.2!important;font-size:13px!important;font-weight:500!important;border-radius:8px!important;position:relative!important}
section[data-testid="stSidebar"] .stButton button::before{content:""!important;position:absolute!important;left:12px!important;top:50%!important;transform:translateY(-50%)!important;width:16px!important;height:16px!important;background-repeat:no-repeat!important;background-size:16px 16px!important;background-position:center!important}
section[data-testid="stSidebar"] .stButton button[kind="primary"]{background:#004031!important}
section[data-testid="stSidebar"] .stButton button[kind="primary"]:hover{background:#005a45!important}
.nav-marker{display:none!important;height:0!important;margin:0!important;padding:0!important}
div:has(.nav-inicio) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0zIDkuNUwxMiAzbDkgNi41VjIwYTEgMSAwIDAgMS0xIDFINGExIDEgMCAwIDEtMS0xVjkuNXoiLz48cGF0aCBkPSJNOSAyMVYxMmg2djkiLz48L3N2Zz4=")!important}
div:has(.nav-inicio) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0zIDkuNUwxMiAzbDkgNi41VjIwYTEgMSAwIDAgMS0xIDFINGExIDEgMCAwIDEtMS0xVjkuNXoiLz48cGF0aCBkPSJNOSAyMVYxMmg2djkiLz48L3N2Zz4=")!important}
div:has(.nav-ipca) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSIxOSIgeTE9IjUiIHgyPSI1IiB5Mj0iMTkiLz48Y2lyY2xlIGN4PSI2LjUiIGN5PSI2LjUiIHI9IjIuNSIvPjxjaXJjbGUgY3g9IjE3LjUiIGN5PSIxNy41IiByPSIyLjUiLz48L3N2Zz4=")!important}
div:has(.nav-ipca) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSIxOSIgeTE9IjUiIHgyPSI1IiB5Mj0iMTkiLz48Y2lyY2xlIGN4PSI2LjUiIGN5PSI2LjUiIHI9IjIuNSIvPjxjaXJjbGUgY3g9IjE3LjUiIGN5PSIxNy41IiByPSIyLjUiLz48L3N2Zz4=")!important}
div:has(.nav-mercados) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIyIDcgMTMuNSAxNS41IDguNSAxMC41IDIgMTciLz48cG9seWxpbmUgcG9pbnRzPSIxNiA3IDIyIDcgMjIgMTMiLz48L3N2Zz4=")!important}
div:has(.nav-mercados) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIyIDcgMTMuNSAxNS41IDguNSAxMC41IDIgMTciLz48cG9seWxpbmUgcG9pbnRzPSIxNiA3IDIyIDcgMjIgMTMiLz48L3N2Zz4=")!important}
div:has(.nav-graficos) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjEyIiB3aWR0aD0iNCIgaGVpZ2h0PSI5Ii8+PHJlY3QgeD0iMTAiIHk9IjciIHdpZHRoPSI0IiBoZWlnaHQ9IjE0Ii8+PHJlY3QgeD0iMTciIHk9IjMiIHdpZHRoPSI0IiBoZWlnaHQ9IjE4Ii8+PC9zdmc+")!important}
div:has(.nav-graficos) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjEyIiB3aWR0aD0iNCIgaGVpZ2h0PSI5Ii8+PHJlY3QgeD0iMTAiIHk9IjciIHdpZHRoPSI0IiBoZWlnaHQ9IjE0Ii8+PHJlY3QgeD0iMTciIHk9IjMiIHdpZHRoPSI0IiBoZWlnaHQ9IjE4Ii8+PC9zdmc+")!important}
div:has(.nav-exportar) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMSAxNXY0YTIgMiAwIDAgMS0yIDJINWEyIDIgMCAwIDEtMi0ydi00Ii8+PHBvbHlsaW5lIHBvaW50cz0iNyAxMCAxMiAxNSAxNyAxMCIvPjxsaW5lIHgxPSIxMiIgeTE9IjE1IiB4Mj0iMTIiIHkyPSIzIi8+PC9zdmc+")!important}
div:has(.nav-exportar) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMSAxNXY0YTIgMiAwIDAgMS0yIDJINWEyIDIgMCAwIDEtMi0ydi00Ii8+PHBvbHlsaW5lIHBvaW50cz0iNyAxMCAxMiAxNSAxNyAxMCIvPjxsaW5lIHgxPSIxMiIgeTE9IjE1IiB4Mj0iMTIiIHkyPSIzIi8+PC9zdmc+")!important}
""", unsafe_allow_html=True)

# ── Helpers UI ────────────────────────────────────────────────────────────────
def fmt(v, dec=2):
    if v is None: return "—"
    s = f"{v:,.{dec}f}".split(".")
    return f"{s[0].replace(',','.')},{s[1]}" if len(s)>1 else s[0].replace(",",".")

def hex_rgba(h, a=0.08):
    h=h.lstrip("#"); return f"rgba({int(h[:2],16)},{int(h[2:4],16)},{int(h[4:],16)},{a})"

def sec_title(txt, badge="", cls="badge-live"):
    b = f'<span class="{cls}">{badge}</span>' if badge else ""
    st.markdown(f'<div class="sec-title">{txt} {b}</div>', unsafe_allow_html=True)

def page_header(title):
    ts = now_brt().strftime("%d/%m/%Y %H:%M")

def kpi_card(label, value, chg_p=None, sub="", invert=False, d=None, raw_delta=None):
    d = d or {}
    cd = d.get("close_date")
    if chg_p is not None:
        up    = chg_p >= 0
        arrow = "▲" if up else "▼"
        color = "#16a34a" if up else "#dc2626"
        display_val = fmt(raw_delta) if raw_delta is not None else f"{abs(chg_p):.2f}%"
        delta_html = f"<div style='color:{color};font-size:12px;font-weight:600;margin-top:4px'>{arrow} {display_val}</div>"
    else:
        delta_html = ""
    sub_html    = f"<div style='font-size:10px;color:#9ca3af;margin-top:6px'>{sub}</div>" if sub else ""
    banner_html = (f"<div style='background:#fef9c3;border:1px solid #fde047;border-radius:6px;"
                   f"font-size:9px;font-weight:600;color:#854d0e;padding:3px 8px;margin-top:8px;"
                   f"text-align:center'>⚠ Ref. {cd}</div>") if cd else ""
    card = (
        "<div style='background:#ffffff;border:1px solid #e2e5e9;border-radius:12px;"
        "padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.05);text-align:center'>"
        f"<div style='font-size:10px;font-weight:700;color:#6b7280;"
        f"text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px'>{label}</div>"
        f"<div style='font-size:22px;font-weight:700;color:#111827'>{value}</div>"
        f"{delta_html}{sub_html}{banner_html}"
        "</div>"
    )
    st.markdown(card, unsafe_allow_html=True)

# ── Helpers Plotly ────────────────────────────────────────────────────────────
_B = dict(paper_bgcolor="#fff",plot_bgcolor="#fff",font_color="#6b7280",font_family="Inter",
          margin=dict(l=52,r=16,t=40,b=36),
          xaxis=dict(gridcolor="#f1f5f9",showline=False,tickfont=dict(size=10,color="#9ca3af"),zeroline=False,fixedrange=True),
          yaxis=dict(gridcolor="#f1f5f9",showline=False,tickfont=dict(size=10,color="#9ca3af"),zeroline=False,fixedrange=True),
          title_font=dict(color="#374151",size=12,family="Inter"),
          hoverlabel=dict(bgcolor="#1a2035",font_size=12,font_color="#e2e8f0"),dragmode=False)
_I = {**_B,
      "xaxis":{**_B["xaxis"],"fixedrange":False},
      "yaxis":{**_B["yaxis"],"fixedrange":False},
      "dragmode":"zoom"}

_RS_BUTTONS = [
    dict(count=6,  label="6M",  step="month", stepmode="backward"),
    dict(count=1,  label="1A",  step="year",  stepmode="backward"),
    dict(count=2,  label="2A",  step="year",  stepmode="backward"),
    dict(count=5,  label="5A",  step="year",  stepmode="backward"),
    dict(step="all", label="Tudo"),
]
_RS_STYLE = dict(bgcolor="#f8fafc", bordercolor="#e2e5e9", borderwidth=1,
                 font=dict(size=11, color="#374151"), activecolor="#e6f0ed",
                 x=1.0, xanchor="right", y=1.0, yanchor="bottom", buttons=_RS_BUTTONS)

def _rng(fig, df, sfx="", pad=0.08):
    if df.empty: return fig
    mn,mx = df["valor"].min(),df["valor"].max()
    yd = (mx-mn)*pad if mx!=mn else abs(mx)*0.1 or 1
    xd = (df["data"].max()-df["data"].min())*0.02
    fig.update_xaxes(range=[df["data"].min()-xd, df["data"].max()+xd])
    fig.update_yaxes(range=[mn-yd,mx+yd],tickformat=".2f",ticksuffix=sfx.strip())
    return fig

def _add_rangeslider(fig, height, extra_top=32):
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.05, bgcolor="#f1f5f9"),
        rangeselector=_RS_STYLE,
    )
    fig.update_yaxes(fixedrange=False)
    fig.update_layout(height=height+40, margin=dict(t=40+extra_top))
    return fig

def line_fig(df, title, color="#1a2035", fill=True, suffix="", height=260, inter=False):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["data"],y=df["valor"],mode="lines",line=dict(color=color,width=2),
        fill="tozeroy" if fill else "none",fillcolor=hex_rgba(color,.07),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>"))
    fig.update_layout(**(_I if inter else _B),title=title,height=height)
    if inter: fig = _add_rangeslider(fig, height)
    return _rng(fig,df,suffix) if not df.empty else fig

def bar_fig(df, title, suffix="", height=260, inter=False):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["data"],y=df["valor"],
        marker_color=["#16a34a" if v>=0 else "#dc2626" for v in df["valor"]],marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>"))
    fig.update_layout(**(_I if inter else _B),title=title,height=height)
    if inter: fig = _add_rangeslider(fig, height)
    return _rng(fig,df,suffix,.15) if not df.empty else fig

# ── Figura overlay: IPCA headline + todos os núcleos ─────────────────────────
def cores_overlay_fig(df_ipca, nucleo_data, height=480):
    fig = go.Figure()

    if not df_ipca.empty:
        fig.add_trace(go.Scatter(
            x=df_ipca["data"], y=df_ipca["valor"],
            mode="lines", name="IPCA (headline)",
            line=dict(color="#1a2035", width=2.5),
            hovertemplate="%{x|%b/%Y}<br><b>IPCA: %{y:.2f}%</b><extra></extra>"
        ))

    for key, (df_n, label, color) in nucleo_data.items():
        if not df_n.empty:
            fig.add_trace(go.Scatter(
                x=df_n["data"], y=df_n["valor"],
                mode="lines", name=f"{key} — {label}",
                line=dict(color=color, width=1.6),
                hovertemplate=f"%{{x|%b/%Y}}<br><b>{key}: %{{y:.2f}}%</b><extra></extra>"
            ))

    _layout_overlay = {**_I, "margin": dict(l=52, r=16, t=44, b=90)}
    fig.update_layout(
        **_layout_overlay,
        height=height,
        title="IPCA e Núcleos de Inflação (% ao mês)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.18,
            xanchor="left", x=0,
            font=dict(size=10, color="#374151"),
            bgcolor="rgba(255,255,255,0)",
        ),
    )
    fig.update_yaxes(range=[-2, 2], ticksuffix="%")
    fig = _add_rangeslider(fig, height, extra_top=40)
    return fig

# ── Figura grupos: barras horizontais — último mês ────────────────────────────
def grupos_bar_fig(df_grupos, ultimo_mes):
    df_m = df_grupos[
        (df_grupos["data"] == ultimo_mes) &
        (df_grupos["grupo_id"] != "7169")
    ].copy()
    if df_m.empty:
        return go.Figure()
    df_m = df_m.sort_values("valor", ascending=True)
    colors = ["#dc2626" if v >= 0 else "#16a34a" for v in df_m["valor"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_m["valor"], y=df_m["grupo"],
        orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[f"{v:+.2f}%" for v in df_m["valor"]],
        textposition="outside",
        hovertemplate="%{y}<br><b>%{x:.2f}%</b><extra></extra>",
    ))
    _layout_g = {**_B, "margin": dict(l=185, r=70, t=44, b=36)}
    fig.update_layout(**_layout_g,
        height=340,
        title=f"Variação Mensal por Grupo — {ultimo_mes.strftime('%b/%Y')}",
        xaxis_title="% ao mês",
    )
    fig.update_xaxes(ticksuffix="%", zeroline=True, zerolinecolor="#e2e5e9", zerolinewidth=1)
    return fig

# ── Figura grupos: linhas — evolução por período (interativa) ─────────────────
def grupos_linhas_fig(df_grupos, d_ini=None, d_fim=None, height=420):
    df_f = df_grupos[df_grupos["grupo_id"] != "7169"].copy()
    if df_f.empty:
        return go.Figure()
    if d_ini:
        df_f = df_f[df_f["data"] >= pd.Timestamp(d_ini)]
    if d_fim:
        df_f = df_f[df_f["data"] <= pd.Timestamp(d_fim)]
    if df_f.empty:
        return go.Figure()

    fig = go.Figure()
    for grupo in sorted(df_f["grupo"].unique()):
        df_g = df_f[df_f["grupo"] == grupo].sort_values("data")
        color = IPCA_GRUPOS_CORES.get(grupo, "#94a3b8")
        fig.add_trace(go.Scatter(
            x=df_g["data"], y=df_g["valor"],
            mode="lines+markers",
            name=grupo,
            line=dict(color=color, width=1.8),
            marker=dict(size=5, color=color),
            hovertemplate=f"%{{x|%b/%Y}}<br><b>{grupo}: %{{y:.2f}}%</b><extra></extra>",
        ))
    _layout_l = {**_I, "margin": dict(l=52, r=16, t=80, b=36)}
    fig.update_layout(**_layout_l,
        height=height,
        title="Variação Mensal por Grupo (% ao mês)",
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(size=10, color="#374151"),
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#e2e5e9", borderwidth=1,
        ),
    )
    fig.update_yaxes(ticksuffix="%")
    fig = _add_rangeslider(fig, height, extra_top=50)
    return fig

# ── Figura acumulado 12M vs meta ──────────────────────────────────────────────
def acum12m_meta_fig(df_ipca_full):
    df = df_ipca_full.copy().sort_values("data").reset_index(drop=True)
    if len(df) < 12:
        return go.Figure()
    df["acum12m"] = df["valor"].rolling(12).sum()
    df = df.dropna(subset=["acum12m"])

    fig = go.Figure()
    meta_val = 3.0
    fig.add_hrect(
        y0=meta_val - BCB_TOLE, y1=meta_val + BCB_TOLE,
        fillcolor="rgba(22,163,74,0.08)", line_width=0,
        annotation_text=f"Banda ±{BCB_TOLE}pp", annotation_position="top right",
        annotation_font=dict(size=10, color="#16a34a"),
    )
    fig.add_hline(
        y=meta_val, line_dash="dot", line_color="#16a34a", line_width=1.5,
        annotation_text=f"Meta {meta_val:.1f}%", annotation_position="right",
        annotation_font=dict(size=10, color="#16a34a"),
    )
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["acum12m"],
        mode="lines",
        name="IPCA acum. 12M",
        line=dict(color="#1a2035", width=2),
        fill="tozeroy", fillcolor="rgba(26,32,53,0.05)",
        hovertemplate="%{x|%b/%Y}<br><b>Acum. 12M: %{y:.2f}%</b><extra></extra>",
    ))
    fig.update_layout(
        **_I,
        height=320,
        title="IPCA Acumulado 12 Meses vs Meta BCB",
        hovermode="x unified",
        showlegend=False,
    )
    fig.update_yaxes(range=[0, 10], ticksuffix="%")
    fig = _add_rangeslider(fig, 320)
    return fig

# ── Data BCB ──────────────────────────────────────────────────────────────────
def _parse(v):
    if v is None: return None
    s = str(v).strip().replace("\xa0","").replace(" ","")
    if "," in s: s=s.replace(".","").replace(",",".")
    try: return float(s)
    except: return None

def _build(raw):
    if not raw: return pd.DataFrame(columns=["data","valor"])
    df = pd.DataFrame(raw)
    if "data" not in df.columns: return pd.DataFrame(columns=["data","valor"])
    df["data"]  = pd.to_datetime(df["data"],format="%d/%m/%Y",errors="coerce")
    df["valor"] = df["valor"].apply(_parse)
    return df.dropna(subset=["data","valor"]).sort_values("data").reset_index(drop=True)[["data","valor"]]

def _fetch(url):
    for _ in range(3):
        try:
            r = requests.get(url,headers=HDRS,timeout=20,verify=False)
            if r.status_code==200 and "html" not in r.headers.get("Content-Type","").lower():
                data=r.json()
                if isinstance(data,list) and data: return data
            time.sleep(0.8)
        except: time.sleep(1)
    return []

@st.cache_data(ttl=3600,show_spinner=False)
def get_bcb(c,n):
    raw=_fetch(BCB_BASE.format(c=c)+f"/ultimos/{n}?formato=json")
    if not raw:
        hoje=datetime.today()
        raw=_fetch(BCB_BASE.format(c=c)+f"?formato=json&dataInicial={(hoje-timedelta(days=n*45)).strftime('%d/%m/%Y')}&dataFinal={hoje.strftime('%d/%m/%Y')}")
    return _build(raw)

@st.cache_data(ttl=3600,show_spinner=False)
def get_bcb_full(c):
    return _build(_fetch(BCB_BASE.format(c=c)+"?formato=json"))

@st.cache_data(ttl=3600,show_spinner=False)
def get_bcb_range(c,ini,fim):
    return _build(_fetch(BCB_BASE.format(c=c)+f"?formato=json&dataInicial={ini}&dataFinal={fim}"))

# ── Data IBGE SIDRA ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_ipca_grupos(n_periodos: int = 24) -> pd.DataFrame:
    """
    Retorna variação mensal do IPCA por grupo (IBGE SIDRA tabela 7060, variável 63).
    grupo_id == '7169' → Índice Geral
    """
    url = IBGE_SIDRA.format(
        tabela="7060",
        periodos=f"-{n_periodos}",
        var="63",
        cls=f"315[{IPCA_GRUPOS_IDS}]",
    )
    try:
        r = requests.get(url, headers=HDRS, timeout=30)
        r.raise_for_status()
        raw = r.json()
        rows = []
        for variavel in raw:
            for resultado in variavel.get("resultados", []):
                cats = resultado.get("classificacoes", [])
                if not cats:
                    continue
                cat_dict = cats[0].get("categoria", {})
                grupo_id = str(next(iter(cat_dict), ""))
                # Usa nome padronizado pelo ID — ignora qualquer subgrupo não mapeado
                grupo_nome = IPCA_ID_NOME.get(grupo_id)
                if not grupo_nome:
                    continue
                series_list = resultado.get("series", [])
                if not series_list:
                    continue
                serie = series_list[0].get("serie", {})
                for periodo, valor in serie.items():
                    try:
                        val = float(str(valor).replace(",", "."))
                        dt  = pd.to_datetime(periodo, format="%Y%m")
                        rows.append({
                            "data":     dt,
                            "grupo_id": grupo_id,
                            "grupo":    grupo_nome,
                            "valor":    val,
                        })
                    except Exception:
                        pass
        if not rows:
            return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])
        return (pd.DataFrame(rows)
                .sort_values(["data", "grupo"])
                .reset_index(drop=True))
    except Exception:
        return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])

@st.cache_data(ttl=3600, show_spinner=False)
def get_ipca_acum_grupo(n_periodos: int = 24) -> pd.DataFrame:
    """
    Variação acumulada 12 meses do IPCA por grupo (IBGE SIDRA tabela 7060, variável 2266).
    """
    url = IBGE_SIDRA.format(
        tabela="7060",
        periodos=f"-{n_periodos}",
        var="2266",
        cls=f"315[{IPCA_GRUPOS_IDS}]",
    )
    try:
        r = requests.get(url, headers=HDRS, timeout=30)
        r.raise_for_status()
        raw = r.json()
        rows = []
        for variavel in raw:
            for resultado in variavel.get("resultados", []):
                cats = resultado.get("classificacoes", [])
                if not cats:
                    continue
                cat_dict = cats[0].get("categoria", {})
                grupo_id = str(next(iter(cat_dict), ""))
                grupo_nome = IPCA_ID_NOME.get(grupo_id)
                if not grupo_nome:
                    continue
                series_list = resultado.get("series", [])
                if not series_list:
                    continue
                serie = series_list[0].get("serie", {})
                for periodo, valor in serie.items():
                    try:
                        val = float(str(valor).replace(",", "."))
                        dt  = pd.to_datetime(periodo, format="%Y%m")
                        rows.append({"data": dt, "grupo_id": grupo_id,
                                     "grupo": grupo_nome, "valor": val})
                    except Exception:
                        pass
        if not rows:
            return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])
        return (pd.DataFrame(rows)
                .sort_values(["data", "grupo"])
                .reset_index(drop=True))
    except Exception:
        return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])

# ── Data Yahoo / yfinance ────────────────────────────────────────────────────
def _yf_quote_raw(sym):
    try:
        import yfinance as yf
        tk   = yf.Ticker(sym)
        hist = tk.history(period="5d", auto_adjust=True)
        if hist.empty:
            return None
        fi    = tk.fast_info
        price = None
        try:    price = float(fi.last_price)
        except: pass
        if not price:
            price = float(hist["Close"].iloc[-1])
        prev = None
        try:    prev = float(fi.previous_close)
        except: pass
        if not prev and len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
        last_dt   = hist.index[-1]
        last_date = pd.Timestamp(last_dt).tz_localize(None).date()
        day_high = day_low = None
        try:    day_high = float(fi.day_high)
        except: pass
        try:    day_low  = float(fi.day_low)
        except: pass
        if not day_high and not hist.empty:
            day_high = float(hist["High"].iloc[-1])
            day_low  = float(hist["Low"].iloc[-1])
        return {"price": price, "prev": prev, "last_date": last_date,
                "day_high": day_high, "day_low": day_low}
    except:
        return None

def _http_quote_raw(sym):
    urls = [
        f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d",
        f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HDRS, timeout=10, verify=False)
            if r.status_code != 200: continue
            data = r.json()
            if "chart" in data:
                meta  = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice") or meta.get("previousClose")
                prev  = meta.get("chartPreviousClose") or meta.get("previousClose")
                rt    = meta.get("regularMarketTime")
                last_date = datetime.fromtimestamp(rt).date() if rt else None
                dh = meta.get("regularMarketDayHigh")
                dl = meta.get("regularMarketDayLow")
                if price: return {"price": float(price), "prev": float(prev) if prev else None,
                                  "last_date": last_date,
                                  "day_high": float(dh) if dh else None,
                                  "day_low":  float(dl) if dl else None}
            if "quoteResponse" in data:
                q     = data["quoteResponse"]["result"][0]
                price = q.get("regularMarketPrice")
                prev  = q.get("regularMarketPreviousClose")
                dh    = q.get("regularMarketDayHigh")
                dl    = q.get("regularMarketDayLow")
                if price: return {"price": float(price), "prev": float(prev) if prev else None,
                                  "last_date": now_brt().date(),
                                  "day_high": float(dh) if dh else None,
                                  "day_low":  float(dl) if dl else None}
        except:
            continue
    return None

@st.cache_data(ttl=60, show_spinner=False)
def get_quote(sym):
    raw = _yf_quote_raw(sym) or _http_quote_raw(sym)
    if not raw or not raw.get("price"):
        return {}
    price      = raw["price"]
    prev       = raw.get("prev") or price
    last_date  = raw.get("last_date")
    today_brt  = now_brt().date()
    is_today   = (last_date == today_brt) if last_date else False
    cd         = last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None
    chg_p = ((price - prev) / prev * 100) if (prev and prev != 0) else None
    chg_v = (price - prev) if prev else None
    return {"price": price, "prev": prev, "chg_p": chg_p, "chg_v": chg_v,
            "day_high": raw.get("day_high"), "day_low": raw.get("day_low"),
            "market": "REGULAR" if is_today else "CLOSED",
            "is_live": is_today, "is_extended": False,
            "is_closed": not is_today,
            "close_date": cd}

@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(sym, years=5):
    try:
        import yfinance as yf
        df = yf.download(sym, period=f"{years}y", auto_adjust=True, progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                closes = df["Close"].iloc[:, 0]
            else:
                closes = df["Close"]
            result = pd.DataFrame({"data": df.index, "valor": closes.values.flatten()})
            result["data"] = pd.to_datetime(result["data"]).dt.tz_localize(None)
            return result.dropna().reset_index(drop=True)
    except: pass
    try:
        r   = requests.get(f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range={years}y",
                           headers=HDRS, timeout=15, verify=False)
        res = r.json()["chart"]["result"][0]
        df  = pd.DataFrame({"data": pd.to_datetime(res["timestamp"], unit="s"),
                            "valor": res["indicators"]["quote"][0]["close"]})
        return df.dropna().reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data", "valor"])

def aplicar_periodo(df, periodo, ind_nome):
    df = df.copy().sort_values("data").reset_index(drop=True)
    if periodo in ("Original","Mensal (original)","Var. trimestral (original)","Nível (original)"):
        return df, df.attrs.get("unit","")
    elif periodo == "Acumulado 12M":
        df["valor"] = df["valor"].rolling(12).sum()
        return df.dropna(), "% acum. 12M"
    elif periodo == "Acumulado no ano":
        df["valor"] = df.groupby(df["data"].dt.year)["valor"].cumsum()
        return df, "% acum. ano"
    elif periodo == "Var. mensal (m/m)":
        df["valor"] = df["valor"].pct_change(1) * 100
        return df.dropna(), "% m/m"
    elif periodo == "Var. trimestral (t/t)":
        df["valor"] = df["valor"].pct_change(3) * 100
        return df.dropna(), "% t/t"
    elif periodo == "Var. anual (a/a)":
        df["valor"] = df["valor"].pct_change(12) * 100
        return df.dropna(), "% a/a"
    elif periodo == "Acumulado 4 trimestres":
        df["valor"] = df["valor"].rolling(4).sum()
        return df.dropna(), "% acum. 4 tri"
    return df, ""

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div style='padding:20px 4px 12px 4px'>"
                "<span style='font-size:24px;font-weight:900;color:#004031;letter-spacing:-0.5px'>EQI</span>"
                "</div>", unsafe_allow_html=True)
    st.divider()
    _NAV_SLUGS = {
        "Início":          "inicio",
        "Monitor Inflação":  "ipca",
        "Mercados Globais":"mercados",
        "Gráficos":        "graficos",
        "Exportar":        "exportar",
    }
    for label in NAV:
        slug = _NAV_SLUGS.get(label, label.lower())
        st.markdown(f"<div class='nav-marker nav-{slug}'></div>", unsafe_allow_html=True)
        if st.button(label, key=f"nav_{label}",
                     type="primary" if st.session_state.pagina == label else "secondary",
                     use_container_width=True):
            st.session_state.pagina = label
            st.rerun()
    st.divider()
    st.caption("Fontes: BCB/SGS · IBGE/SIDRA · Yahoo Finance")
    st.caption("Mercados ↻60s · BCB/IBGE ↻1h")

# ══════════════════════════════════════════════════════════════════════════════
# INÍCIO
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pagina == "Início":
    page_header("EQI Dashboard Macro")
    with st.spinner("Carregando..."):
        ibov=get_quote("^BVSP"); usd=get_quote("USDBRL=X"); eur=get_quote("EURBRL=X")
        _hoje  = datetime.today()
        _ini13 = (_hoje - timedelta(days=400)).strftime("%d/%m/%Y")
        _ini30 = (_hoje - timedelta(days=45)).strftime("%d/%m/%Y")
        _ini3a = (_hoje - timedelta(days=3*365)).strftime("%d/%m/%Y")
        _fim   = _hoje.strftime("%d/%m/%Y")
        dsel  = get_bcb_range(432,   _ini13, _fim)
        dipca = get_bcb_range(433,   _ini13, _fim)
        dibc  = get_bcb_range(24363, _ini13, _fim)
        dcam  = get_bcb_range(1,     _ini30, _fim)
        dpib  = get_bcb_range(4380,  _ini3a, _fim)
        ddes  = get_bcb_range(24369, _ini3a, _fim)

    sec_title("Indicadores de Mercado","↻ 60s","badge-live")
    c1,c2,c3=st.columns(3)
    with c1:
        v=ibov.get("price")
        kpi_card("IBOVESPA",fmt(v,0)+" pts" if v else "—",ibov.get("chg_p"),
                 sub=f"Var. dia: {fmt(ibov.get('chg_v'),0)} pts" if ibov.get("chg_v") is not None else "",d=ibov)
    with c2:
        v=usd.get("price")
        kpi_card("Dólar (USD/BRL)",f"R$ {fmt(v,4)}" if v else "—",usd.get("chg_p"),
                 sub=f"Ant.: R$ {fmt(usd.get('prev'),4)}" if v else "",invert=True,d=usd)
    with c3:
        v=eur.get("price")
        kpi_card("Euro (EUR/BRL)",f"R$ {fmt(v,4)}" if v else "—",eur.get("chg_p"),
                 sub=f"Ant.: R$ {fmt(eur.get('prev'),4)}" if v else "",invert=True,d=eur)

    sec_title("Indicadores Econômicos","↻ diário","badge-daily")
    c4,c5,c6=st.columns(3)
    with c4:
        if not dsel.empty:
            vs = dsel["valor"].iloc[-1]
            ds = float(vs - dsel["valor"].iloc[-2]) if len(dsel)>=2 else None
            kpi_card("Selic", f"{fmt(vs)}% a.a.", chg_p=ds,
                     sub=f"Ref: {dsel['data'].iloc[-1].strftime('%b/%Y')}")
        else: kpi_card("Selic","—",sub="BCB indisponível")
    with c5:
        if not dipca.empty:
            v=dipca["valor"].iloc[-1]
            d2=float(v-dipca["valor"].iloc[-2]) if len(dipca)>=2 else None
            kpi_card("IPCA",f"{fmt(v)}% mês",chg_p=d2,sub=f"Ref: {dipca['data'].iloc[-1].strftime('%b/%Y')}")
        else: kpi_card("IPCA","—",sub="BCB indisponível")
    with c6:
        if not ddes.empty:
            vd = ddes["valor"].iloc[-1]
            dd = float(vd - ddes["valor"].iloc[-2]) if len(ddes)>=2 else None
            kpi_card("Desemprego (PNAD)", f"{fmt(vd)}%", chg_p=dd,
                     sub=f"Ref: {ddes['data'].iloc[-1].strftime('%b/%Y')}")
        else: kpi_card("Desemprego (PNAD)","—",sub="BCB indisponível")

    st.markdown('<div class="sec-title">Histórico — 12 meses <span style="font-size:10px;font-weight:400;color:#9ca3af;text-transform:none;letter-spacing:0;margin-left:4px">→ análise completa em Monitor Inflação</span></div>',unsafe_allow_html=True)
    ca,cb=st.columns(2)
    with ca:
        if not dsel.empty: st.plotly_chart(line_fig(dsel,"Selic (% a.a.)","#1a2035",suffix="%"),use_container_width=True,config=CHART_CFG)
    with cb:
        if not dipca.empty: st.plotly_chart(bar_fig(dipca,"IPCA (% ao mês)",suffix="%"),use_container_width=True,config=CHART_CFG)
    cc,cd=st.columns(2)
    with cc:
        df30=dcam.tail(30) if not dcam.empty else dcam
        if not df30.empty: st.plotly_chart(line_fig(df30,"Dólar PTAX — 30 dias (R$)","#d97706",suffix=" R$"),use_container_width=True,config=CHART_CFG)
    with cd:
        if not dibc.empty: st.plotly_chart(line_fig(dibc,"IBC-Br","#0891b2",fill=False),use_container_width=True,config=CHART_CFG)
    ce,cf=st.columns(2)
    with ce:
        if not dpib.empty: st.plotly_chart(bar_fig(dpib,"PIB — variação trimestral (%)",suffix="%"),use_container_width=True,config=CHART_CFG)
    with cf:
        if not ddes.empty: st.plotly_chart(line_fig(ddes,"Desemprego PNAD (%)","#dc2626",suffix="%"),use_container_width=True,config=CHART_CFG)

# ══════════════════════════════════════════════════════════════════════════════
# IPCA & NÚCLEOS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Monitor Inflação":
    page_header("Monitor de Inflação")

    with st.spinner("Carregando indicadores de inflação..."):
        # ── IPCA headline (série completa para cálculos) ──────────────────────
        df_ipca_full = get_bcb_full(433)

        # ── Núcleos — séries completas do BCB/SGS ────────────────────────────
        nucleo_data = {}
        for key, (cod, label, color) in NUCLEO_SGS.items():
            nucleo_data[key] = (get_bcb_full(cod), label, color)

        # ── Grupos IPCA — IBGE SIDRA ──────────────────────────────────────────
        df_grupos_mensal = get_ipca_grupos(60)
        df_grupos_acum   = get_ipca_acum_grupo(60)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    sec_title("IPCA — Inflação ao Consumidor", "↻ diário", "badge-daily")

    hoje_ano  = datetime.today().year
    meta_bcb  = BCB_META.get(hoje_ano, 3.0)
    teto_meta = meta_bcb + BCB_TOLE
    piso_meta = meta_bcb - BCB_TOLE

    ipca_mensal  = df_ipca_full["valor"].iloc[-1]  if not df_ipca_full.empty else None
    ipca_ant     = df_ipca_full["valor"].iloc[-2]  if len(df_ipca_full) >= 2 else None
    ipca_acum12m = df_ipca_full["valor"].tail(12).sum() if len(df_ipca_full) >= 12 else None
    ref_mes      = df_ipca_full["data"].iloc[-1].strftime("%b/%Y") if not df_ipca_full.empty else ""
    desvio_meta  = (ipca_acum12m - meta_bcb) if ipca_acum12m is not None else None
    var_mensal   = (ipca_mensal - ipca_ant) if (ipca_mensal is not None and ipca_ant is not None) else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("IPCA Mensal",
                 f"{fmt(ipca_mensal)}%" if ipca_mensal is not None else "—",
                 chg_p=var_mensal,
                 raw_delta=var_mensal,
                 sub=f"Ref: {ref_mes}")
    with c2:
        if ipca_acum12m is not None:
            dentro = piso_meta <= ipca_acum12m <= teto_meta
            status = "✓ dentro da meta" if dentro else ("↑ acima do teto" if ipca_acum12m > teto_meta else "↓ abaixo do piso")
            kpi_card("Acum. 12 Meses",
                     f"{fmt(ipca_acum12m)}%",
                     sub=status)
        else:
            kpi_card("Acum. 12 Meses", "—")
    with c3:
        kpi_card("Meta BCB",
                 f"{fmt(meta_bcb, 1)}%",
                 sub=f"Banda: {fmt(piso_meta,1)}% – {fmt(teto_meta,1)}% (±{BCB_TOLE}pp)")
    with c4:
        if desvio_meta is not None:
            color_dev = "#dc2626" if abs(desvio_meta) > BCB_TOLE else "#16a34a"
            kpi_card("Desvio da Meta",
                     f"{'+' if desvio_meta >= 0 else ''}{fmt(desvio_meta)}pp",
                     chg_p=desvio_meta,
                     raw_delta=desvio_meta,
                     sub=f"Meta contínua {hoje_ano}")
        else:
            kpi_card("Desvio da Meta", "—")

    # ── Núcleos de Inflação ────────────────────────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("Núcleos de Inflação — BCB", "↻ diário", "badge-daily")

    st.markdown(
        "<div style='font-size:11px;color:#6b7280;margin:0 0 14px'>"
        "Cinco medidas de núcleo calculadas e publicadas pelo BCB no <em>Relatório de Inflação</em>: "
        "<b>MA-S</b> médias aparadas c/ suavização (cód. 4466) · "
        "<b>MA</b> médias aparadas s/ suavização (11426) · "
        "<b>DP</b> dupla ponderação (4467) · "
        "<b>EX</b> exclusão de alimentação no domicílio e administrados (11427) · "
        "<b>P55</b> percentil 55 (28750)"
        "</div>",
        unsafe_allow_html=True,
    )

    fig_cores = cores_overlay_fig(df_ipca_full, nucleo_data, height=480)
    if not df_ipca_full.empty:
        _xmax = df_ipca_full["data"].max()
        _xmin = _xmax - pd.DateOffset(months=24)
        fig_cores.update_xaxes(range=[str(_xmin.date()), str(_xmax.date())])
    st.plotly_chart(fig_cores, use_container_width=True, config={**CHART_CFG_INT,
        "toImageButtonOptions": {"format":"png","filename":"ipca_nucleos","scale":2}})

    # Tabela resumo — últimas leituras
    tab_rows = []
    if not df_ipca_full.empty:
        ul = df_ipca_full.iloc[-1]
        an = df_ipca_full.iloc[-2]["valor"] if len(df_ipca_full) >= 2 else None
        tab_rows.append({
            "Medida":     "IPCA (headline)",
            "Cód. SGS":   433,
            "Último valor": f"{fmt(ul['valor'])}%",
            "Ref.":       ul["data"].strftime("%b/%Y"),
            "Var. s/ ant.": f"{'+' if an and ul['valor']>=an else ''}{fmt(ul['valor']-an)}pp" if an else "—",
        })
    for key, (df_n, label, color) in nucleo_data.items():
        if not df_n.empty:
            ul = df_n.iloc[-1]
            an = df_n.iloc[-2]["valor"] if len(df_n) >= 2 else None
            cod = NUCLEO_SGS[key][0]
            tab_rows.append({
                "Medida":     f"{key} — {label}",
                "Cód. SGS":   cod,
                "Último valor": f"{fmt(ul['valor'])}%",
                "Ref.":       ul["data"].strftime("%b/%Y"),
                "Var. s/ ant.": f"{'+' if an and ul['valor']>=an else ''}{fmt(ul['valor']-an)}pp" if an else "—",
            })
    if tab_rows:
        st.dataframe(pd.DataFrame(tab_rows), hide_index=True, use_container_width=True,
                     height=46 + len(tab_rows) * 35)

    # ── Média dos Núcleos — últimos 12 meses ──────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("Média dos Núcleos — Acumulado 12 Meses", "↻ diário", "badge-daily")

    _series_nucleos = [df_n.set_index("data")["valor"].rename(key)
                       for key, (df_n, _, _) in nucleo_data.items()
                       if not df_n.empty]
    if _series_nucleos:
        # Monta DataFrame com todas as séries mensais alinhadas
        _df_all = pd.concat(_series_nucleos, axis=1).sort_index()

        # Calcula acumulado 12M (soma rolling de 12 meses) para cada núcleo
        _keys = [k for k in NUCLEO_SGS if k in _df_all.columns]
        for k in _keys:
            _df_all[f"{k}_a12"] = _df_all[k].rolling(12).sum()

        # Média do acumulado 12M entre todos os núcleos
        _acum_cols = [f"{k}_a12" for k in _keys]
        _df_all["media_a12"] = _df_all[_acum_cols].mean(axis=1)
        _df_all = _df_all.dropna(subset=["media_a12"]).reset_index()

        # Acumulado 12M do IPCA headline para comparação
        _ipca_a12 = pd.DataFrame()
        if not df_ipca_full.empty:
            _tmp = df_ipca_full.copy().sort_values("data").set_index("data")
            _tmp["acum12m"] = _tmp["valor"].rolling(12).sum()
            _ipca_a12 = _tmp.dropna(subset=["acum12m"]).reset_index()

        # Filtra últimos 24 meses para exibição inicial (carrega tudo)
        _xmax_m = _df_all["data"].max()
        _xmin_m = _xmax_m - pd.DateOffset(months=24)

        if not _df_all.empty:
            fig_media = go.Figure()

            # Faixa sombreada min/max dos núcleos acumulados
            _df_all["min_a12"] = _df_all[_acum_cols].min(axis=1)
            _df_all["max_a12"] = _df_all[_acum_cols].max(axis=1)

            fig_media.add_trace(go.Scatter(
                x=pd.concat([_df_all["data"], _df_all["data"].iloc[::-1]]),
                y=pd.concat([_df_all["max_a12"], _df_all["min_a12"].iloc[::-1]]),
                fill="toself",
                fillcolor="rgba(139,92,246,0.10)",
                line=dict(color="rgba(0,0,0,0)"),
                hoverinfo="skip",
                showlegend=False,
            ))

            # Linha de cada núcleo (fina, discreta)
            for key, (_, label, color) in nucleo_data.items():
                col_a = f"{key}_a12"
                if col_a in _df_all.columns:
                    fig_media.add_trace(go.Scatter(
                        x=_df_all["data"], y=_df_all[col_a],
                        mode="lines",
                        name=key,
                        line=dict(color=color, width=1, dash="dot"),
                        opacity=0.55,
                        hovertemplate=f"%{{x|%b/%Y}}<br>{key} acum. 12M: %{{y:.2f}}%<extra></extra>",
                    ))

            # IPCA acumulado 12M
            if not _ipca_a12.empty:
                fig_media.add_trace(go.Scatter(
                    x=_ipca_a12["data"], y=_ipca_a12["acum12m"],
                    mode="lines",
                    name="IPCA acum. 12M",
                    line=dict(color="#1a2035", width=1.8, dash="dash"),
                    hovertemplate="%{x|%b/%Y}<br>IPCA acum. 12M: %{y:.2f}%<extra></extra>",
                ))

            # Linha da média dos núcleos acumulados (destaque)
            fig_media.add_trace(go.Scatter(
                x=_df_all["data"], y=_df_all["media_a12"],
                mode="lines+markers",
                name="Média Núcleos acum. 12M",
                line=dict(color="#7c3aed", width=2.5),
                marker=dict(size=6, color="#7c3aed"),
                hovertemplate="%{x|%b/%Y}<br><b>Média acum. 12M: %{y:.2f}%</b><extra></extra>",
            ))

            # Banda e meta BCB
            fig_media.add_hrect(
                y0=meta_bcb - BCB_TOLE, y1=meta_bcb + BCB_TOLE,
                fillcolor="rgba(22,163,74,0.07)", line_width=0,
            )
            fig_media.add_hline(
                y=meta_bcb, line_dash="dot", line_color="#16a34a", line_width=1.2,
                annotation_text=f"Meta {meta_bcb:.1f}%",
                annotation_position="right",
                annotation_font=dict(size=10, color="#16a34a"),
            )

            _layout_m = {**_I, "margin": dict(l=52, r=16, t=44, b=90)}
            fig_media.update_layout(
                **_layout_m,
                height=360,
                title="Núcleos de Inflação — Acumulado 12 Meses (%) vs Meta BCB",
                hovermode="x unified",
                legend=dict(
                    orientation="h",
                    yanchor="top", y=-0.22,
                    xanchor="left", x=0,
                    font=dict(size=10, color="#374151"),
                    bgcolor="rgba(255,255,255,0)",
                ),
            )
            fig_media.update_yaxes(ticksuffix="%", range=[0, 10])
            fig_media.update_xaxes(range=[str(_xmin_m.date()), str(_xmax_m.date())])
            fig_media = _add_rangeslider(fig_media, 360, extra_top=40)

            # Anotação com valor mais recente da média
            _last_media = _df_all["media_a12"].iloc[-1]
            _last_dt    = _df_all["data"].iloc[-1]
            fig_media.add_annotation(
                x=_last_dt, y=_last_media,
                text=f"  {fmt(_last_media)}%",
                showarrow=False,
                font=dict(size=11, color="#7c3aed", family="Inter"),
                xanchor="left",
            )

            st.plotly_chart(fig_media, use_container_width=True, config={**CHART_CFG_INT,
                "toImageButtonOptions": {"format":"png","filename":"nucleos_acum12m","scale":2}})

    # ── IPCA Acumulado 12M vs Meta ─────────────────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("Acumulado 12 Meses vs Meta BCB", "↻ diário", "badge-daily")
    if not df_ipca_full.empty:
        fig_acum = acum12m_meta_fig(df_ipca_full)
        _xmax_a = df_ipca_full["data"].max()
        _xmin_a = _xmax_a - pd.DateOffset(months=24)
        fig_acum.update_xaxes(range=[str(_xmin_a.date()), str(_xmax_a.date())])
        st.plotly_chart(fig_acum, use_container_width=True, config={**CHART_CFG_INT,
            "toImageButtonOptions": {"format":"png","filename":"ipca_acum12m_meta","scale":2}})

    # ── Desagregação por Grupos (IBGE) ─────────────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sec_title("IPCA por Grupos — IBGE SIDRA", "↻ diário", "badge-daily")

    if df_grupos_mensal.empty:
        st.warning("⚠️ API IBGE/SIDRA temporariamente indisponível. Tente novamente em instantes.")
    else:
        from datetime import date as _dg
        datas_disp = sorted(df_grupos_mensal["data"].unique())
        dmin_g = datas_disp[0].date()
        dmax_g = datas_disp[-1].date()
        # padrão: últimos 24 meses
        _d24g  = datas_disp[-24].date() if len(datas_disp) >= 24 else dmin_g

        st.markdown(
            f"<div style='font-size:11px;color:#6b7280;margin:0 0 12px'>"
            f"Disponível: <strong>{dmin_g.strftime('%b/%Y')}</strong> → "
            f"<strong>{dmax_g.strftime('%b/%Y')}</strong> · "
            f"{len(datas_disp)} meses · <em>Série completa carregada</em></div>",
            unsafe_allow_html=True,
        )

        cg1, cg2 = st.columns(2)
        with cg1:
            g_ini = st.date_input("Exibir de", value=_d24g,
                                  min_value=dmin_g, max_value=dmax_g, key="g_ini")
        with cg2:
            g_fim = st.date_input("Exibir até", value=dmax_g,
                                  min_value=dmin_g, max_value=dmax_g, key="g_fim")

        ultimo_mes = df_grupos_mensal[
            df_grupos_mensal["data"] <= pd.Timestamp(g_fim)
        ]["data"].max()

        if pd.isna(ultimo_mes):
            st.warning("Nenhum dado no intervalo selecionado.")
        else:
            st.success(
                f"✅ Exibindo {g_ini.strftime('%b/%Y')} → {g_fim.strftime('%b/%Y')} · "
                f"Referência do mês: {ultimo_mes.strftime('%b/%Y')}"
            )

            # ── Mini-cards: maiores altas e baixas no último mês ──────────────
            df_ult = df_grupos_mensal[
                (df_grupos_mensal["data"] == ultimo_mes) &
                (df_grupos_mensal["grupo_id"] != "7169")
            ].copy().sort_values("valor", ascending=False)

            def _mini_card(grupo, valor):
                cor   = "#dc2626" if valor >= 0 else "#16a34a"
                sinal = "▲" if valor >= 0 else "▼"
                st.markdown(
                    f"<div style='background:#fff;border:1px solid #e2e5e9;border-radius:10px;"
                    f"padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;"
                    f"justify-content:space-between'>"
                    f"<span style='font-size:12px;font-weight:500;color:#374151'>{grupo}</span>"
                    f"<span style='font-size:14px;font-weight:700;color:{cor}'>{sinal} {abs(valor):.2f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            ga, gb = st.columns([1.2, 1])
            with ga:
                st.plotly_chart(
                    grupos_bar_fig(df_grupos_mensal, ultimo_mes),
                    use_container_width=True, config=CHART_CFG,
                )
            with gb:
                top_alta  = df_ult.head(3)
                top_baixa = df_ult.tail(3)
                st.markdown(
                    f"<div style='font-size:10px;font-weight:700;color:#6b7280;"
                    f"text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px'>"
                    f"Maiores altas — {ultimo_mes.strftime('%b/%Y')}</div>",
                    unsafe_allow_html=True,
                )
                for _, row in top_alta.iterrows():
                    _mini_card(row["grupo"], row["valor"])
                st.markdown(
                    f"<div style='font-size:10px;font-weight:700;color:#6b7280;"
                    f"text-transform:uppercase;letter-spacing:1.5px;margin:14px 0 8px'>"
                    f"Menores variações — {ultimo_mes.strftime('%b/%Y')}</div>",
                    unsafe_allow_html=True,
                )
                for _, row in top_baixa.iterrows():
                    _mini_card(row["grupo"], row["valor"])

            # ── Gráfico de linhas — evolução no período selecionado ───────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.plotly_chart(
                grupos_linhas_fig(df_grupos_mensal, d_ini=g_ini, d_fim=g_fim, height=440),
                use_container_width=True,
                config={**CHART_CFG_INT,
                        "toImageButtonOptions": {"format":"png","filename":"ipca_grupos_evolucao","scale":2}},
            )

            # ── Acumulado 12M por grupo (IBGE) ────────────────────────────────
            if not df_grupos_acum.empty:
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                sec_title("Acumulado 12 Meses por Grupo — IBGE", "↻ diário", "badge-daily")

                ult_acum  = df_grupos_acum[
                    df_grupos_acum["data"] <= pd.Timestamp(g_fim)
                ]["data"].max()
                df_acum_u = df_grupos_acum[
                    (df_grupos_acum["data"] == ult_acum) &
                    (df_grupos_acum["grupo_id"] != "7169")
                ].copy().sort_values("valor", ascending=True)

                if not df_acum_u.empty:
                    colors_acum = [
                        "#dc2626" if v > teto_meta else
                        "#16a34a" if v < piso_meta else
                        "#0891b2"
                        for v in df_acum_u["valor"]
                    ]
                    fig_acum_g = go.Figure()
                    fig_acum_g.add_shape(type="rect",
                        x0=piso_meta, x1=teto_meta, y0=-0.5, y1=len(df_acum_u)-0.5,
                        fillcolor="rgba(22,163,74,0.07)", line_width=0)
                    fig_acum_g.add_vline(x=meta_bcb, line_dash="dot", line_color="#16a34a",
                                         line_width=1.5,
                                         annotation_text=f"Meta {meta_bcb:.1f}%",
                                         annotation_position="top",
                                         annotation_font=dict(size=10, color="#16a34a"))
                    fig_acum_g.add_trace(go.Bar(
                        x=df_acum_u["valor"], y=df_acum_u["grupo"],
                        orientation="h",
                        marker_color=colors_acum, marker_line_width=0,
                        text=[f"{v:.1f}%" for v in df_acum_u["valor"]],
                        textposition="outside",
                        hovertemplate="%{y}<br><b>Acum. 12M: %{x:.2f}%</b><extra></extra>",
                    ))
                    _layout_acum = {**_B, "margin": dict(l=190, r=70, t=44, b=36)}
                    fig_acum_g.update_layout(**_layout_acum,
                        height=340,
                        title=f"IPCA Acumulado 12M por Grupo — {ult_acum.strftime('%b/%Y')} (meta {meta_bcb:.1f}%)",
                        xaxis_title="% acumulado 12 meses",
                    )
                    fig_acum_g.update_xaxes(ticksuffix="%")
                    st.plotly_chart(fig_acum_g, use_container_width=True, config=CHART_CFG)

            # ── Download ──────────────────────────────────────────────────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            dlo_g = df_grupos_mensal[
                (df_grupos_mensal["data"] >= pd.Timestamp(g_ini)) &
                (df_grupos_mensal["data"] <= pd.Timestamp(g_fim))
            ].copy()
            dlo_g["data"] = dlo_g["data"].dt.strftime("%Y-%m")
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    f"💾 Baixar CSV — var. mensal por grupo ({len(dlo_g)} linhas)",
                    data=dlo_g.to_csv(index=False).encode("utf-8-sig"),
                    file_name="ipca_grupos_mensal.csv",
                    mime="text/csv",
                )
            with col_dl2:
                if not df_grupos_acum.empty:
                    dlo_acum = df_grupos_acum[
                        (df_grupos_acum["data"] >= pd.Timestamp(g_ini)) &
                        (df_grupos_acum["data"] <= pd.Timestamp(g_fim))
                    ].copy()
                    dlo_acum["data"] = dlo_acum["data"].dt.strftime("%Y-%m")
                    st.download_button(
                        f"💾 Baixar CSV — acum. 12M por grupo ({len(dlo_acum)} linhas)",
                        data=dlo_acum.to_csv(index=False).encode("utf-8-sig"),
                        file_name="ipca_grupos_acum12m.csv",
                        mime="text/csv",
                    )

    # ── Nota metodológica ──────────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    sec_title("Metodologia dos Núcleos de Inflação — BCB", "", "badge-daily")
    st.markdown("""
    <div style='background:#fff;border:1px solid #e2e5e9;border-radius:12px;padding:20px 24px;
                font-size:12px;color:#374151;line-height:1.8'>

    <p style='margin:0 0 12px'>
    Os núcleos de inflação são medidas alternativas ao IPCA cheio que buscam capturar a 
    <strong>tendência subjacente da inflação</strong>, removendo componentes voláteis ou transitórios. 
    O BCB acompanha cinco medidas oficiais, publicadas mensalmente no 
    <em>Relatório de Inflação</em>:
    </p>

    <table style='width:100%;border-collapse:collapse;font-size:11.5px'>
      <thead>
        <tr style='border-bottom:2px solid #e2e5e9'>
          <th style='text-align:left;padding:6px 10px;color:#6b7280;font-weight:700;
                     text-transform:uppercase;letter-spacing:1px;font-size:10px'>Sigla</th>
          <th style='text-align:left;padding:6px 10px;color:#6b7280;font-weight:700;
                     text-transform:uppercase;letter-spacing:1px;font-size:10px'>Nome</th>
          <th style='text-align:left;padding:6px 10px;color:#6b7280;font-weight:700;
                     text-transform:uppercase;letter-spacing:1px;font-size:10px'>Cód. SGS</th>
          <th style='text-align:left;padding:6px 10px;color:#6b7280;font-weight:700;
                     text-transform:uppercase;letter-spacing:1px;font-size:10px'>Como é calculado</th>
        </tr>
      </thead>
      <tbody>
        <tr style='border-bottom:1px solid #f1f5f9'>
          <td style='padding:8px 10px;font-weight:700;color:#0891b2'>MA-S</td>
          <td style='padding:8px 10px'>Médias Aparadas com Suavização</td>
          <td style='padding:8px 10px;color:#6b7280'>4466</td>
          <td style='padding:8px 10px'>Exclui os itens com maior e menor variação no mês 
          (aparamento simétrico de 20% em cada extremo). Aplica <strong>suavização</strong> em 
          serviços de preços monitorados e sazonais, distribuindo ao longo de 12 meses as 
          variações atípicas. É a medida mais utilizada pelo Copom.</td>
        </tr>
        <tr style='border-bottom:1px solid #f1f5f9'>
          <td style='padding:8px 10px;font-weight:700;color:#06b6d4'>MA</td>
          <td style='padding:8px 10px'>Médias Aparadas sem Suavização</td>
          <td style='padding:8px 10px;color:#6b7280'>11426</td>
          <td style='padding:8px 10px'>Idêntico ao MA-S, porém <strong>sem suavizar</strong> 
          os itens monitorados e sazonais. Apara 20% dos extremos e recalcula a média 
          ponderada com os itens restantes. Mais sensível a choques pontuais.</td>
        </tr>
        <tr style='border-bottom:1px solid #f1f5f9'>
          <td style='padding:8px 10px;font-weight:700;color:#16a34a'>DP</td>
          <td style='padding:8px 10px'>Dupla Ponderação</td>
          <td style='padding:8px 10px;color:#6b7280'>4467</td>
          <td style='padding:8px 10px'>Recalcula o peso de cada item na cesta do IPCA 
          com base em duas dimensões: o <strong>peso original</strong> do item e a 
          <strong>inversa da volatilidade histórica</strong> de sua variação de preços. 
          Itens mais voláteis recebem peso menor, sem necessidade de exclusão.</td>
        </tr>
        <tr style='border-bottom:1px solid #f1f5f9'>
          <td style='padding:8px 10px;font-weight:700;color:#d97706'>EX</td>
          <td style='padding:8px 10px'>Exclusão</td>
          <td style='padding:8px 10px;color:#6b7280'>11427</td>
          <td style='padding:8px 10px'>Exclui sistematicamente dois subgrupos: 
          <strong>alimentação no domicílio</strong> (altamente volátil, sujeita a choques 
          climáticos) e <strong>preços administrados</strong> (energia, combustíveis, tarifas), 
          que dependem de decisões regulatórias. Reflete a inflação de mercado "livre".</td>
        </tr>
        <tr>
          <td style='padding:8px 10px;font-weight:700;color:#7c3aed'>P55</td>
          <td style='padding:8px 10px'>Percentil 55</td>
          <td style='padding:8px 10px;color:#6b7280'>28750</td>
          <td style='padding:8px 10px'>Calcula a variação no <strong>percentil 55 da 
          distribuição</strong> das variações dos itens (ponderadas pelos seus pesos na 
          cesta). Ao usar a mediana deslocada para cima, captura a pressão inflacionária 
          de forma robusta a outliers sem precisar definir regras de exclusão.</td>
        </tr>
      </tbody>
    </table>

    <p style='margin:14px 0 0;font-size:11px;color:#9ca3af'>
    Fonte: Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS). 
    Dados referentes à variação mensal (% ao mês) e ao acumulado em 12 meses (% a.a.). 
    Atualização mensal, geralmente na semana seguinte à divulgação do IPCA pelo IBGE.
    </p>

    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MERCADOS GLOBAIS — Terminal financeiro
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Mercados Globais":
    page_header("Mercados Globais")

    st.markdown("""<style>
    .terminal-cat{font-size:9px;font-weight:800;color:#6b7280;text-transform:uppercase;
                  letter-spacing:2.5px;margin:0 0 8px 2px;display:block}
    .tile{border-radius:6px;padding:10px 12px 9px}
    .tile-name{font-size:9px;font-weight:800;color:rgba(255,255,255,.55);
               text-transform:uppercase;letter-spacing:1.2px;margin-bottom:5px;
               white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tile-price{font-size:20px;font-weight:700;color:#fff;
                line-height:1.1;margin-bottom:6px;white-space:nowrap}
    .tile-hl{font-size:9.5px;font-weight:500;display:flex;
             justify-content:space-between;margin-bottom:2px}
    .tile-chg{font-size:9.5px;font-weight:700;display:flex;justify-content:space-between}
    .up {background:#14522c}
    .dn {background:#7f1d1d}
    .neu{background:#1e2535}
    .up  .tile-hl,.up  .tile-chg{color:#86efac}
    .dn  .tile-hl,.dn  .tile-chg{color:#fca5a5}
    .neu .tile-hl,.neu .tile-chg{color:#94a3b8}
    .tile-closed{font-size:8px;background:rgba(0,0,0,.3);border-radius:3px;
                 padding:1px 5px;color:rgba(255,255,255,.45);margin-left:5px;
                 font-weight:600;vertical-align:middle}
    </style>""", unsafe_allow_html=True)

    def _tfmt(v, unit):
        if v is None: return "—"
        if unit == "pts":
            if v >= 10000: return f"{v:,.0f}".replace(",",".")
            return f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        dec = 4 if unit == "R$" else 2
        return f"{v:,.{dec}f}".replace(",","X").replace(".",",").replace("X",".")

    def _tile_html(nome, d, unit):
        price  = d.get("price")
        chg_p  = d.get("chg_p")
        chg_v  = d.get("chg_v")
        dh     = d.get("day_high")
        dl     = d.get("day_low")
        closed = d.get("is_closed", False)
        if price is None:
            return (f"<div class='tile neu'>"
                    f"<div class='tile-name'>{nome}</div>"
                    f"<div class='tile-price' style='opacity:.4'>—</div>"
                    f"</div>")
        cls   = "up" if (chg_p or 0) >= 0 else "dn"
        arrow = "▲" if (chg_p or 0) >= 0 else "▼"
        px    = "R$ " if unit == "R$" else ("US$ " if "US$" in unit else "")
        p_str = f"{px}{_tfmt(price, unit)}"
        v_str = (f"{'+' if chg_v >= 0 else ''}{_tfmt(chg_v, unit)}" if chg_v is not None else "—")
        c_str = (f"{'+' if chg_p >= 0 else ''}{chg_p:.2f}%".replace(".",",") if chg_p is not None else "—")
        h_str = f"H {_tfmt(dh, unit)}" if dh else "H —"
        l_str = f"L {_tfmt(dl, unit)}" if dl else "L —"
        badge = "<span class='tile-closed'>FEC</span>" if closed else ""
        return (
            f"<div class='tile {cls}'>"
            f"<div class='tile-name'>{nome}{badge}</div>"
            f"<div class='tile-price'>{p_str}</div>"
            f"<div class='tile-hl'><span>{h_str}</span><span>{v_str} {arrow}</span></div>"
            f"<div class='tile-chg'><span>{l_str}</span><span>{c_str}</span></div>"
            f"</div>"
        )

    def _group(label, ativos_list):
        st.markdown(f"<span class='terminal-cat'>{label}</span>", unsafe_allow_html=True)
        cols = st.columns(len(ativos_list))
        for col, nome in zip(cols, ativos_list):
            sym, unit, _ = GLOBAL[nome]
            with col:
                st.markdown(_tile_html(nome, get_quote(sym), unit), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    with st.spinner("Carregando cotações..."):
        _group("Índices", ["IBOVESPA","S&P 500","Nasdaq 100","Dow Jones","FTSE 100","DAX"])
        c_en, c_me = st.columns([2, 3])
        with c_en:
            _group("Energia", ["Petróleo Brent","Petróleo WTI"])
        with c_me:
            _group("Metais", ["Ouro","Prata","Cobre"])
        c_fx, c_cr = st.columns([2, 2])
        with c_fx:
            _group("Câmbio", ["Dólar (USD/BRL)","Euro (EUR/BRL)"])
        with c_cr:
            _group("Cripto", ["Bitcoin","Ethereum"])

    ts_now = now_brt().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(
        f"<div style='text-align:right;font-size:10px;color:#6b7280;margin-top:4px'>"
        f"Atualizado: {ts_now} BRT &nbsp;·&nbsp; ↻ 60s</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    sec_title("Histórico Interativo", "2 anos", "badge-daily")

    hist_ativos = {
        "IBOVESPA":        ("^BVSP",   "#0891b2", "pts"),
        "S&P 500":         ("^GSPC",   "#16a34a", "pts"),
        "Petróleo Brent":  ("BZ=F",    "#d97706", "US$"),
        "Ouro":            ("GC=F",    "#b45309", "US$"),
        "Dólar (USD/BRL)": ("USDBRL=X","#7c3aed", "R$"),
        "Bitcoin":         ("BTC-USD", "#f59e0b", "US$"),
    }
    tabs_hist = st.tabs(list(hist_ativos.keys()))
    for tab, (nome_h, (sym_h, cor_h, unit_h)) in zip(tabs_hist, hist_ativos.items()):
        with tab:
            dfh = get_hist(sym_h, 2)
            if not dfh.empty:
                st.plotly_chart(
                    line_fig(dfh, f"{nome_h} — 2 anos", cor_h,
                             suffix=f" {unit_h}", height=320, inter=True),
                    use_container_width=True,
                    config={**CHART_CFG_INT,
                            "toImageButtonOptions": {"format":"png","filename":nome_h,"scale":2}},
                )

    time.sleep(60)
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Gráficos":
    page_header("Gráficos")
    t1,t2=st.tabs(["BCB — Indicadores Brasil","Yahoo Finance — Ativos Globais"])
    with t1:
        PERIODOS = {
            "Selic":       ["Original"],
            "IPCA":        ["Mensal (original)","Acumulado 12M","Acumulado no ano"],
            "IBC-Br":      ["Nível (original)","Var. mensal (m/m)","Var. trimestral (t/t)","Var. anual (a/a)"],
            "Dólar PTAX":  ["Original"],
            "PIB":         ["Var. trimestral (original)","Var. anual (a/a)","Acumulado 4 trimestres"],
            "Desemprego":  ["Original"],
            "IGP-M":       ["Mensal (original)","Acumulado 12M"],
            "IPCA-15":     ["Mensal (original)","Acumulado 12M"],
            "Exportações": ["Original","Var. mensal (m/m)","Var. anual (a/a)"],
            "Importações": ["Original","Var. mensal (m/m)","Var. anual (a/a)"],
            "Dívida/PIB":  ["Original","Var. mensal (m/m)"],
        }
        col1, col2 = st.columns([2, 2])
        with col1: ind = st.selectbox("Indicador", list(SGS.keys()), key="gind")
        opts = PERIODOS.get(ind, ["Original"])
        with col2:
            periodo = st.selectbox("Período / Transformação", opts, key="gperiodo") if len(opts) > 1 else opts[0]

        cod, unit, freq, tipo = SGS[ind]
        with st.spinner(f"Carregando {ind}..."): df_f = get_bcb_full(cod)
        if df_f.empty:
            st.warning("⚠️ API BCB temporariamente indisponível.")
        else:
            df_t, unit_t = aplicar_periodo(df_f, periodo, ind)
            if not unit_t: unit_t = unit
            label_t = f"{ind} — {periodo}" if periodo not in ("Original","Mensal (original)","Nível (original)","Var. trimestral (original)") else f"{ind} ({unit_t})"
            dmin = df_t["data"].min().date(); dmax = df_t["data"].max().date()
            st.markdown(
                f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px'>"
                f"Disponível: <strong>{dmin.strftime('%d/%m/%Y')}</strong> → "
                f"<strong>{dmax.strftime('%d/%m/%Y')}</strong> · {len(df_t)} obs. · "
                f"<em>Série completa carregada</em></div>",
                unsafe_allow_html=True,
            )
            from datetime import date as _date
            _d24 = max(dmin, _date(dmax.year - 2, dmax.month, dmax.day))
            c2, c3 = st.columns(2)
            with c2: d_ini = st.date_input("Exibir de", value=_d24, min_value=dmin, max_value=dmax, key="gini")
            with c3: d_fim = st.date_input("Exibir até", value=dmax, min_value=dmin, max_value=dmax, key="gfim")
            if d_ini < d_fim:
                st.success(f"✅ {len(df_t)} obs. · {label_t} · {freq}")
                use_bar = (tipo == "bar") and (periodo in ("Original","Mensal (original)","Var. trimestral (original)"))
                if use_bar:
                    fig = bar_fig(df_t, label_t, suffix=f" {unit_t}", height=440, inter=True)
                else:
                    fig = line_fig(df_t, label_t, "#004031", suffix=f" {unit_t}", height=440, inter=True)
                fig.update_xaxes(range=[str(d_ini), str(d_fim)])
                st.plotly_chart(fig, use_container_width=True, config={**CHART_CFG_INT,
                    "toImageButtonOptions": {"format":"png","filename":f"{ind}_{periodo}","scale":2}})
                dlo = df_t.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                st.download_button(
                    f"💾 Baixar CSV ({len(dlo)} linhas)",
                    data=dlo.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{ind.replace(' ','_')}_{periodo.replace(' ','_')}.csv",
                    mime="text/csv",
                )
    with t2:
        co1, _ = st.columns([2, 3])
        with co1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="gativo")
        sym, unit, _ = GLOBAL[ativo]
        with st.spinner(f"Carregando {ativo}..."): dfg = get_hist(sym, years=10)
        if not dfg.empty:
            dmin_y = dfg["data"].min().date(); dmax_y = dfg["data"].max().date()
            from datetime import date as _date2
            _d24y = max(dmin_y, _date2(dmax_y.year - 2, dmax_y.month, dmax_y.day))
            st.markdown(
                f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px'>"
                f"Disponível: <strong>{dmin_y.strftime('%d/%m/%Y')}</strong> → "
                f"<strong>{dmax_y.strftime('%d/%m/%Y')}</strong> · {len(dfg)} obs. · "
                f"<em>Série completa carregada</em></div>",
                unsafe_allow_html=True,
            )
            cy1, cy2 = st.columns(2)
            with cy1: dy_ini = st.date_input("Exibir de", value=_d24y, min_value=dmin_y, max_value=dmax_y, key="gyini")
            with cy2: dy_fim = st.date_input("Exibir até", value=dmax_y, min_value=dmin_y, max_value=dmax_y, key="gyfim")
            if dy_ini < dy_fim:
                st.success(f"✅ {len(dfg)} obs. carregadas · {ativo}")
                fig_y = line_fig(dfg, f"{ativo}", "#004031", suffix=f" {unit}", height=440, inter=True)
                fig_y.update_xaxes(range=[str(dy_ini), str(dy_fim)])
                st.plotly_chart(fig_y, use_container_width=True, config={**CHART_CFG_INT,
                    "toImageButtonOptions": {"format":"png","filename":f"{ativo}","scale":2}})
                dlo = dfg.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                st.download_button(
                    f"💾 Baixar CSV completo ({len(dlo)} linhas)",
                    data=dlo.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{ativo.replace(' ','_')}_completo.csv",
                    mime="text/csv",
                )
        else: st.warning("Sem dados disponíveis.")

# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ══════════════════════════════════════════════════════════════════════════════
else:
    page_header("Exportar Dados")
    fonte = st.radio("Fonte:", ["BCB/SGS — Brasil", "Yahoo Finance — Globais"], horizontal=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if fonte == "BCB/SGS — Brasil":
        _PERIODOS_EXP = {
            "Selic":       ["Original"],
            "IPCA":        ["Mensal (original)", "Acumulado 12M", "Acumulado no ano"],
            "IBC-Br":      ["Nível (original)", "Var. mensal (m/m)", "Var. trimestral (t/t)", "Var. anual (a/a)"],
            "Dólar PTAX":  ["Original"],
            "PIB":         ["Var. trimestral (original)", "Var. anual (a/a)", "Acumulado 4 trimestres"],
            "Desemprego":  ["Original"],
            "IGP-M":       ["Mensal (original)", "Acumulado 12M"],
            "IPCA-15":     ["Mensal (original)", "Acumulado 12M"],
            "Exportações": ["Original", "Var. mensal (m/m)", "Var. anual (a/a)"],
            "Importações": ["Original", "Var. mensal (m/m)", "Var. anual (a/a)"],
            "Dívida/PIB":  ["Original", "Var. mensal (m/m)"],
        }
        c1, c2 = st.columns([2, 2])
        with c1: ind = st.selectbox("Indicador", list(SGS.keys()), index=1, key="eind")
        opts_e = _PERIODOS_EXP.get(ind, ["Original"])
        with c2:
            periodo_e = st.selectbox("Período / Transformação", opts_e, key="eperiodo") if len(opts_e) > 1 else opts_e[0]
        c3, c4 = st.columns(2)
        with c3: d_ini = st.date_input("De", value=datetime.today() - timedelta(days=365*5), key="eini")
        with c4: d_fim = st.date_input("Até", value=datetime.today(), key="efim")
        modo = st.radio("Dados:", ["Filtrar pelo intervalo acima", "Série completa desde o início"],
                        horizontal=True, key="emodo")
        if st.button("Gerar CSV", type="primary", key="ebtn"):
            cod, unit, freq, _ = SGS[ind]
            with st.spinner(f"Carregando {ind}..."):
                if "completa" in modo:
                    dfe = get_bcb_full(cod)
                else:
                    dfe = get_bcb_range(cod, d_ini.strftime("%d/%m/%Y"), d_fim.strftime("%d/%m/%Y"))
            if dfe.empty:
                st.warning("Nenhum dado encontrado.")
            else:
                dfe2, unit_t = aplicar_periodo(dfe, periodo_e, ind)
                if not unit_t: unit_t = unit
                if dfe2.empty:
                    st.warning("Transformação resultou em série vazia (poucos dados).")
                else:
                    label_e = f"{ind} — {periodo_e}" if periodo_e not in ("Original","Mensal (original)","Nível (original)","Var. trimestral (original)") else ind
                    dlo = dfe2.copy()
                    dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                    col_val = f"Valor ({unit_t})"
                    st.success(f"✅ {len(dlo)} registros — {label_e}")
                    st.dataframe(
                        dlo.rename(columns={"data": "Data", "valor": col_val}),
                        use_container_width=True,
                        height=min(400, 46 + len(dlo) * 35),
                    )
                    nome = f"{ind.replace(' ','_')}_{periodo_e.replace(' ','_').replace('/','')}.csv"
                    st.download_button(
                        f"💾 Baixar {nome}",
                        data=dlo.to_csv(index=False).encode("utf-8-sig"),
                        file_name=nome,
                        mime="text/csv",
                    )
    else:
        co1, co2 = st.columns([2, 1])
        with co1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="eativo")
        with co2: anos = st.select_slider("Período (anos)", [1, 2, 3, 5, 10], value=5, key="eanos")
        if st.button("Gerar CSV", type="primary", key="ebtn2"):
            sym, unit, _ = GLOBAL[ativo]
            with st.spinner(f"Buscando {ativo}..."): dfe = get_hist(sym, anos)
            if dfe.empty:
                st.warning("Sem dados disponíveis.")
            else:
                dlo = dfe.copy(); dlo["data"] = dlo["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ {len(dlo)} registros — {ativo}")
                st.dataframe(
                    dlo.rename(columns={"data": "Data", "valor": f"Valor ({unit})"}),
                    use_container_width=True,
                    height=min(400, 46 + len(dlo) * 35),
                )
                nome = f"{ativo.replace(' ','_')}_{anos}anos.csv"
                st.download_button(
                    f"💾 Baixar {nome}",
                    data=dlo.to_csv(index=False).encode("utf-8-sig"),
                    file_name=nome,
                    mime="text/csv",
                )

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    lbl = "▲  Ocultar indicadores e ativos" if st.session_state.tabela_aberta else "▼  Ver todos os indicadores e ativos disponíveis"
    if st.button(lbl, key="btn_tabela", use_container_width=False):
        st.session_state.tabela_aberta = not st.session_state.tabela_aberta
        st.rerun()

    if st.session_state.tabela_aberta:
        with st.container():
            st.markdown(
                "<div style='background:#fff;border:1px solid #e2e5e9;border-radius:12px;padding:20px 24px;margin-top:4px'>",
                unsafe_allow_html=True,
            )
            st.markdown("**BCB/SGS — Indicadores Brasil**")
            df_sgs = pd.DataFrame([{
                "Indicador": k,
                "Cód. SGS": v[0],
                "Unidade": v[1],
                "Freq.": v[2],
                "Transformações disponíveis": ", ".join({
                    "Selic":       ["Original"],
                    "IPCA":        ["Mensal","Acum. 12M","Acum. ano"],
                    "IBC-Br":      ["Nível","m/m","t/t","a/a"],
                    "Dólar PTAX":  ["Original"],
                    "PIB":         ["Trimestral","a/a","Acum. 4 tri"],
                    "Desemprego":  ["Original"],
                    "IGP-M":       ["Mensal","Acum. 12M"],
                    "IPCA-15":     ["Mensal","Acum. 12M"],
                    "Exportações": ["Original","m/m","a/a"],
                    "Importações": ["Original","m/m","a/a"],
                    "Dívida/PIB":  ["Original","m/m"],
                }.get(k, ["Original"]))
            } for k, v in SGS.items()])
            st.dataframe(df_sgs, hide_index=True, use_container_width=True, height=46 + len(df_sgs)*35)
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.markdown("**Yahoo Finance — Ativos Globais**")
            df_yf = pd.DataFrame([{
                "Ativo": k, "Símbolo": v[0], "Unidade": v[1],
                "Tipo": ("Câmbio" if "BRL" in v[0] else "Índice" if v[0].startswith("^") else
                         "Commodity" if v[0] in ("BZ=F","CL=F","GC=F","SI=F","HG=F") else "Cripto")
            } for k, v in GLOBAL.items()])
            st.dataframe(df_yf, hide_index=True, use_container_width=True, height=46 + len(df_yf)*35)
            st.markdown("</div>", unsafe_allow_html=True)
