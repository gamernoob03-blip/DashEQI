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
BCB_BASE   = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"
YAHOO_SNAP = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=7d"
YAHOO_HIST = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range={}y"
HEADERS    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Código SGS → (codigo, unidade, frequencia, é_percentual)
SGS = {
    "Selic":        (11,    "% a.a.",  "Mensal",      True),
    "IPCA":         (433,   "% mês",   "Mensal",      True),
    "IBC-Br":       (24363, "índice",  "Mensal",      False),
    "Dólar PTAX":   (1,     "R$",      "Diário",      False),
    "PIB":          (4380,  "% trim.", "Trimestral",  True),
    "Desemprego":   (24369, "%",       "Trimestral",  False),
    "IGP-M":        (189,   "% mês",   "Mensal",      True),
    "IPCA-15":      (7478,  "% mês",   "Mensal",      True),
    "Exportações":  (2257,  "US$ mi",  "Mensal",      False),
    "Importações":  (2258,  "US$ mi",  "Mensal",      False),
    "Dívida/PIB":   (4513,  "%",       "Mensal",      False),
}

# Nota: Selic usa código 11 (Selic diária acumulada mensal, mais estável)
# Fallback: se código 11 falhar, tenta 432

GLOBAL = {
    # Brasil
    "IBOVESPA":        ("^BVSP",    "pts",   "🇧🇷", False),
    "Dólar (USD/BRL)": ("USDBRL=X", "R$",    "💵",  True),
    "Euro (EUR/BRL)":  ("EURBRL=X", "R$",    "💶",  True),
    # EUA
    "S&P 500":         ("^GSPC",    "pts",   "🇺🇸", False),
    "Nasdaq 100":      ("^NDX",     "pts",   "🇺🇸", False),
    "Dow Jones":       ("^DJI",     "pts",   "🇺🇸", False),
    # Europa
    "FTSE 100":        ("^FTSE",    "pts",   "🇬🇧", False),
    "DAX":             ("^GDAXI",   "pts",   "🇩🇪", False),
    # Commodities
    "Petróleo Brent":  ("BZ=F",     "US$",   "🛢️",  True),
    "Petróleo WTI":    ("CL=F",     "US$",   "🛢️",  True),
    "Ouro":            ("GC=F",     "US$",   "🥇",  False),
    "Prata":           ("SI=F",     "US$",   "🥈",  False),
    "Cobre":           ("HG=F",     "US$/lb","🪙",  True),
    # Cripto
    "Bitcoin":         ("BTC-USD",  "US$",   "₿",   False),
    "Ethereum":        ("ETH-USD",  "US$",   "Ξ",   False),
}

CHART_CFG = {"displayModeBar": False}

PLOT_BASE = dict(
    paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
    font_color="#6b7fa8", font_family="Inter",
    margin=dict(l=0, r=4, t=38, b=0),
    xaxis=dict(gridcolor="#131929", showline=False, tickfont=dict(size=10), zeroline=False),
    yaxis=dict(gridcolor="#131929", showline=False, tickfont=dict(size=10), zeroline=False),
    title_font=dict(color="#94a3b8", size=13),
    hoverlabel=dict(bgcolor="#1e2640", font_size=12),
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
    integer = parts[0].replace(",",".")
    decimal = parts[1] if len(parts) > 1 else ""
    return f"{integer},{decimal}" if decimal else integer

# ─── DATA ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def get_quote(symbol: str) -> dict:
    try:
        r    = requests.get(YAHOO_SNAP.format(symbol), headers=HEADERS, timeout=8)
        data = r.json()
        result = data["chart"]["result"][0]
        meta   = result["meta"]
        price  = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev   = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        chg_p  = ((price - prev) / prev * 100) if (prev and price and prev != 0) else None
        chg_v  = (price - prev) if (prev and price) else None
        market = meta.get("marketState", "CLOSED")
        ts     = result.get("timestamp", [])
        last_d = datetime.fromtimestamp(ts[-1]).strftime("%d/%m/%Y") if ts else None
        return {"price": price, "prev": prev, "chg_p": chg_p, "chg_v": chg_v,
                "market": market, "last_date": last_d}
    except:
        return {}

@st.cache_data(ttl=3600)
def get_hist(symbol: str, years: int = 5) -> pd.DataFrame:
    try:
        r    = requests.get(YAHOO_HIST.format(symbol, years), headers=HEADERS, timeout=12)
        data = r.json()
        res  = data["chart"]["result"][0]
        ts   = res["timestamp"]
        vals = res["indicators"]["quote"][0]["close"]
        df   = pd.DataFrame({"data": pd.to_datetime(ts, unit="s"), "valor": vals})
        return df.dropna().reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

@st.cache_data(ttl=3600)
def get_bcb(codigo: int, ultimos: int) -> pd.DataFrame:
    try:
        url = BCB_BASE.format(codigo) + f"/ultimos/{ultimos}?formato=json"
        r   = requests.get(url, headers=HEADERS, timeout=12)
        raw = r.json()
        # BCB retorna erro como dict, não lista
        if not isinstance(raw, list) or len(raw) == 0:
            return pd.DataFrame(columns=["data","valor"])
        df = pd.DataFrame(raw)
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

@st.cache_data(ttl=3600)
def get_bcb_full(codigo: int) -> pd.DataFrame:
    try:
        url = BCB_BASE.format(codigo) + "?formato=json"
        r   = requests.get(url, headers=HEADERS, timeout=25)
        raw = r.json()
        if not isinstance(raw, list) or len(raw) == 0:
            return pd.DataFrame(columns=["data","valor"])
        df = pd.DataFrame(raw)
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

@st.cache_data(ttl=3600)
def get_bcb_range(codigo: int, ini: str, fim: str) -> pd.DataFrame:
    try:
        url = BCB_BASE.format(codigo) + f"?formato=json&dataInicial={ini}&dataFinal={fim}"
        r   = requests.get(url, headers=HEADERS, timeout=15)
        raw = r.json()
        if not isinstance(raw, list) or len(raw) == 0:
            return pd.DataFrame(columns=["data","valor"])
        df = pd.DataFrame(raw)
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

def get_selic(ultimos=25) -> pd.DataFrame:
    """Tenta código 11 (Selic Over diária acumulada mensal). Fallback para 432."""
    df = get_bcb(11, ultimos)
    if df.empty:
        df = get_bcb(432, ultimos)
    return df

def get_ipca(ultimos=25) -> pd.DataFrame:
    """Tenta 433. Em caso de erro tenta 7060 (IPCA acumulado)."""
    df = get_bcb(433, ultimos)
    return df

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

    if closed and close_date:
        badge = f'<div class="cb">Fechamento {close_date}</div>'
    elif closed:
        badge = '<div class="cb">Último fechamento</div>'
    else:
        badge = ""

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

# ─── CHARTS ──────────────────────────────────────────────────────────────────
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
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**PLOT_BASE, title=title, height=height)
    return fig

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding:10px 0 6px 0'>"
        "<span style='font-size:22px'>🇧🇷</span>&nbsp;"
        "<span style='font-size:14px;font-weight:700;color:#94a3b8'>Macro Brasil</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#131929;margin:4px 0 10px 0'>", unsafe_allow_html=True)

    pagina = st.radio(
        "nav",
        options=[
            "🏠  Início",
            "🌍  Mercados Globais",
            "📈  Gráficos",
            "📥  Exportar",
        ],
        label_visibility="collapsed",
    )
    st.markdown("<hr style='border-color:#131929;margin:10px 0'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:9px;color:#1e2640;line-height:2'>"
        "Fontes:<br>• BCB/SGS<br>• Yahoo Finance<br><br>"
        "Mercados: ↻ 60s<br>BCB: ↻ 1h"
        "</div>",
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# INÍCIO
# ═════════════════════════════════════════════════════════════════════════════
if pagina == "🏠  Início":

    col_t, col_h = st.columns([5,1])
    with col_t:
        st.markdown("## 🇧🇷 Dashboard Macro Brasil")
    with col_h:
        st.markdown(
            f"<div style='text-align:right;color:#2d3748;font-size:10px;padding-top:16px'>"
            f"Atualizado<br><b style='color:#4b5a7a'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='border-color:#131929;margin:2px 0 10px 0'>", unsafe_allow_html=True)

    # ── Carregar dados ────────────────────────────────────────────────────────
    with st.spinner("Carregando indicadores..."):
        ibov_d = get_quote("^BVSP")
        usd_d  = get_quote("USDBRL=X")
        eur_d  = get_quote("EURBRL=X")
        df_sel  = get_selic(25)
        df_ipca = get_ipca(25)
        df_ibc  = get_bcb(24363, 25)
        df_cam  = get_bcb(1, 65)
        df_pib  = get_bcb(4380, 12)
        df_des  = get_bcb(24369, 12)

    # ── Mercado ───────────────────────────────────────────────────────────────
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
            fmt(v,0) + " pts" if v else "—",
            ibov_d.get("chg_p"),
            f"Var. dia: {fmt(ibov_d.get('chg_v'),0)} pts" if v else "—",
            closed=closed, close_date=ibov_d.get("last_date"))
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

    # ── Econômico ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Indicadores Econômicos'
        '<span class="badge-daily">↻ diário</span></div>',
        unsafe_allow_html=True,
    )
    c4, c5, c6 = st.columns(3)
    with c4:
        v   = float(df_sel["valor"].iloc[-1])  if not df_sel.empty  else None
        ref = df_sel["data"].iloc[-1].strftime("%b/%Y") if not df_sel.empty else "sem dados"
        kpi("Selic", f"{fmt(v)}% a.a." if v is not None else "—", sub=f"Ref: {ref}")
    with c5:
        v   = float(df_ipca["valor"].iloc[-1]) if not df_ipca.empty else None
        ref = df_ipca["data"].iloc[-1].strftime("%b/%Y") if not df_ipca.empty else "sem dados"
        delta = None
        if not df_ipca.empty and len(df_ipca) >= 2:
            delta = float(df_ipca["valor"].iloc[-1]) - float(df_ipca["valor"].iloc[-2])
        kpi("IPCA", f"{fmt(v)}% mês" if v is not None else "—", chg_p=delta, sub=f"Ref: {ref}")
    with c6:
        v   = float(df_des["valor"].iloc[-1])  if not df_des.empty  else None
        ref = df_des["data"].iloc[-1].strftime("%b/%Y") if not df_des.empty else "sem dados"
        kpi("Desemprego (PNAD)", f"{fmt(v)}%" if v is not None else "—", sub=f"Ref: {ref}")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Histórico — últimos 24 meses '
        '<span style="font-size:9px;color:#2d3748;font-weight:400">'
        '→ série completa em Gráficos</span></div>',
        unsafe_allow_html=True,
    )

    ca, cb = st.columns(2)
    with ca:
        if not df_sel.empty:
            st.plotly_chart(line_fig(df_sel, "Selic (% a.a.)", "#6366f1", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ Selic: API BCB indisponível no momento.")
    with cb:
        if not df_ipca.empty:
            st.plotly_chart(bar_fig(df_ipca, "IPCA (% ao mês)", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ IPCA: API BCB indisponível no momento.")

    cc, cd = st.columns(2)
    with cc:
        df_cam45 = df_cam.tail(45) if not df_cam.empty else df_cam
        if not df_cam45.empty:
            st.plotly_chart(line_fig(df_cam45, "Dólar PTAX — 45 dias úteis (R$)", "#f59e0b", suffix=" R$"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ Dólar PTAX: API BCB indisponível no momento.")
    with cd:
        if not df_ibc.empty:
            st.plotly_chart(line_fig(df_ibc, "IBC-Br (índice)", "#22d3ee", fill=False),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ IBC-Br: API BCB indisponível no momento.")

    ce, cf = st.columns(2)
    with ce:
        if not df_pib.empty:
            # PIB: força eixo Y como percentual puro sem escala automática
            fig_pib = bar_fig(df_pib, "PIB — variação trimestral (%)", suffix="%")
            fig_pib.update_yaxes(tickformat=".2f", ticksuffix="%")
            st.plotly_chart(fig_pib, use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ PIB: API BCB indisponível no momento.")
    with cf:
        if not df_des.empty:
            st.plotly_chart(line_fig(df_des, "Desemprego PNAD (%)", "#f87171", fill=True, suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.warning("⚠️ Desemprego: API BCB indisponível no momento.")

    st.markdown(
        "<div style='text-align:center;color:#131929;font-size:10px;margin-top:16px'>"
        "Yahoo Finance (mercados, ↻60s) • BCB/SGS (econômicos, ↻1h)"
        "</div>", unsafe_allow_html=True,
    )
    time.sleep(60)
    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# MERCADOS GLOBAIS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "🌍  Mercados Globais":

    col_t, col_h = st.columns([5,1])
    with col_t:
        st.markdown("## 🌍 Mercados Globais")
    with col_h:
        st.markdown(
            f"<div style='text-align:right;color:#2d3748;font-size:10px;padding-top:16px'>"
            f"Atualizado<br><b style='color:#4b5a7a'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='border-color:#131929;margin:2px 0 10px 0'>", unsafe_allow_html=True)

    grupos = {
        "🇧🇷 Brasil":        ["IBOVESPA","Dólar (USD/BRL)","Euro (EUR/BRL)"],
        "🇺🇸 Índices EUA":   ["S&P 500","Nasdaq 100","Dow Jones"],
        "🌎 Europa":          ["FTSE 100","DAX"],
        "🛢️ Energia":        ["Petróleo Brent","Petróleo WTI"],
        "🥇 Metais":          ["Ouro","Prata","Cobre"],
        "₿ Cripto":           ["Bitcoin","Ethereum"],
    }

    for grupo, ativos in grupos.items():
        st.markdown(f'<div class="sec-title">{grupo}<span class="badge-live">↻ 60s</span></div>', unsafe_allow_html=True)
        n = len(ativos)
        cols = st.columns(n)
        for i, nome in enumerate(ativos):
            sym, unit, flag, inv = GLOBAL[nome]
            d = get_quote(sym)
            with cols[i]:
                v = d.get("price")
                closed = d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
                prefix = "R$ " if unit == "R$" else ("US$ " if "US$" in unit else "")
                dec    = 0 if unit == "pts" else 2
                val_str = f"{prefix}{fmt(v, dec)}" if v else "—"
                kpi(f"{flag} {nome}", val_str, d.get("chg_p"),
                    sub=f"Ant.: {prefix}{fmt(d.get('prev'), dec)}" if v else "",
                    invert=inv, closed=closed, close_date=d.get("last_date"))
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # Mini gráficos destaques
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sec-title">Histórico — últimos 2 anos</div>', unsafe_allow_html=True)

    destaques = [
        ("IBOVESPA",       "^BVSP",  "#6366f1","pts"),
        ("S&P 500",        "^GSPC",  "#22d3ee","pts"),
        ("Petróleo Brent", "BZ=F",   "#f59e0b","US$"),
        ("Ouro",           "GC=F",   "#fbbf24","US$"),
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
# GRÁFICOS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "📈  Gráficos":

    st.markdown("## 📈 Gráficos")
    st.markdown(
        "<p style='color:#475569;font-size:13px;margin-bottom:12px'>"
        "Visualize séries completas ou personalizadas de qualquer indicador ou ativo.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#131929'>", unsafe_allow_html=True)

    fonte = st.radio("Fonte:", ["📊 BCB — Indicadores Brasil", "🌍 Yahoo Finance — Ativos Globais"],
                     horizontal=True)

    if fonte == "📊 BCB — Indicadores Brasil":
        col1, col2 = st.columns([2,2])
        with col1:
            ind = st.selectbox("Indicador", list(SGS.keys()))
        with col2:
            modo = st.selectbox("Período", [
                "Últimos 24 meses",
                "Últimos 5 anos",
                "Série completa desde o início",
                "Intervalo personalizado",
            ])

        d_ini = d_fim = None
        if modo == "Intervalo personalizado":
            c3, c4 = st.columns(2)
            with c3: d_ini = st.date_input("De", value=datetime.today()-timedelta(days=365*5))
            with c4: d_fim = st.date_input("Até", value=datetime.today())

        if st.button("📈 Carregar", type="primary"):
            cod, unit, freq, is_pct = SGS[ind]
            with st.spinner(f"Carregando {ind}..."):
                if modo == "Últimos 24 meses":
                    n = 25 if "Mensal" in freq else (12 if "Trim" in freq else 65)
                    df_g = get_bcb(cod, n)
                elif modo == "Últimos 5 anos":
                    n = 62 if "Mensal" in freq else (25 if "Trim" in freq else 365)
                    df_g = get_bcb(cod, n)
                elif modo == "Série completa desde o início":
                    df_g = get_bcb_full(cod)
                else:
                    if not d_ini or not d_fim or d_ini >= d_fim:
                        st.error("Datas inválidas.")
                        st.stop()
                    df_g = get_bcb_range(cod, d_ini.strftime("%d/%m/%Y"), d_fim.strftime("%d/%m/%Y"))

            if df_g.empty:
                st.warning("Sem dados para o período selecionado. A API BCB pode estar temporariamente indisponível.")
            else:
                st.success(f"✅ {len(df_g)} observações · {ind} · {freq}")
                titulo = f"{ind} ({unit}) — {modo}"
                bar_inds = {"IPCA","IGP-M","IPCA-15","PIB","Exportações","Importações"}
                if ind in bar_inds:
                    fig = bar_fig(df_g, titulo, suffix=f" {unit}", height=400)
                    if is_pct:
                        fig.update_yaxes(tickformat=".2f", ticksuffix="%")
                else:
                    fig = line_fig(df_g, titulo, "#6366f1", suffix=f" {unit}", height=400)
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

                df_dl = df_g.copy()
                df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
                csv = df_dl.to_csv(index=False).encode("utf-8-sig")
                st.download_button(f"💾 Baixar CSV ({len(df_dl)} linhas)", data=csv,
                                   file_name=f"{ind.replace(' ','_')}_{modo[:10]}.csv",
                                   mime="text/csv")

    else:  # Yahoo
        col1, col2 = st.columns([2,1])
        with col1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()))
        with col2: anos  = st.select_slider("Período (anos)", [1,2,3,5,10], value=5)

        if st.button("📈 Carregar", type="primary"):
            sym, unit, flag, _ = GLOBAL[ativo]
            with st.spinner(f"Carregando {ativo}..."):
                df_g = get_hist(sym, years=anos)
            if df_g.empty:
                st.warning("Sem dados históricos disponíveis.")
            else:
                st.success(f"✅ {len(df_g)} observações · {flag} {ativo}")
                fig = line_fig(df_g, f"{flag} {ativo} — {anos} ano(s)", "#6366f1",
                               suffix=f" {unit}", height=420)
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
                df_dl = df_g.copy()
                df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
                csv = df_dl.to_csv(index=False).encode("utf-8-sig")
                st.download_button(f"💾 Baixar CSV ({len(df_dl)} linhas)", data=csv,
                                   file_name=f"{ativo.replace(' ','_')}_{anos}a.csv",
                                   mime="text/csv")

# ═════════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ═════════════════════════════════════════════════════════════════════════════
else:
    st.markdown("## 📥 Exportar")
    st.markdown(
        "<p style='color:#475569;font-size:13px;margin-bottom:12px'>"
        "Baixe dados históricos em CSV. Fontes: BCB/SGS (Brasil) e Yahoo Finance (globais).</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#131929'>", unsafe_allow_html=True)

    fonte = st.radio("Fonte:", ["📊 BCB/SGS — Brasil", "🌍 Yahoo Finance — Globais"],
                     horizontal=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if fonte == "📊 BCB/SGS — Brasil":
        col1, col2, col3 = st.columns([2,1.5,1.5])
        with col1: ind = st.selectbox("Indicador", list(SGS.keys()), index=1)
        with col2: d_ini = st.date_input("De", value=datetime.today()-timedelta(days=365))
        with col3: d_fim = st.date_input("Até", value=datetime.today())

        modo_b = st.radio("Período:", ["Usar datas acima","Série completa desde o início"], horizontal=True)

        if st.button("⬇  Gerar CSV", type="primary"):
            cod, unit, freq, _ = SGS[ind]
            with st.spinner(f"Buscando {ind}..."):
                if modo_b == "Série completa desde o início":
                    df_exp = get_bcb_full(cod)
                else:
                    if d_ini >= d_fim:
                        st.error("Data início deve ser anterior à data fim.")
                        st.stop()
                    df_exp = get_bcb_range(cod, d_ini.strftime("%d/%m/%Y"), d_fim.strftime("%d/%m/%Y"))

            if df_exp.empty:
                st.warning("Nenhum dado encontrado. A API BCB pode estar temporariamente indisponível.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** — {ind} ({unit})")
                st.dataframe(df_out.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),
                             use_container_width=True,
                             height=min(380, 46 + len(df_out)*35))
                csv   = df_out.to_csv(index=False).encode("utf-8-sig")
                suf   = "completo" if "completa" in modo_b else f"{d_ini}_{d_fim}"
                nome  = f"{ind.replace(' ','_')}_{suf}.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    else:
        col1, col2 = st.columns([2,1])
        with col1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()))
        with col2: anos  = st.select_slider("Período (anos)", [1,2,3,5,10], value=5)

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
                st.dataframe(df_out.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),
                             use_container_width=True,
                             height=min(380, 46 + len(df_out)*35))
                csv  = df_out.to_csv(index=False).encode("utf-8-sig")
                nome = f"{ativo.replace(' ','_')}_{anos}anos.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    with st.expander("📋 Ver todos os indicadores e ativos disponíveis"):
        st.markdown("**BCB/SGS**")
        st.dataframe(pd.DataFrame([
            {"Indicador": k, "Cód. SGS": v[0], "Unidade": v[1], "Freq.": v[2]}
            for k, v in SGS.items()
        ]), hide_index=True, use_container_width=False)
        st.markdown("<br>**Yahoo Finance**", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Ativo": k, "Símbolo": v[0], "Unidade": v[1]}
            for k, v in GLOBAL.items()
        ]), hide_index=True, use_container_width=False)
