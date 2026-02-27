import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Macro Brasil",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Desativa fade/transição de página ── */
[data-testid="stMain"],
[data-testid="stAppViewContainer"],
[data-testid="stVerticalBlock"] {
    animation: none !important;
    transition: none !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #080c14 !important;
    border-right: 1px solid #131929;
    min-width: 220px !important;
    max-width: 220px !important;
}
section[data-testid="stSidebar"] .stRadio > div {
    gap: 2px !important;
}
section[data-testid="stSidebar"] .stRadio label {
    display: flex !important;
    align-items: center !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #64748b !important;
    cursor: pointer !important;
    transition: background 0.15s, color 0.15s !important;
    margin: 1px 0 !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: #0f1424 !important;
    color: #94a3b8 !important;
}
section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    font-size: 13px !important;
}
/* Radio selecionado */
section[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: #0f1e3d !important;
    color: #818cf8 !important;
}

/* ── Main container ── */
.main .block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px; }
footer, #MainMenu { visibility: hidden; }

/* ── Títulos de seção ── */
.sec-title {
    font-size: 10px; font-weight: 700; color: #374151;
    text-transform: uppercase; letter-spacing: 2.5px;
    border-bottom: 1px solid #131929; padding-bottom: 7px; margin: 14px 0 14px 0;
}
.sec-label {
    font-size: 9px; font-weight: 700; color: #1e2640;
    text-transform: uppercase; letter-spacing: 2.5px;
    margin: 18px 0 6px 0; padding-left: 2px;
}

/* ── Badges ── */
.badge-live  { display:inline-block;background:#052e16;border:1px solid #166534;
               color:#4ade80;font-size:9px;padding:1px 7px;border-radius:20px;margin-left:6px; }
.badge-daily { display:inline-block;background:#1e1b4b;border:1px solid #3730a3;
               color:#818cf8;font-size:9px;padding:1px 7px;border-radius:20px;margin-left:6px; }

/* ── Botões ── */
.stDownloadButton > button {
    background:#1d4ed8 !important; color:white !important;
    border:none !important; border-radius:8px !important; font-weight:600 !important;
}
.stButton > button[kind="primary"] {
    background: #6366f1 !important; border: none !important;
    border-radius: 8px !important; font-weight: 600 !important;
}

/* ── Expander ── */
div[data-testid="stExpander"] { border:1px solid #131929 !important; border-radius:10px !important; }

/* ── Tabs (para página de gráficos) ── */
div[data-testid="stTabs"] [data-testid="stTabsTabList"] {
    border-bottom: 1px solid #131929 !important;
    gap: 4px;
}
div[data-testid="stTabs"] button[role="tab"] {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    padding: 6px 16px !important;
    border-radius: 8px 8px 0 0 !important;
    border: 1px solid transparent !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #818cf8 !important;
    border-color: #131929 !important;
    border-bottom-color: #0f1117 !important;
    background: #0f1117 !important;
}

/* ── Page header bar ── */
.page-header {
    display: flex; justify-content: space-between; align-items: flex-end;
    border-bottom: 1px solid #131929; padding-bottom: 12px; margin-bottom: 18px;
}
.page-header h2 { font-size: 20px; font-weight: 700; color: #e2e8f0; margin: 0; }
.page-header .ts { font-size: 10px; color: #2d3748; text-align: right; line-height: 1.6; }
.page-header .ts b { color: #4b5a7a; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE   = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
YAHOO_SNAP = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=7d"
YAHOO_HIST = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range={y}y"
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

SGS = {
    "Selic":       (432,   "% a.a.",  "Mensal",      "line"),
    "IPCA":        (433,   "% mês",   "Mensal",      "bar"),
    "IBC-Br":      (24363, "índice",  "Mensal",      "line"),
    "Dólar PTAX":  (1,     "R$",      "Diário",      "line"),
    "PIB":         (4380,  "% trim.", "Trimestral",  "bar"),
    "Desemprego":  (24369, "%",       "Trimestral",  "line"),
    "IGP-M":       (189,   "% mês",   "Mensal",      "bar"),
    "IPCA-15":     (7478,  "% mês",   "Mensal",      "bar"),
    "Exportações": (2257,  "US$ mi",  "Mensal",      "bar"),
    "Importações": (2258,  "US$ mi",  "Mensal",      "bar"),
    "Dívida/PIB":  (4513,  "%",       "Mensal",      "line"),
}

GLOBAL = {
    "IBOVESPA":        ("^BVSP",    "pts",   "🇧🇷", False),
    "Dólar (USD/BRL)": ("USDBRL=X", "R$",    "💵",  True),
    "Euro (EUR/BRL)":  ("EURBRL=X", "R$",    "💶",  True),
    "S&P 500":         ("^GSPC",    "pts",   "🇺🇸", False),
    "Nasdaq 100":      ("^NDX",     "pts",   "🇺🇸", False),
    "Dow Jones":       ("^DJI",     "pts",   "🇺🇸", False),
    "FTSE 100":        ("^FTSE",    "pts",   "🇬🇧", False),
    "DAX":             ("^GDAXI",   "pts",   "🇩🇪", False),
    "Petróleo Brent":  ("BZ=F",     "US$",   "🛢️",  True),
    "Petróleo WTI":    ("CL=F",     "US$",   "🛢️",  True),
    "Ouro":            ("GC=F",     "US$",   "🥇",  False),
    "Prata":           ("SI=F",     "US$",   "🥈",  False),
    "Cobre":           ("HG=F",     "US$/lb","🪙",  True),
    "Bitcoin":         ("BTC-USD",  "US$",   "₿",   False),
    "Ethereum":        ("ETH-USD",  "US$",   "Ξ",   False),
}

CHART_CFG = {
    "displayModeBar": False,
    "staticPlot": False,
    "scrollZoom": False,
}

PLOT_BASE = dict(
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#0a0e1a",
    font_color="#6b7fa8",
    font_family="Inter",
    margin=dict(l=0, r=4, t=38, b=0),
    xaxis=dict(
        gridcolor="#131929", showline=False,
        tickfont=dict(size=10), zeroline=False,
        fixedrange=False,
    ),
    yaxis=dict(
        gridcolor="#131929", showline=False,
        tickfont=dict(size=10), zeroline=False,
        fixedrange=False,
    ),
    title_font=dict(color="#94a3b8", size=13),
    hoverlabel=dict(bgcolor="#1e2640", font_size=12),
    dragmode="pan",
)

# ─── UTILS ───────────────────────────────────────────────────────────────────
def hex_rgba(h, a=0.12):
    h = h.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{a})"

def fmt(v, dec=2):
    if v is None: return "—"
    s = f"{v:,.{dec}f}"
    parts = s.split(".")
    integer = parts[0].replace(",", ".")
    decimal = parts[1] if len(parts) > 1 else ""
    return f"{integer},{decimal}" if decimal else integer

def parse_bcb_valor(valor_str):
    if valor_str is None:
        return None
    s = str(valor_str).strip()
    s = s.replace("\xa0", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "")
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

# ─── BCB API ─────────────────────────────────────────────────────────────────
def _bcb_request(url: str) -> list:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            return []
        data = r.json()
        if isinstance(data, dict):
            return []
        if not isinstance(data, list) or len(data) == 0:
            return []
        return data
    except Exception:
        return []

def _build_df(raw: list) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["data", "valor"])
    df = pd.DataFrame(raw)
    if "data" not in df.columns or "valor" not in df.columns:
        return pd.DataFrame(columns=["data", "valor"])
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = df["valor"].apply(parse_bcb_valor)
    df = df.dropna(subset=["data", "valor"])
    df = df.sort_values("data").reset_index(drop=True)
    return df[["data", "valor"]]

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb(codigo: int, ultimos: int) -> pd.DataFrame:
    url = BCB_BASE.format(codigo=codigo) + f"/ultimos/{ultimos}?formato=json"
    return _build_df(_bcb_request(url))

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb_full(codigo: int) -> pd.DataFrame:
    url = BCB_BASE.format(codigo=codigo) + "?formato=json"
    return _build_df(_bcb_request(url))

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb_range(codigo: int, ini: str, fim: str) -> pd.DataFrame:
    url = (BCB_BASE.format(codigo=codigo)
           + f"?formato=json&dataInicial={ini}&dataFinal={fim}")
    return _build_df(_bcb_request(url))

# ─── YAHOO FINANCE ────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def get_quote(symbol: str) -> dict:
    try:
        url   = YAHOO_SNAP.format(sym=symbol)
        r     = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        data  = r.json()
        result = data["chart"]["result"][0]
        meta  = result["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        chg_p = ((price - prev) / prev * 100) if (prev and price and prev != 0) else None
        chg_v = (price - prev) if (prev and price) else None
        market = meta.get("marketState", "CLOSED")
        ts    = result.get("timestamp", [])
        last_d = datetime.fromtimestamp(ts[-1]).strftime("%d/%m/%Y") if ts else None
        return {"price": price, "prev": prev, "chg_p": chg_p, "chg_v": chg_v,
                "market": market, "last_date": last_d}
    except:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(symbol: str, years: int = 5) -> pd.DataFrame:
    try:
        url  = YAHOO_HIST.format(sym=symbol, y=years)
        r    = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        res  = data["chart"]["result"][0]
        ts   = res["timestamp"]
        vals = res["indicators"]["quote"][0]["close"]
        df   = pd.DataFrame({"data": pd.to_datetime(ts, unit="s"), "valor": vals})
        return df.dropna().reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data", "valor"])

# ─── KPI CARD ─────────────────────────────────────────────────────────────────
import streamlit.components.v1 as components

def kpi(label, value, chg_p=None, sub="", invert=False, closed=False, close_date=None):
    if chg_p is not None:
        up  = (chg_p >= 0) if not invert else (chg_p < 0)
        cls = "pos" if up else "neg"
        arr = "▲" if chg_p >= 0 else "▼"
        dlt = f'<div class="d-{cls}">{arr} {abs(chg_p):.2f}%</div>'
    else:
        dlt = '<div class="d-neu">—</div>'

    badge = ""
    if closed and close_date:
        badge = f'<div class="cb">Fechamento {close_date}</div>'
    elif closed:
        badge = '<div class="cb">Último fechamento</div>'

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:'Inter',sans-serif}}
.card{{background:linear-gradient(135deg,#0f1424,#161d30);border:1px solid #1e2640;
       border-radius:14px;padding:16px;text-align:center;height:118px;
       display:flex;flex-direction:column;justify-content:center;gap:3px}}
.lbl{{font-size:9px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1.6px}}
.val{{font-size:20px;font-weight:800;color:#e2e8f0;line-height:1.15}}
.d-pos{{font-size:11px;color:#4ade80}}
.d-neg{{font-size:11px;color:#f87171}}
.d-neu{{font-size:11px;color:#2a3050}}
.sub{{font-size:9px;color:#334155}}
.cb{{font-size:9px;color:#92400e;background:#1c1208;border:1px solid #451a03;
     display:inline-block;padding:1px 7px;border-radius:10px;margin-top:2px}}
</style></head><body>
<div class="card">
  <div class="lbl">{label}</div>
  <div class="val">{value}</div>
  {dlt}
  <div class="sub">{sub}</div>
  {badge}
</div></body></html>"""
    components.html(html, height=126)

# ─── CHART FACTORIES ──────────────────────────────────────────────────────────
def _apply_fixed_axes(fig, df, suffix="", pad_pct=0.08):
    if df.empty:
        return fig
    y_min = df["valor"].min()
    y_max = df["valor"].max()
    y_pad = (y_max - y_min) * pad_pct if (y_max - y_min) > 0 else abs(y_max) * 0.1 or 1
    x_min = df["data"].min()
    x_max = df["data"].max()
    x_pad = (x_max - x_min) * 0.02
    fig.update_xaxes(range=[x_min - x_pad, x_max + x_pad])
    fig.update_yaxes(
        range=[y_min - y_pad, y_max + y_pad],
        tickformat=".2f",
        ticksuffix=suffix.strip() if suffix.strip() else "",
    )
    return fig

def line_fig(df, title, color="#6366f1", fill=True, suffix="", height=260, fixed_axes=True):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=4, color=color),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_rgba(color, 0.10),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**PLOT_BASE, title=title, height=height)
    if fixed_axes:
        fig = _apply_fixed_axes(fig, df, suffix)
    return fig

def bar_fig(df, title, suffix="", height=260, fixed_axes=True):
    colors = ["#4ade80" if v >= 0 else "#f87171" for v in df["valor"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=colors, marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**PLOT_BASE, title=title, height=height)
    if fixed_axes:
        fig = _apply_fixed_axes(fig, df, suffix, pad_pct=0.15)
    return fig

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding:14px 4px 10px 4px;display:flex;align-items:center;gap:8px'>"
        "<span style='font-size:20px'>🇧🇷</span>"
        "<span style='font-size:15px;font-weight:700;color:#94a3b8;letter-spacing:0.3px'>Macro Brasil</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:2px;background:#131929;margin-bottom:12px'></div>",
                unsafe_allow_html=True)

    st.markdown("<div class='sec-label'>NAVEGAÇÃO</div>", unsafe_allow_html=True)
    pagina = st.radio(
        "nav",
        options=["🏠  Início", "🌍  Mercados Globais", "📈  Gráficos", "📥  Exportar"],
        label_visibility="collapsed",
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("<div style='height:2px;background:#131929'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:9px;color:#1e2640;line-height:2;padding:10px 4px 0 4px'>"
        "Fontes:<br>• BCB/SGS<br>• Yahoo Finance<br><br>"
        "Mercados: ↻ 60s<br>BCB: ↻ 1h"
        "</div>",
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# 🏠 INÍCIO
# ═════════════════════════════════════════════════════════════════════════════
if pagina == "🏠  Início":

    # ── Header ───────────────────────────────────────────────────────────────
    col_t, col_h = st.columns([5, 1])
    with col_t:
        st.markdown("<h2 style='margin:0;color:#e2e8f0'>🇧🇷 Dashboard Macro Brasil</h2>",
                    unsafe_allow_html=True)
    with col_h:
        st.markdown(
            f"<div style='text-align:right;color:#2d3748;font-size:10px;padding-top:10px'>"
            f"Atualizado<br><b style='color:#4b5a7a'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:2px;background:#131929;margin:10px 0 18px 0'></div>",
                unsafe_allow_html=True)

    # ── Carregamento de dados ─────────────────────────────────────────────────
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

    # ── KPIs Mercado ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Indicadores de Mercado'
        '<span class="badge-live">↻ 60s</span></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        v = ibov_d.get("price")
        closed = ibov_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Ibovespa",
            fmt(v, 0) + " pts" if v else "—",
            ibov_d.get("chg_p"),
            f"Var. dia: {fmt(ibov_d.get('chg_v'), 0)} pts" if ibov_d.get("chg_v") is not None else "—",
            closed=closed, close_date=ibov_d.get("last_date"))
    with c2:
        v = usd_d.get("price")
        closed = usd_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Dólar (USD/BRL)",
            f"R$ {fmt(v, 4)}" if v else "—",
            usd_d.get("chg_p"),
            f"Ant.: R$ {fmt(usd_d.get('prev'), 4)}" if v else "—",
            invert=True, closed=closed, close_date=usd_d.get("last_date"))
    with c3:
        v = eur_d.get("price")
        closed = eur_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Euro (EUR/BRL)",
            f"R$ {fmt(v, 4)}" if v else "—",
            eur_d.get("chg_p"),
            f"Ant.: R$ {fmt(eur_d.get('prev'), 4)}" if v else "—",
            invert=True, closed=closed, close_date=eur_d.get("last_date"))

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── KPIs Econômicos ───────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Indicadores Econômicos'
        '<span class="badge-daily">↻ diário</span></div>',
        unsafe_allow_html=True,
    )
    c4, c5, c6 = st.columns(3)
    with c4:
        if not df_sel.empty:
            v   = df_sel["valor"].iloc[-1]
            ref = df_sel["data"].iloc[-1].strftime("%b/%Y")
            kpi("Selic", f"{fmt(v)}% a.a.", sub=f"Ref: {ref}")
        else:
            kpi("Selic", "—", sub="BCB indisponível")
    with c5:
        if not df_ipca.empty:
            v   = df_ipca["valor"].iloc[-1]
            ref = df_ipca["data"].iloc[-1].strftime("%b/%Y")
            delta = (df_ipca["valor"].iloc[-1] - df_ipca["valor"].iloc[-2]) if len(df_ipca) >= 2 else None
            kpi("IPCA", f"{fmt(v)}% mês", chg_p=float(delta) if delta is not None else None, sub=f"Ref: {ref}")
        else:
            kpi("IPCA", "—", sub="BCB indisponível")
    with c6:
        if not df_des.empty:
            v   = df_des["valor"].iloc[-1]
            ref = df_des["data"].iloc[-1].strftime("%b/%Y")
            kpi("Desemprego (PNAD)", f"{fmt(v)}%", sub=f"Ref: {ref}")
        else:
            kpi("Desemprego (PNAD)", "—", sub="BCB indisponível")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Gráficos — 12 meses ───────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Histórico — 12 meses '
        '<span style="font-size:9px;color:#2d3748;font-weight:400">'
        '→ série completa em Gráficos</span></div>',
        unsafe_allow_html=True,
    )

    ca, cb = st.columns(2)
    with ca:
        if not df_sel.empty:
            st.plotly_chart(
                line_fig(df_sel, "Selic (% a.a.)", "#6366f1", suffix="%"),
                use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ Selic: indisponível no momento.")
    with cb:
        if not df_ipca.empty:
            st.plotly_chart(
                bar_fig(df_ipca, "IPCA (% ao mês)", suffix="%"),
                use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ IPCA: indisponível no momento.")

    cc, cd = st.columns(2)
    with cc:
        df_cam30 = df_cam.tail(30) if not df_cam.empty else df_cam
        if not df_cam30.empty:
            st.plotly_chart(
                line_fig(df_cam30, "Dólar PTAX — 30 dias úteis (R$)", "#f59e0b", suffix=" R$"),
                use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ Dólar PTAX: indisponível no momento.")
    with cd:
        if not df_ibc.empty:
            st.plotly_chart(
                line_fig(df_ibc, "IBC-Br", "#22d3ee", fill=False),
                use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ IBC-Br: indisponível no momento.")

    ce, cf = st.columns(2)
    with ce:
        if not df_pib.empty:
            st.plotly_chart(
                bar_fig(df_pib, "PIB — variação trimestral (%)", suffix="%"),
                use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ PIB: indisponível no momento.")
    with cf:
        if not df_des.empty:
            st.plotly_chart(
                line_fig(df_des, "Desemprego PNAD (%)", "#f87171", fill=True, suffix="%"),
                use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ Desemprego: indisponível no momento.")

    st.markdown(
        "<div style='text-align:center;color:#131929;font-size:10px;margin-top:16px'>"
        "Yahoo Finance (↻60s) • BCB/SGS (↻1h)"
        "</div>", unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# 🌍 MERCADOS GLOBAIS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "🌍  Mercados Globais":

    col_t, col_h = st.columns([5, 1])
    with col_t:
        st.markdown("<h2 style='margin:0;color:#e2e8f0'>🌍 Mercados Globais</h2>",
                    unsafe_allow_html=True)
    with col_h:
        st.markdown(
            f"<div style='text-align:right;color:#2d3748;font-size:10px;padding-top:10px'>"
            f"Atualizado<br><b style='color:#4b5a7a'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:2px;background:#131929;margin:10px 0 18px 0'></div>",
                unsafe_allow_html=True)

    grupos = {
        "🇧🇷 Brasil":      ["IBOVESPA","Dólar (USD/BRL)","Euro (EUR/BRL)"],
        "🇺🇸 Índices EUA": ["S&P 500","Nasdaq 100","Dow Jones"],
        "🌎 Europa":        ["FTSE 100","DAX"],
        "🛢️ Energia":      ["Petróleo Brent","Petróleo WTI"],
        "🥇 Metais":        ["Ouro","Prata","Cobre"],
        "₿ Cripto":         ["Bitcoin","Ethereum"],
    }

    for grupo, ativos in grupos.items():
        st.markdown(
            f'<div class="sec-title">{grupo}'
            '<span class="badge-live">↻ 60s</span></div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(ativos))
        for i, nome in enumerate(ativos):
            sym, unit, flag, inv = GLOBAL[nome]
            d = get_quote(sym)
            with cols[i]:
                v      = d.get("price")
                closed = d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
                prefix = "R$ " if unit == "R$" else ("US$ " if "US$" in unit else "")
                dec    = 0 if unit == "pts" else 2
                val_str = f"{prefix}{fmt(v, dec)}" if v else "—"
                kpi(f"{flag} {nome}", val_str, d.get("chg_p"),
                    sub=f"Ant.: {prefix}{fmt(d.get('prev'), dec)}" if v else "",
                    invert=inv, closed=closed, close_date=d.get("last_date"))
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sec-title">Histórico — 2 anos</div>', unsafe_allow_html=True)

    destaques = [
        ("IBOVESPA",       "^BVSP",  "#6366f1", "pts"),
        ("S&P 500",        "^GSPC",  "#22d3ee", "pts"),
        ("Petróleo Brent", "BZ=F",   "#f59e0b", "US$"),
        ("Ouro",           "GC=F",   "#fbbf24", "US$"),
    ]
    g1, g2 = st.columns(2)
    g3, g4 = st.columns(2)
    for col, (nome, sym, cor, unit) in zip([g1, g2, g3, g4], destaques):
        with col:
            df_h = get_hist(sym, years=2)
            if not df_h.empty:
                st.plotly_chart(
                    line_fig(df_h, f"{nome} — 2 anos", cor, fill=True, suffix=f" {unit}"),
                    use_container_width=True, config=CHART_CFG)
            else:
                st.info(f"{nome}: sem dados.")

    time.sleep(60)
    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# 📈 GRÁFICOS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "📈  Gráficos":

    col_t, col_h = st.columns([5, 1])
    with col_t:
        st.markdown("<h2 style='margin:0;color:#e2e8f0'>📈 Gráficos</h2>",
                    unsafe_allow_html=True)
    with col_h:
        st.markdown(
            f"<div style='text-align:right;color:#2d3748;font-size:10px;padding-top:10px'>"
            f"Série completa com filtro de período</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:2px;background:#131929;margin:10px 0 18px 0'></div>",
                unsafe_allow_html=True)

    tab_bcb, tab_yahoo = st.tabs(["📊 BCB — Indicadores Brasil", "🌍 Yahoo Finance — Ativos Globais"])

    # ── Tab BCB ───────────────────────────────────────────────────────────────
    with tab_bcb:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        col1, col2 = st.columns([2, 2])
        with col1:
            ind = st.selectbox("Indicador", list(SGS.keys()), key="graf_ind")
        with col2:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            st.caption("A série completa é carregada automaticamente. Ajuste o período abaixo.")

        cod, unit, freq, tipo = SGS[ind]

        # Sempre busca a série completa (cacheada por 1h)
        with st.spinner(f"Carregando série completa de {ind}..."):
            df_full = get_bcb_full(cod)

        if df_full.empty:
            st.warning("⚠️ Sem dados disponíveis. A API BCB pode estar temporariamente indisponível.")
        else:
            date_min = df_full["data"].min().date()
            date_max = df_full["data"].max().date()
            # Padrão: últimos 12 meses
            default_start = max(date_min, (df_full["data"].max() - pd.DateOffset(months=12)).date())

            st.markdown(
                f"<div style='font-size:11px;color:#475569;margin:4px 0 10px 0'>"
                f"Série disponível: <b style='color:#64748b'>{date_min.strftime('%d/%m/%Y')}</b>"
                f" → <b style='color:#64748b'>{date_max.strftime('%d/%m/%Y')}</b>"
                f" &nbsp;|&nbsp; {len(df_full)} observações"
                f"</div>",
                unsafe_allow_html=True,
            )

            c3, c4, c5 = st.columns([2, 2, 1])
            with c3:
                d_ini = st.date_input(
                    "De", value=default_start,
                    min_value=date_min, max_value=date_max,
                    key="graf_ini"
                )
            with c4:
                d_fim = st.date_input(
                    "Até", value=date_max,
                    min_value=date_min, max_value=date_max,
                    key="graf_fim"
                )
            with c5:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("🔄 Série completa", key="graf_reset"):
                    st.session_state["graf_ini"] = date_min
                    st.session_state["graf_fim"] = date_max
                    st.rerun()

            # Filtra em memória — sem nova chamada à API
            if d_ini >= d_fim:
                st.error("⚠️ Data início deve ser anterior à data fim.")
            else:
                mask  = (df_full["data"].dt.date >= d_ini) & (df_full["data"].dt.date <= d_fim)
                df_g  = df_full[mask].copy()

                if df_g.empty:
                    st.warning("Nenhuma observação no período selecionado.")
                else:
                    st.success(f"✅ {len(df_g)} observações · {ind} ({unit}) · {freq}")
                    titulo = f"{ind} ({unit})"
                    fig = (
                        bar_fig(df_g, titulo, suffix=f" {unit}", height=420, fixed_axes=False)
                        if tipo == "bar"
                        else line_fig(df_g, titulo, "#6366f1", suffix=f" {unit}", height=420, fixed_axes=False)
                    )
                    st.plotly_chart(fig, use_container_width=True, config={**CHART_CFG, "scrollZoom": True})

                    df_dl = df_g.copy()
                    df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
                    csv = df_dl.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        f"💾 Baixar CSV ({len(df_dl)} linhas)",
                        data=csv,
                        file_name=f"{ind.replace(' ','_')}_{d_ini}_{d_fim}.csv",
                        mime="text/csv",
                    )

    # ── Tab Yahoo Finance ─────────────────────────────────────────────────────
    with tab_yahoo:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="graf_ativo")
        with col2:
            anos = st.select_slider("Período (anos)", [1, 2, 3, 5, 10], value=5, key="graf_anos")

        sym, unit, flag, _ = GLOBAL[ativo]
        with st.spinner(f"Carregando {ativo}..."):
            df_g = get_hist(sym, years=anos)

        if df_g.empty:
            st.warning("Sem dados históricos disponíveis.")
        else:
            st.success(f"✅ {len(df_g)} observações · {flag} {ativo}")
            fig = line_fig(df_g, f"{flag} {ativo} — {anos} ano(s)",
                           "#6366f1", suffix=f" {unit}", height=420, fixed_axes=False)
            st.plotly_chart(fig, use_container_width=True, config={**CHART_CFG, "scrollZoom": True})

            df_dl = df_g.copy()
            df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
            csv = df_dl.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                f"💾 Baixar CSV ({len(df_dl)} linhas)",
                data=csv,
                file_name=f"{ativo.replace(' ','_')}_{anos}a.csv",
                mime="text/csv",
            )

# ═════════════════════════════════════════════════════════════════════════════
# 📥 EXPORTAR
# ═════════════════════════════════════════════════════════════════════════════
else:
    col_t, col_h = st.columns([5, 1])
    with col_t:
        st.markdown("<h2 style='margin:0;color:#e2e8f0'>📥 Exportar</h2>",
                    unsafe_allow_html=True)
    with col_h:
        st.markdown(
            "<div style='text-align:right;color:#2d3748;font-size:10px;padding-top:10px'>"
            "Baixe dados históricos em CSV</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:2px;background:#131929;margin:10px 0 18px 0'></div>",
                unsafe_allow_html=True)

    fonte = st.radio("Fonte:", ["📊 BCB/SGS — Brasil", "🌍 Yahoo Finance — Globais"],
                     horizontal=True)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if fonte == "📊 BCB/SGS — Brasil":
        col1, col2, col3 = st.columns([2, 1.5, 1.5])
        with col1: ind   = st.selectbox("Indicador", list(SGS.keys()), index=1)
        with col2: d_ini = st.date_input("De", value=datetime.today()-timedelta(days=365))
        with col3: d_fim = st.date_input("Até", value=datetime.today())

        modo_b = st.radio("Período:", ["Usar datas acima", "Série completa desde o início"],
                          horizontal=True)

        if st.button("⬇  Gerar CSV", type="primary"):
            cod, unit, freq, _ = SGS[ind]
            with st.spinner(f"Buscando {ind}..."):
                if "completa" in modo_b:
                    df_exp = get_bcb_full(cod)
                else:
                    if d_ini >= d_fim:
                        st.error("Data início deve ser anterior à data fim.")
                        st.stop()
                    df_exp = get_bcb_range(cod,
                                           d_ini.strftime("%d/%m/%Y"),
                                           d_fim.strftime("%d/%m/%Y"))

            if df_exp.empty:
                st.warning("Nenhum dado encontrado. Tente outro período ou verifique a disponibilidade da API BCB.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** — {ind} ({unit})")
                st.dataframe(
                    df_out.rename(columns={"data": "Data", "valor": f"Valor ({unit})"}),
                    use_container_width=True,
                    height=min(380, 46 + len(df_out) * 35),
                )
                csv  = df_out.to_csv(index=False).encode("utf-8-sig")
                suf  = "completo" if "completa" in modo_b else f"{d_ini}_{d_fim}"
                nome = f"{ind.replace(' ','_')}_{suf}.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    else:  # Yahoo
        col1, col2 = st.columns([2, 1])
        with col1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()))
        with col2: anos  = st.select_slider("Período (anos)", [1, 2, 3, 5, 10], value=5)

        if st.button("⬇  Gerar CSV", type="primary"):
            sym, unit, flag, _ = GLOBAL[ativo]
            with st.spinner(f"Buscando {ativo}..."):
                df_exp = get_hist(sym, years=anos)

            if df_exp.empty:
                st.warning("Sem dados disponíveis.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** — {flag} {ativo}")
                st.dataframe(
                    df_out.rename(columns={"data": "Data", "valor": f"Valor ({unit})"}),
                    use_container_width=True,
                    height=min(380, 46 + len(df_out) * 35),
                )
                csv  = df_out.to_csv(index=False).encode("utf-8-sig")
                nome = f"{ativo.replace(' ','_')}_{anos}anos.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    with st.expander("📋 Ver todos os indicadores e ativos disponíveis"):
        st.markdown("**BCB/SGS — Indicadores Brasil**")
        st.dataframe(pd.DataFrame([
            {"Indicador": k, "Cód. SGS": v[0], "Unidade": v[1], "Freq.": v[2]}
            for k, v in SGS.items()
        ]), hide_index=True, use_container_width=False)
        st.markdown("<br>**Yahoo Finance — Ativos Globais**", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Ativo": k, "Símbolo": v[0], "Unidade": v[1]}
            for k, v in GLOBAL.items()
        ]), hide_index=True, use_container_width=False)
