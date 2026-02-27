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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] {
    background: #080c14 !important;
    border-right: 1px solid #131929;
    min-width: 210px !important; max-width: 210px !important;
}
.main .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
footer, #MainMenu { visibility: hidden; }

.sec-title {
    font-size: 10px; font-weight: 700; color: #374151;
    text-transform: uppercase; letter-spacing: 2.5px;
    border-bottom: 1px solid #131929;
    padding-bottom: 7px; margin: 10px 0 14px 0;
}
.badge-live  { display:inline-block;background:#052e16;border:1px solid #166534;
               color:#4ade80;font-size:9px;padding:1px 7px;border-radius:20px;margin-left:6px; }
.badge-daily { display:inline-block;background:#1e1b4b;border:1px solid #3730a3;
               color:#818cf8;font-size:9px;padding:1px 7px;border-radius:20px;margin-left:6px; }
.stDownloadButton > button {
    background:#1d4ed8 !important;color:white !important;
    border:none !important;border-radius:8px !important;font-weight:600 !important;
}
div[data-testid="stExpander"] { border: 1px solid #131929 !important; border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE  = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=7d"
YAHOO_HIST= "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range={}y"

SGS_CODES = {
    "Selic":           (432,   "% a.a.",     "Mensal"),
    "IPCA":            (433,   "% mês",      "Mensal"),
    "IBC-Br":          (24363, "índice",     "Mensal"),
    "Dólar PTAX":      (1,     "R$",         "Diário"),
    "PIB":             (4380,  "% trim.",    "Trimestral"),
    "Desemprego":      (24369, "%",          "Trimestral"),
    "IGP-M":           (189,   "% mês",      "Mensal"),
    "IPCA-15":         (7478,  "% mês",      "Mensal"),
    "Exportações":     (2257,  "US$ mi",     "Mensal"),
    "Importações":     (2258,  "US$ mi",     "Mensal"),
    "Dívida/PIB":      (13762, "%",          "Mensal"),
}

GLOBAL_ASSETS = {
    # Futuros BR
    "IBOVESPA":          ("^BVSP",    "pts",  "🇧🇷"),
    "Dólar (USD/BRL)":   ("USDBRL=X", "R$",   "💵"),
    "Euro (EUR/BRL)":    ("EURBRL=X", "R$",   "💶"),
    # Índices globais
    "S&P 500":           ("^GSPC",    "pts",  "🇺🇸"),
    "Nasdaq 100":        ("^NDX",     "pts",  "🇺🇸"),
    "Dow Jones":         ("^DJI",     "pts",  "🇺🇸"),
    "FTSE 100":          ("^FTSE",    "pts",  "🇬🇧"),
    # Commodities
    "Petróleo Brent":    ("BZ=F",     "US$",  "🛢️"),
    "Petróleo WTI":      ("CL=F",     "US$",  "🛢️"),
    "Ouro":              ("GC=F",     "US$",  "🥇"),
    "Prata":             ("SI=F",     "US$",  "🥈"),
    "Cobre":             ("HG=F",     "US$/lb","🪙"),
    "Minério de Ferro":  ("TIO=F",    "US$",  "⚙️"),
    # Cripto
    "Bitcoin":           ("BTC-USD",  "US$",  "₿"),
    "Ethereum":          ("ETH-USD",  "US$",  "Ξ"),
}

CHART_CFG = {"displayModeBar": False}

PLOT_BASE = dict(
    paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
    font_color="#6b7fa8", font_family="Inter",
    margin=dict(l=0, r=4, t=38, b=0),
    xaxis=dict(gridcolor="#131929", showline=False, tickfont=dict(size=10), zeroline=False),
    yaxis=dict(gridcolor="#131929", showline=False, tickfont=dict(size=10), zeroline=False),
    title_font=dict(color="#94a3b8", size=13),
    hoverlabel=dict(bgcolor="#1e2640", font_size=12, bordercolor="#2d3a5a"),
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

# ─── DATA FUNCTIONS ───────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def get_yahoo_quote(symbol: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(YAHOO_URL.format(symbol), headers=headers, timeout=8)
        data  = r.json()
        result = data["chart"]["result"][0]
        meta  = result["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        chg_p = ((price - prev) / prev * 100) if (prev and price and prev != 0) else None
        chg_v = (price - prev) if (prev and price) else None
        market = meta.get("marketState", "CLOSED")
        # Pega timestamp do último preço disponível
        timestamps = result.get("timestamp", [])
        last_ts = timestamps[-1] if timestamps else None
        last_date = datetime.fromtimestamp(last_ts).strftime("%d/%m/%Y") if last_ts else None
        return {
            "price": price, "prev": prev,
            "chg_p": chg_p, "chg_v": chg_v,
            "market": market, "last_date": last_date,
            "currency": meta.get("currency",""),
        }
    except:
        return {}

@st.cache_data(ttl=3600)
def get_yahoo_hist(symbol: str, years: int = 5):
    """Histórico via Yahoo Finance para ativos globais."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = YAHOO_HIST.format(symbol, years)
        r = requests.get(url, headers=headers, timeout=12)
        data   = r.json()
        result = data["chart"]["result"][0]
        ts     = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        df = pd.DataFrame({"data": pd.to_datetime(ts, unit="s"), "valor": closes})
        df = df.dropna().reset_index(drop=True)
        return df
    except:
        return pd.DataFrame(columns=["data","valor"])

@st.cache_data(ttl=3600)
def get_bcb(codigo: int, ultimos: int):
    try:
        url = BCB_BASE.format(codigo) + f"/ultimos/{ultimos}?formato=json"
        r   = requests.get(url, timeout=10)
        df  = pd.DataFrame(r.json())
        if df.empty: return df
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

@st.cache_data(ttl=3600)
def get_bcb_full(codigo: int):
    """Carrega série completa do BCB (desde o início)."""
    try:
        url = BCB_BASE.format(codigo) + "?formato=json"
        r   = requests.get(url, timeout=20)
        df  = pd.DataFrame(r.json())
        if df.empty: return df
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

@st.cache_data(ttl=3600)
def get_bcb_range(codigo: int, ini: str, fim: str):
    try:
        url = BCB_BASE.format(codigo) + f"?formato=json&dataInicial={ini}&dataFinal={fim}"
        r   = requests.get(url, timeout=15)
        df  = pd.DataFrame(r.json())
        if df.empty: return df
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

# ─── KPI CARD ────────────────────────────────────────────────────────────────
import streamlit.components.v1 as components

def kpi(label, value, chg_p=None, sub="", invert=False, closed=False, close_date=None):
    if chg_p is not None:
        up  = (chg_p >= 0) if not invert else (chg_p < 0)
        cls = "pos" if up else "neg"
        arr = "▲" if chg_p >= 0 else "▼"
        dlt = f'<div class="d-{cls}">{arr} {abs(chg_p):.2f}%</div>'
    else:
        dlt = '<div class="d-neu"> </div>'

    if closed and close_date:
        badge = f'<div class="closed">Fechamento {close_date}</div>'
    elif closed:
        badge = '<div class="closed">Último fechamento</div>'
    else:
        badge = ""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:'Inter',sans-serif}}
.card{{
  background:linear-gradient(135deg,#0f1424,#161d30);
  border:1px solid #1e2640;border-radius:14px;
  padding:16px;text-align:center;height:118px;
  display:flex;flex-direction:column;justify-content:center;gap:3px;
}}
.lbl{{font-size:9px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1.6px}}
.val{{font-size:20px;font-weight:800;color:#e2e8f0;line-height:1.15}}
.d-pos{{font-size:11px;color:#4ade80}}
.d-neg{{font-size:11px;color:#f87171}}
.d-neu{{font-size:11px;color:#1e2640}}
.sub{{font-size:9px;color:#334155}}
.closed{{font-size:9px;color:#92400e;background:#1c1208;
          border:1px solid #451a03;display:inline-block;
          padding:1px 7px;border-radius:10px;margin-top:2px}}
</style></head><body>
<div class="card">
  <div class="lbl">{label}</div>
  <div class="val">{value}</div>
  {dlt}
  <div class="sub">{sub}</div>
  {badge}
</div></body></html>"""
    components.html(html, height=126)

# ─── CHART FACTORIES ─────────────────────────────────────────────────────────
def line_fig(df, title, color="#6366f1", fill=True, suffix="", height=260):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=3, color=color),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_rgba(color, 0.10),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**PLOT_BASE, title=title, height=height)
    return fig

def bar_fig(df, title, suffix="", height=260):
    colors = ["#4ade80" if v >= 0 else "#f87171" for v in df["valor"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=colors, marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**PLOT_BASE, title=title, height=height)
    return fig

def candlestick_fig(df, title, height=320):
    """Só para Yahoo (tem OHLC). Fallback para linha se só tiver close."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines",
        line=dict(color="#6366f1", width=1.5),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}</b><extra></extra>",
        fill="tozeroy", fillcolor=hex_rgba("#6366f1", 0.08),
    ))
    fig.update_layout(**PLOT_BASE, title=title, height=height)
    return fig

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding:8px 0 4px 0'>"
        "<span style='font-size:20px'>🇧🇷</span> "
        "<span style='font-size:14px;font-weight:700;color:#94a3b8'>Macro Brasil</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#131929;margin:6px 0 10px 0'>", unsafe_allow_html=True)

    pagina = st.radio(
        "nav",
        options=[
            "📊  Dashboard",
            "🌍  Mercados Globais",
            "📈  Gráficos Avançados",
            "📥  Exportar CSV",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color:#131929;margin:10px 0'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:9px;color:#1e2640;line-height:1.9'>"
        "Fontes:<br>• BCB/SGS (indicadores BR)<br>• Yahoo Finance (mercados)<br><br>"
        "Mercados: ↻ 60s<br>BCB: ↻ 1h"
        "</div>",
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
if pagina == "📊  Dashboard":

    col_t, col_h = st.columns([4,1])
    with col_t:
        st.markdown("## 🇧🇷 Dashboard Macro Brasil")
    with col_h:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.markdown(
            f"<div style='text-align:right;color:#1e2640;font-size:10px;padding-top:16px'>"
            f"Atualizado<br><b style='color:#334155'>{now}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='border-color:#131929;margin:2px 0 10px 0'>", unsafe_allow_html=True)

    # Carregar dados (24 meses padrão)
    with st.spinner("Carregando..."):
        ibov_d = get_yahoo_quote("^BVSP")
        usd_d  = get_yahoo_quote("USDBRL=X")
        eur_d  = get_yahoo_quote("EURBRL=X")
        # BCB: meses mensais = 24 obs, diários = 60 dias úteis (~3 meses)
        df_sel  = get_bcb(432,   25)
        df_ipca = get_bcb(433,   25)
        df_ibc  = get_bcb(24363, 25)
        df_cam  = get_bcb(1,     65)   # diário → 65 para garantir ~45 dias úteis
        df_pib  = get_bcb(4380,  12)
        df_des  = get_bcb(24369, 12)

    # ── KPIs Mercado ─────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Indicadores de Mercado'
        '<span class="badge-live">↻ 60s</span></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        v = ibov_d.get("price")
        closed = ibov_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        close_date = ibov_d.get("last_date") if closed else None
        kpi("Ibovespa",
            fmt(v,0) + " pts" if v else "—",
            ibov_d.get("chg_p"),
            f"Var. dia: {fmt(ibov_d.get('chg_v'),0)} pts" if v else "—",
            closed=closed, close_date=close_date)
    with c2:
        v = usd_d.get("price")
        closed = usd_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Dólar (USD/BRL)",
            f"R$ {fmt(v,4)}" if v else "—",
            usd_d.get("chg_p"),
            f"Ant.: R$ {fmt(usd_d.get('prev'),4)}" if v else "—",
            invert=True, closed=closed, close_date=usd_d.get("last_date"))
    with c3:
        v = eur_d.get("price")
        closed = eur_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Euro (EUR/BRL)",
            f"R$ {fmt(v,4)}" if v else "—",
            eur_d.get("chg_p"),
            f"Ant.: R$ {fmt(eur_d.get('prev'),4)}" if v else "—",
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
        v   = float(df_sel["valor"].iloc[-1])  if not df_sel.empty  else None
        ref = df_sel["data"].iloc[-1].strftime("%b/%Y") if not df_sel.empty else ""
        kpi("Selic", f"{fmt(v)}% a.a." if v else "—", sub=f"Ref: {ref}")
    with c5:
        v   = float(df_ipca["valor"].iloc[-1]) if not df_ipca.empty else None
        ref = df_ipca["data"].iloc[-1].strftime("%b/%Y") if not df_ipca.empty else ""
        delta = None
        if not df_ipca.empty and len(df_ipca) >= 2:
            delta = float(df_ipca["valor"].iloc[-1]) - float(df_ipca["valor"].iloc[-2])
        kpi("IPCA", f"{fmt(v)}% mês" if v else "—", chg_p=delta, sub=f"Ref: {ref}")
    with c6:
        v   = float(df_des["valor"].iloc[-1])  if not df_des.empty  else None
        ref = df_des["data"].iloc[-1].strftime("%b/%Y") if not df_des.empty else ""
        kpi("Desemprego (PNAD)", f"{fmt(v)}%" if v else "—", sub=f"Ref: {ref}")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Gráficos — 24 meses ───────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Histórico — últimos 24 meses '
        '<span style="font-size:9px;color:#334155;font-weight:400">'
        '(para série completa → Gráficos Avançados no menu)</span></div>',
        unsafe_allow_html=True,
    )

    ca, cb = st.columns(2)
    with ca:
        if not df_sel.empty:
            st.plotly_chart(line_fig(df_sel, "Selic (% a.a.)", "#6366f1", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.info("Sem dados.")
    with cb:
        if not df_ipca.empty:
            st.plotly_chart(bar_fig(df_ipca, "IPCA (% ao mês)", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.info("Sem dados.")

    cc, cd = st.columns(2)
    with cc:
        df_cam30 = df_cam.tail(45) if not df_cam.empty else df_cam
        if not df_cam30.empty:
            st.plotly_chart(line_fig(df_cam30, "Dólar PTAX — 45 dias úteis (R$)", "#f59e0b", suffix=" R$"),
                            use_container_width=True, config=CHART_CFG)
        else: st.info("Sem dados.")
    with cd:
        if not df_ibc.empty:
            st.plotly_chart(line_fig(df_ibc, "IBC-Br (índice)", "#22d3ee", fill=False),
                            use_container_width=True, config=CHART_CFG)
        else: st.info("Sem dados.")

    ce, cf = st.columns(2)
    with ce:
        if not df_pib.empty:
            st.plotly_chart(bar_fig(df_pib, "PIB — variação trimestral (%)", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.info("Sem dados.")
    with cf:
        if not df_des.empty:
            st.plotly_chart(line_fig(df_des, "Desemprego PNAD (%)", "#f87171", fill=True, suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.info("Sem dados.")

    st.markdown(
        "<div style='text-align:center;color:#131929;font-size:10px;margin-top:16px'>"
        "Yahoo Finance (mercados, ↻60s) • BCB/SGS (econômicos, cache 1h)"
        "</div>", unsafe_allow_html=True,
    )
    time.sleep(60)
    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — MERCADOS GLOBAIS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "🌍  Mercados Globais":

    col_t, col_h = st.columns([4,1])
    with col_t:
        st.markdown("## 🌍 Mercados Globais")
    with col_h:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.markdown(
            f"<div style='text-align:right;color:#1e2640;font-size:10px;padding-top:16px'>"
            f"Atualizado<br><b style='color:#334155'>{now}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='border-color:#131929;margin:2px 0 10px 0'>", unsafe_allow_html=True)

    # Grupos de ativos
    grupos = {
        "🇧🇷 Brasil": ["IBOVESPA","Dólar (USD/BRL)","Euro (EUR/BRL)"],
        "🇺🇸 Índices EUA": ["S&P 500","Nasdaq 100","Dow Jones"],
        "🌎 Índices Globais": ["FTSE 100"],
        "🛢️ Energia": ["Petróleo Brent","Petróleo WTI"],
        "🥇 Metais": ["Ouro","Prata","Cobre","Minério de Ferro"],
        "₿ Cripto": ["Bitcoin","Ethereum"],
    }

    for grupo, ativos in grupos.items():
        st.markdown(f'<div class="sec-title">{grupo}</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(ativos), 4))
        for i, nome in enumerate(ativos):
            symbol, unit, flag = GLOBAL_ASSETS[nome]
            with st.spinner(f""):
                d = get_yahoo_quote(symbol)
            with cols[i % 4]:
                v = d.get("price")
                closed = d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
                prefix = "R$ " if unit == "R$" else ("US$ " if unit in ("US$","US$/lb") else "")
                val_str = f"{prefix}{fmt(v, 2 if unit!='pts' else 0)} {unit}" if v else "—"
                invert = nome in ("Dólar (USD/BRL)","Euro (EUR/BRL)")
                kpi(f"{flag} {nome}", val_str, d.get("chg_p"),
                    sub=f"Ant.: {prefix}{fmt(d.get('prev'),2)}" if v else "",
                    invert=invert, closed=closed, close_date=d.get("last_date"))

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Mini gráficos dos principais
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sec-title">Gráficos — últimos 2 anos</div>', unsafe_allow_html=True)

    destaques = [
        ("IBOVESPA","^BVSP","#6366f1","pts"),
        ("S&P 500","^GSPC","#22d3ee","pts"),
        ("Petróleo Brent","BZ=F","#f59e0b","US$"),
        ("Ouro","GC=F","#fbbf24","US$"),
    ]

    g1, g2 = st.columns(2)
    g3, g4 = st.columns(2)
    pairs = [(g1, destaques[0]), (g2, destaques[1]), (g3, destaques[2]), (g4, destaques[3])]
    for col, (nome, sym, cor, unit) in pairs:
        with col:
            with st.spinner(f"Carregando {nome}..."):
                df_h = get_yahoo_hist(sym, years=2)
            if not df_h.empty:
                st.plotly_chart(
                    line_fig(df_h, f"{nome} — 2 anos", cor, fill=True, suffix=f" {unit}"),
                    use_container_width=True, config=CHART_CFG)
            else:
                st.info(f"{nome}: sem dados históricos.")

    time.sleep(60)
    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 3 — GRÁFICOS AVANÇADOS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "📈  Gráficos Avançados":

    st.markdown("## 📈 Gráficos Avançados")
    st.markdown(
        "<p style='color:#475569;font-size:13px;margin-bottom:16px'>"
        "Visualize séries completas desde o início da coleta, ou defina um intervalo personalizado.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#131929'>", unsafe_allow_html=True)

    tipo_fonte = st.radio("Fonte:", ["📊 Indicadores BCB (Brasil)", "🌍 Ativos Globais (Yahoo Finance)"],
                          horizontal=True)

    if tipo_fonte == "📊 Indicadores BCB (Brasil)":
        col1, col2 = st.columns(2)
        with col1:
            ind_sel = st.selectbox("Indicador", list(SGS_CODES.keys()))
        with col2:
            modo = st.radio("Período:", ["Últimos 24 meses","Últimos 5 anos","Série completa","Personalizado"],
                            horizontal=False)

        if modo == "Personalizado":
            c3, c4 = st.columns(2)
            with c3:
                d_ini = st.date_input("De", value=datetime.today()-timedelta(days=365*5), max_value=datetime.today())
            with c4:
                d_fim = st.date_input("Até", value=datetime.today(), max_value=datetime.today())

        if st.button("📈 Carregar gráfico", type="primary"):
            cod, unit, freq = SGS_CODES[ind_sel]
            with st.spinner(f"Carregando série de {ind_sel}..."):
                if modo == "Últimos 24 meses":
                    n = 25 if "Mensal" in freq else (8 if "Trim" in freq else 60)
                    df_g = get_bcb(cod, n)
                elif modo == "Últimos 5 anos":
                    n = 62 if "Mensal" in freq else (20 if "Trim" in freq else 365)
                    df_g = get_bcb(cod, n)
                elif modo == "Série completa":
                    df_g = get_bcb_full(cod)
                else:
                    df_g = get_bcb_range(cod,
                                         d_ini.strftime("%d/%m/%Y"),
                                         d_fim.strftime("%d/%m/%Y"))

            if df_g.empty:
                st.warning("Sem dados para o período selecionado.")
            else:
                st.success(f"✅ {len(df_g)} observações — {ind_sel}")
                titulo = f"{ind_sel} ({unit}) — {modo}"
                # Barras para IPCA, PIB, IGP-M, variações; linha para o resto
                bar_inds = {"IPCA","IGP-M","IPCA-15","PIB","Exportações","Importações"}
                if ind_sel in bar_inds:
                    fig = bar_fig(df_g, titulo, suffix=f" {unit}", height=380)
                else:
                    fig = line_fig(df_g, titulo, "#6366f1", suffix=f" {unit}", height=380)
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

                # Download direto da série exibida
                df_dl = df_g.copy()
                df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
                csv = df_dl.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    f"💾 Baixar CSV ({len(df_dl)} linhas)",
                    data=csv,
                    file_name=f"{ind_sel.replace(' ','_')}_{modo.replace(' ','_')}.csv",
                    mime="text/csv",
                )

    else:  # Yahoo Finance
        col1, col2 = st.columns(2)
        with col1:
            ativo_sel = st.selectbox("Ativo", list(GLOBAL_ASSETS.keys()))
        with col2:
            anos = st.select_slider("Período (anos)", options=[1,2,3,5,10], value=5)

        if st.button("📈 Carregar gráfico", type="primary"):
            symbol, unit, flag = GLOBAL_ASSETS[ativo_sel]
            with st.spinner(f"Carregando {ativo_sel}..."):
                df_g = get_yahoo_hist(symbol, years=anos)

            if df_g.empty:
                st.warning("Sem dados históricos disponíveis para este ativo.")
            else:
                st.success(f"✅ {len(df_g)} observações — {ativo_sel}")
                titulo = f"{flag} {ativo_sel} — {anos} ano(s)"
                fig = line_fig(df_g, titulo, "#6366f1", suffix=f" {unit}", height=420)
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

                # Download
                df_dl = df_g.copy()
                df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
                csv = df_dl.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    f"💾 Baixar CSV ({len(df_dl)} linhas)",
                    data=csv,
                    file_name=f"{ativo_sel.replace(' ','_')}_{anos}anos.csv",
                    mime="text/csv",
                )

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 4 — EXPORTAR CSV
# ═════════════════════════════════════════════════════════════════════════════
else:

    st.markdown("## 📥 Exportar CSV")
    st.markdown(
        "<p style='color:#475569;font-size:13px;margin-bottom:16px'>"
        "Baixe dados históricos de qualquer indicador ou ativo em CSV. "
        "Fontes: BCB/SGS para indicadores brasileiros, Yahoo Finance para ativos globais.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#131929'>", unsafe_allow_html=True)

    fonte = st.radio("Fonte de dados:", ["📊 BCB/SGS — Indicadores Brasil", "🌍 Yahoo Finance — Ativos Globais"],
                     horizontal=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if fonte == "📊 BCB/SGS — Indicadores Brasil":
        col1, col2, col3 = st.columns([2,1.5,1.5])
        with col1:
            ind_sel = st.selectbox("Indicador", list(SGS_CODES.keys()), index=1)
        with col2:
            d_ini = st.date_input("Data início", value=datetime.today()-timedelta(days=365),
                                  max_value=datetime.today())
        with col3:
            d_fim = st.date_input("Data fim", value=datetime.today(), max_value=datetime.today())

        modo_bcb = st.radio("Ou use:", ["Intervalo acima","Série completa desde o início"],
                             horizontal=True)

        gerar = st.button("⬇  Gerar CSV", type="primary")
        if gerar:
            cod, unit, freq = SGS_CODES[ind_sel]
            with st.spinner(f"Buscando {ind_sel}..."):
                if modo_bcb == "Série completa desde o início":
                    df_exp = get_bcb_full(cod)
                else:
                    if d_ini >= d_fim:
                        st.error("Data início deve ser anterior à data fim.")
                        st.stop()
                    df_exp = get_bcb_range(cod, d_ini.strftime("%d/%m/%Y"), d_fim.strftime("%d/%m/%Y"))

            if df_exp.empty:
                st.warning("Nenhum dado encontrado.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** de {ind_sel}")
                st.dataframe(
                    df_out.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),
                    use_container_width=True,
                    height=min(400, 46 + len(df_out)*35),
                )
                csv   = df_out.to_csv(index=False).encode("utf-8-sig")
                sufixo = "completo" if modo_bcb.startswith("Série") else f"{d_ini}_{d_fim}"
                nome  = f"{ind_sel.replace(' ','_')}_{sufixo}.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    else:  # Yahoo Finance
        col1, col2 = st.columns([2,1])
        with col1:
            ativo_sel = st.selectbox("Ativo", list(GLOBAL_ASSETS.keys()))
        with col2:
            anos = st.select_slider("Período (anos)", options=[1,2,3,5,10], value=5)

        gerar = st.button("⬇  Gerar CSV", type="primary")
        if gerar:
            symbol, unit, flag = GLOBAL_ASSETS[ativo_sel]
            with st.spinner(f"Buscando {ativo_sel}..."):
                df_exp = get_yahoo_hist(symbol, years=anos)

            if df_exp.empty:
                st.warning("Sem dados históricos disponíveis.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** de {flag} {ativo_sel}")
                st.dataframe(
                    df_out.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),
                    use_container_width=True,
                    height=min(400, 46 + len(df_out)*35),
                )
                csv  = df_out.to_csv(index=False).encode("utf-8-sig")
                nome = f"{ativo_sel.replace(' ','_')}_{anos}anos.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    # Referência
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    with st.expander("📋 Ver todos os indicadores e ativos disponíveis"):
        st.markdown("**BCB/SGS — Indicadores Brasil**")
        st.dataframe(pd.DataFrame([
            {"Indicador": k, "Código SGS": v[0], "Unidade": v[1], "Frequência": v[2]}
            for k, v in SGS_CODES.items()
        ]), hide_index=True, use_container_width=False)

        st.markdown("<br>**Yahoo Finance — Ativos Globais**", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Ativo": k, "Símbolo Yahoo": v[0], "Unidade": v[1]}
            for k, v in GLOBAL_ASSETS.items()
        ]), hide_index=True, use_container_width=False)
