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

# ─── SESSION STATE ────────────────────────────────────────────────────────────
if "pagina"    not in st.session_state: st.session_state.pagina    = "Início"
if "sb_collapsed" not in st.session_state: st.session_state.sb_collapsed = False

collapsed = st.session_state.sb_collapsed
sb_w      = 60 if collapsed else 220

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*, html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; }}

/* ── Fundo principal ── */
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] {{
    background: #f0f2f5 !important;
}}
.main .block-container {{ padding-top:0 !important; padding-bottom:2rem; max-width:1400px; }}
footer,#MainMenu,header {{ visibility:hidden !important; }}
[data-testid="stToolbar"] {{ display:none !important; }}

/* ── Sidebar branca + largura dinâmica ── */
section[data-testid="stSidebar"] {{
    background: #ffffff !important;
    border-right: 1px solid #e8eaed !important;
    min-width: {sb_w}px !important;
    max-width: {sb_w}px !important;
    overflow: hidden !important;
    transition: min-width 0.2s, max-width 0.2s;
}}
section[data-testid="stSidebar"] > div:first-child {{
    padding: 0 !important;
    overflow: hidden !important;
}}
/* Esconde todos os widgets nativos na sidebar */
section[data-testid="stSidebar"] input[type="radio"],
section[data-testid="stSidebar"] [data-baseweb="radio"] {{ display:none !important; }}
section[data-testid="stSidebar"] label {{ display:none !important; }}
section[data-testid="stSidebar"] .stButton > button {{
    display:none !important;
}}

/* ── Cabeçalho de página ── */
.page-top {{
    background:#ffffff; border-bottom:1px solid #e8eaed;
    padding:15px 28px; margin:0 -3rem 22px -3rem;
    display:flex; align-items:center; justify-content:space-between;
}}
.page-top h1 {{ font-size:16px; font-weight:600; color:#111827; margin:0; }}
.page-top .ts {{ font-size:11px; color:#6b7280; text-align:right; line-height:1.5; }}

/* ── Títulos de seção ── */
.sec-title {{
    font-size:10px; font-weight:700; color:#6b7280;
    text-transform:uppercase; letter-spacing:2px;
    margin:20px 0 12px 0; padding-bottom:8px;
    border-bottom:1px solid #e2e5e9;
    display:flex; align-items:center; gap:8px;
}}

/* ── Badges ── */
.badge-live {{
    display:inline-block; background:#f0fdf4; border:1px solid #bbf7d0;
    color:#16a34a; font-size:9px; font-weight:600; padding:2px 8px;
    border-radius:20px; text-transform:none; letter-spacing:0;
}}
.badge-daily {{
    display:inline-block; background:#f5f3ff; border:1px solid #ddd6fe;
    color:#7c3aed; font-size:9px; font-weight:600; padding:2px 8px;
    border-radius:20px; text-transform:none; letter-spacing:0;
}}

/* ── Botões gerais ── */
.stButton > button {{
    background:#1a2035 !important; color:#ffffff !important;
    border:none !important; border-radius:7px !important;
    font-weight:600 !important; font-size:13px !important; padding:8px 18px !important;
}}
.stButton > button:hover {{ background:#2d3a56 !important; }}
.stDownloadButton > button {{
    background:#ffffff !important; color:#374151 !important;
    border:1px solid #e2e8f0 !important; border-radius:7px !important;
    font-weight:500 !important; font-size:12px !important;
}}

/* ── Selectboxes / inputs ── */
[data-testid="stSelectbox"] > div > div {{
    background:#ffffff !important; border:1px solid #e2e8f0 !important;
    border-radius:7px !important; color:#111827 !important;
}}
[data-testid="stSelectbox"] label,[data-testid="stDateInput"] label,
[data-testid="stSlider"] label,[data-testid="stRadio"] > label {{
    font-size:12px !important; font-weight:500 !important; color:#4b5563 !important;
}}

/* ── Tabs ── */
[data-testid="stTabs"] [data-testid="stTabsTabList"] {{
    background:transparent !important; border-bottom:1px solid #e8eaed !important; gap:0 !important;
}}
[data-testid="stTabs"] button[role="tab"] {{
    font-size:13px !important; font-weight:500 !important; color:#6b7280 !important;
    padding:8px 20px !important; border-radius:0 !important;
    border:none !important; border-bottom:2px solid transparent !important; background:transparent !important;
}}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
    color:#1a2035 !important; border-bottom:2px solid #1a2035 !important; font-weight:600 !important;
}}

/* ── Expander ── */
div[data-testid="stExpander"] {{
    background:#ffffff !important; border:1px solid #e8eaed !important; border-radius:10px !important;
}}
div[data-testid="stExpander"] summary p {{ color:#374151 !important; font-weight:500 !important; }}

/* ── Alertas ── */
[data-testid="stAlert"] {{ border-radius:8px !important; font-size:13px !important; }}

/* Sem fade de transição */
[data-testid="stMain"],[data-testid="stVerticalBlock"] {{
    animation:none !important; transition:none !important;
}}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE   = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
YAHOO_SNAP = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
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

CHART_CFG = {"displayModeBar": False, "staticPlot": False, "scrollZoom": False}

PLOT_BASE = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    font_color="#6b7280", font_family="Inter",
    margin=dict(l=0, r=4, t=36, b=0),
    xaxis=dict(gridcolor="#f1f5f9", showline=False,
               tickfont=dict(size=10, color="#9ca3af"), zeroline=False, fixedrange=True),
    yaxis=dict(gridcolor="#f1f5f9", showline=False,
               tickfont=dict(size=10, color="#9ca3af"), zeroline=False, fixedrange=True),
    title_font=dict(color="#374151", size=12, family="Inter"),
    hoverlabel=dict(bgcolor="#1a2035", font_size=12, font_color="#e2e8f0", bordercolor="#1a2035"),
    dragmode=False,
)
PLOT_INTER = {**PLOT_BASE,
    "xaxis": {**PLOT_BASE["xaxis"], "fixedrange": False},
    "yaxis": {**PLOT_BASE["yaxis"], "fixedrange": False},
    "dragmode": "pan",
}

# ─── UTILS ───────────────────────────────────────────────────────────────────
def hex_rgba(h, a=0.08):
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
    if valor_str is None: return None
    s = str(valor_str).strip().replace("\xa0","").replace(" ","")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:    return float(s)
    except: return None

# ─── BCB API — robusta com retry e fallback ───────────────────────────────────
def _bcb_fetch(url: str) -> list:
    """
    Tenta buscar a URL da API BCB com até 3 tentativas e fallback sem SSL.
    Retorna lista de dicts ou [] em caso de falha.
    """
    for attempt in range(3):
        try:
            kwargs = dict(headers=HEADERS, timeout=20)
            if attempt == 2:          # 3ª tentativa: desativa verificação SSL
                kwargs["verify"] = False
            r = requests.get(url, **kwargs)
            if r.status_code != 200:
                time.sleep(1)
                continue
            content_type = r.headers.get("Content-Type", "")
            if "html" in content_type.lower():
                time.sleep(1)
                continue
            data = r.json()
            if isinstance(data, dict):   # objeto de erro BCB
                time.sleep(1)
                continue
            if isinstance(data, list) and len(data) > 0:
                return data
            time.sleep(0.5)
        except requests.exceptions.SSLError:
            if attempt < 2:
                time.sleep(1)
                continue
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < 2:
                time.sleep(1)
                continue
        except Exception:
            break
    return []

def _build_df(raw: list) -> pd.DataFrame:
    if not raw: return pd.DataFrame(columns=["data","valor"])
    df = pd.DataFrame(raw)
    if "data" not in df.columns or "valor" not in df.columns:
        return pd.DataFrame(columns=["data","valor"])
    df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = df["valor"].apply(parse_bcb_valor)
    df = df.dropna(subset=["data","valor"]).sort_values("data").reset_index(drop=True)
    return df[["data","valor"]]

# Cache curto para resultados vazios (60s), longo para dados válidos (1h)
@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb(codigo: int, ultimos: int) -> pd.DataFrame:
    url = BCB_BASE.format(codigo=codigo) + f"/ultimos/{ultimos}?formato=json"
    raw = _bcb_fetch(url)
    if not raw:
        # Fallback: pede os últimos 30 via intervalo de datas
        hoje  = datetime.today()
        ini   = (hoje - timedelta(days=ultimos * 45)).strftime("%d/%m/%Y")
        fim   = hoje.strftime("%d/%m/%Y")
        url2  = BCB_BASE.format(codigo=codigo) + f"?formato=json&dataInicial={ini}&dataFinal={fim}"
        raw   = _bcb_fetch(url2)
    return _build_df(raw)

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb_full(codigo: int) -> pd.DataFrame:
    url = BCB_BASE.format(codigo=codigo) + "?formato=json"
    return _build_df(_bcb_fetch(url))

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb_range(codigo: int, ini: str, fim: str) -> pd.DataFrame:
    url = BCB_BASE.format(codigo=codigo) + f"?formato=json&dataInicial={ini}&dataFinal={fim}"
    return _build_df(_bcb_fetch(url))

# ─── YAHOO FINANCE ────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def get_quote(symbol: str) -> dict:
    try:
        r      = requests.get(YAHOO_SNAP.format(sym=symbol), headers=HEADERS, timeout=10)
        r.raise_for_status()
        data   = r.json()
        result = data["chart"]["result"][0]
        meta   = result["meta"]
        market_state = meta.get("marketState", "CLOSED")
        is_live      = market_state == "REGULAR"
        is_extended  = market_state in ("PRE","POST","PREPRE","POSTPOST")
        is_closed    = not (is_live or is_extended)

        if is_live or is_extended:
            price = meta.get("regularMarketPrice") or meta.get("previousClose")
            prev  = meta.get("chartPreviousClose") or meta.get("previousClose", price)
            close_date = None
        else:
            price = meta.get("previousClose") or meta.get("regularMarketPrice")
            prev  = meta.get("chartPreviousClose") or price
            ts_list = result.get("timestamp", [])
            if ts_list:
                close_date = datetime.fromtimestamp(ts_list[-1]).strftime("%d/%m/%Y")
            else:
                reg_ts     = meta.get("regularMarketTime")
                close_date = datetime.fromtimestamp(reg_ts).strftime("%d/%m/%Y") if reg_ts else None

        if price is None: return {}
        chg_p = ((price-prev)/prev*100) if (prev and prev!=0) else None
        chg_v = (price-prev) if prev else None
        return {"price":price,"prev":prev,"chg_p":chg_p,"chg_v":chg_v,
                "market":market_state,"is_live":is_live,
                "is_extended":is_extended,"is_closed":is_closed,"close_date":close_date}
    except:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(symbol, years=5):
    try:
        r    = requests.get(YAHOO_HIST.format(sym=symbol, y=years), headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        res  = data["chart"]["result"][0]
        ts   = res["timestamp"]
        vals = res["indicators"]["quote"][0]["close"]
        df   = pd.DataFrame({"data": pd.to_datetime(ts, unit="s"), "valor": vals})
        return df.dropna().reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

# ─── KPI CARD ─────────────────────────────────────────────────────────────────
import streamlit.components.v1 as components

def kpi(label, value, chg_p=None, sub="", invert=False, d=None):
    is_closed   = d.get("is_closed",   False) if d else False
    is_extended = d.get("is_extended", False) if d else False
    close_date  = d.get("close_date",  None)  if d else None

    if chg_p is not None:
        up  = (chg_p >= 0) if not invert else (chg_p < 0)
        cls = "pos" if up else "neg"
        arr = "▲" if chg_p >= 0 else "▼"
        dlt = f'<div class="d-{cls}">{arr} {abs(chg_p):.2f}%</div>'
    else:
        dlt = '<div class="d-neu">—</div>'

    sub_html = f'<div class="sub">{sub}</div>' if sub else ""

    ribbon = ""
    if is_closed and close_date:
        ribbon = f'<div class="ribbon">Fechamento {close_date}</div>'
    elif is_closed:
        ribbon = '<div class="ribbon">Último fechamento</div>'
    elif is_extended:
        mstate    = d.get("market","") if d else ""
        label_ext = "Pré-mercado" if "PRE" in mstate else "Pós-mercado"
        ribbon    = f'<div class="ribbon-ext">{label_ext}</div>'

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:'Inter',sans-serif}}
.card{{
  background:#ffffff; border:1px solid #e2e5e9; border-radius:12px;
  padding:16px 12px 14px 12px; text-align:center; min-height:112px;
  display:flex; flex-direction:column; justify-content:center; gap:4px;
  box-shadow:0 1px 3px rgba(0,0,0,0.05); overflow:hidden; position:relative;
}}
.ribbon{{
  position:absolute; top:0; right:0;
  background:#fef3c7; border-bottom-left-radius:8px;
  color:#92400e; font-size:9px; font-weight:600; padding:3px 9px; white-space:nowrap;
}}
.ribbon-ext{{
  position:absolute; top:0; right:0;
  background:#eff6ff; border-bottom-left-radius:8px;
  color:#1d4ed8; font-size:9px; font-weight:600; padding:3px 9px; white-space:nowrap;
}}
.lbl{{font-size:9px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:1.5px;margin-top:6px}}
.val{{font-size:19px;font-weight:700;color:#111827;line-height:1.2}}
.d-pos{{font-size:12px;font-weight:600;color:#16a34a}}
.d-neg{{font-size:12px;font-weight:600;color:#dc2626}}
.d-neu{{font-size:12px;color:#9ca3af}}
.sub{{font-size:10px;color:#9ca3af;margin-top:1px}}
</style></head><body>
<div class="card">
  {ribbon}
  <div class="lbl">{label}</div>
  <div class="val">{value}</div>
  {dlt}
  {sub_html}
</div></body></html>"""
    components.html(html, height=120)

# ─── CHART FACTORIES ──────────────────────────────────────────────────────────
def _apply_range(fig, df, suffix="", pad_pct=0.08):
    if df.empty: return fig
    y_min, y_max = df["valor"].min(), df["valor"].max()
    y_pad = (y_max-y_min)*pad_pct if (y_max-y_min)>0 else abs(y_max)*0.1 or 1
    x_min, x_max = df["data"].min(), df["data"].max()
    x_pad = (x_max-x_min)*0.02
    fig.update_xaxes(range=[x_min-x_pad, x_max+x_pad])
    fig.update_yaxes(range=[y_min-y_pad, y_max+y_pad],
                     tickformat=".2f",
                     ticksuffix=suffix.strip() if suffix.strip() else "")
    return fig

def line_fig(df, title, color="#1a2035", fill=True, suffix="", height=260, interactive=False):
    base = PLOT_INTER if interactive else PLOT_BASE
    fig  = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"], mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_rgba(color, 0.07),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**base, title=title, height=height)
    if not interactive: fig = _apply_range(fig, df, suffix)
    return fig

def bar_fig(df, title, suffix="", height=260, interactive=False):
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in df["valor"]]
    base   = PLOT_INTER if interactive else PLOT_BASE
    fig    = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=colors, marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**base, title=title, height=height)
    if not interactive: fig = _apply_range(fig, df, suffix, pad_pct=0.15)
    return fig

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
# SVGs Feather-style, 16×16
ICONS = {
    "Início":          '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    "Mercados Globais":'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    "Gráficos":        '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "Exportar":        '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
}
NAV_KEYS = ["Início", "Mercados Globais", "Gráficos", "Exportar"]

# Ícone do toggle (chevron)
CHEV_LEFT  = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>'
CHEV_RIGHT = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>'

with st.sidebar:
    if collapsed:
        # ── MODO COLAPSADO: só ícones ───────────────────────────────────────
        # Botão de toggle (expand)
        st.markdown(
            "<div style='padding:14px 0 10px 0;display:flex;justify-content:center'>",
            unsafe_allow_html=True,
        )
        if st.button("▶", key="sb_expand", help="Expandir menu",
                     use_container_width=True):
            st.session_state.sb_collapsed = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<div style='height:1px;background:#e8eaed;margin:0 8px 10px 8px'></div>",
            unsafe_allow_html=True,
        )

        # Ícones de navegação (um por linha, centralizado)
        for key in NAV_KEYS:
            is_active = st.session_state.pagina == key
            color     = "#1a2035" if is_active else "#9ca3af"
            bg        = "#f0f2ff" if is_active else "transparent"
            icon_svg  = ICONS[key].format(c=color)
            st.markdown(
                f"<div style='display:flex;justify-content:center;margin:2px 6px;"
                f"padding:9px 0;border-radius:8px;background:{bg};cursor:pointer'>"
                f"<span title='{key}'>{icon_svg}</span></div>",
                unsafe_allow_html=True,
            )
            if st.button(key, key=f"nav_c_{key}", use_container_width=True):
                st.session_state.pagina = key
                st.rerun()

        # CSS para tornar os botões invisíveis mas clicáveis sobre os ícones
        st.markdown("""
        <style>
        [data-testid="stSidebar"] .stButton { position:relative; margin-top:-44px !important; }
        [data-testid="stSidebar"] .stButton > button {
            display:block !important; opacity:0 !important;
            width:100% !important; height:38px !important;
            cursor:pointer !important; background:transparent !important;
            border:none !important; position:relative; z-index:5;
        }
        </style>
        """, unsafe_allow_html=True)

    else:
        # ── MODO EXPANDIDO ──────────────────────────────────────────────────
        # Header com logo + botão collapse
        st.markdown(
            "<div style='padding:18px 16px 10px 18px;display:flex;"
            "align-items:flex-start;justify-content:space-between'>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div>"
            "<div style='font-size:9px;font-weight:700;color:#d1d5db;"
            "letter-spacing:3px;text-transform:uppercase;margin-bottom:3px'>BR</div>"
            "<div style='font-size:15px;font-weight:700;color:#111827;"
            "letter-spacing:-0.3px'>Macro Brasil</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("◀", key="sb_collapse", help="Recolher menu"):
            st.session_state.sb_collapsed = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # Estilo do botão toggle
        st.markdown("""
        <style>
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
            background: transparent !important;
            border: 1px solid #e8eaed !important;
            color: #9ca3af !important;
            padding: 3px 7px !important;
            font-size: 11px !important;
            border-radius: 6px !important;
            min-height: unset !important;
            height: 26px !important;
            width: 28px !important;
            display: block !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
            background: #f5f6f8 !important;
            color: #374151 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown(
            "<div style='height:1px;background:#e8eaed;margin:0 0 8px 0'></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:9px;font-weight:700;color:#9ca3af;"
            "text-transform:uppercase;letter-spacing:2px;"
            "padding:6px 18px 6px 18px'>Navegação</div>",
            unsafe_allow_html=True,
        )

        for key in NAV_KEYS:
            is_active = st.session_state.pagina == key
            color     = "#1a2035" if is_active else "#9ca3af"
            bg        = "#f0f2ff" if is_active else "transparent"
            fw        = "600"    if is_active else "500"
            tc        = "#1a2035" if is_active else "#4b5563"
            bl        = "3px solid #1a2035" if is_active else "3px solid transparent"
            icon_svg  = ICONS[key].format(c=color)
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;"
                f"padding:9px 12px 9px 14px;margin:1px 6px;border-radius:7px;"
                f"background:{bg};border-left:{bl};cursor:pointer'>"
                f"{icon_svg}"
                f"<span style='font-size:13px;font-weight:{fw};color:{tc};font-family:Inter,sans-serif'>"
                f"{key}</span></div>",
                unsafe_allow_html=True,
            )
            if st.button(key, key=f"nav_e_{key}", use_container_width=True):
                st.session_state.pagina = key
                st.rerun()

        # Botões de nav invisíveis sobrepostos
        st.markdown("""
        <style>
        [data-testid="stSidebar"] .stButton { position:relative; margin-top:-42px !important; }
        [data-testid="stSidebar"] .stButton > button {
            display:block !important; opacity:0 !important;
            width:100% !important; height:38px !important;
            cursor:pointer !important; background:transparent !important;
            border:none !important; position:relative; z-index:5;
        }
        </style>
        """, unsafe_allow_html=True)

        # Rodapé
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='height:1px;background:#e8eaed;margin:0 0 10px 0'></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:9px;color:#d1d5db;line-height:1.9;padding:0 18px 16px 18px'>"
            "Fontes: BCB/SGS · Yahoo Finance<br>"
            "Mercados: ↻ 60s &nbsp;|&nbsp; BCB: ↻ 1h"
            "</div>",
            unsafe_allow_html=True,
        )

pagina = st.session_state.pagina

# ═════════════════════════════════════════════════════════════════════════════
# 🏠 INÍCIO
# ═════════════════════════════════════════════════════════════════════════════
if pagina == "Início":

    st.markdown(
        f"<div class='page-top'><h1>Dashboard Macro Brasil</h1>"
        f"<div class='ts'>Atualizado<br>"
        f"<strong style='color:#374151'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

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
        kpi("IBOVESPA",
            fmt(v, 0)+" pts" if v else "—",
            ibov_d.get("chg_p"),
            f"Var. dia: {fmt(ibov_d.get('chg_v'),0)} pts" if ibov_d.get("chg_v") is not None else "—",
            d=ibov_d)
    with c2:
        v = usd_d.get("price")
        kpi("Dólar (USD/BRL)",
            f"R$ {fmt(v,4)}" if v else "—",
            usd_d.get("chg_p"),
            f"Ant.: R$ {fmt(usd_d.get('prev'),4)}" if v else "—",
            invert=True, d=usd_d)
    with c3:
        v = eur_d.get("price")
        kpi("Euro (EUR/BRL)",
            f"R$ {fmt(v,4)}" if v else "—",
            eur_d.get("chg_p"),
            f"Ant.: R$ {fmt(eur_d.get('prev'),4)}" if v else "—",
            invert=True, d=eur_d)

    # ── KPIs Econômicos ───────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Indicadores Econômicos'
        '<span class="badge-daily">↻ diário</span></div>',
        unsafe_allow_html=True,
    )
    c4, c5, c6 = st.columns(3)
    with c4:
        if not df_sel.empty:
            v, ref = df_sel["valor"].iloc[-1], df_sel["data"].iloc[-1].strftime("%b/%Y")
            kpi("Selic", f"{fmt(v)}% a.a.", sub=f"Ref: {ref}")
        else:
            kpi("Selic", "—", sub="BCB indisponível")
    with c5:
        if not df_ipca.empty:
            v, ref = df_ipca["valor"].iloc[-1], df_ipca["data"].iloc[-1].strftime("%b/%Y")
            delta  = (df_ipca["valor"].iloc[-1]-df_ipca["valor"].iloc[-2]) if len(df_ipca)>=2 else None
            kpi("IPCA", f"{fmt(v)}% mês",
                chg_p=float(delta) if delta is not None else None, sub=f"Ref: {ref}")
        else:
            kpi("IPCA", "—", sub="BCB indisponível")
    with c6:
        if not df_des.empty:
            v, ref = df_des["valor"].iloc[-1], df_des["data"].iloc[-1].strftime("%b/%Y")
            kpi("Desemprego (PNAD)", f"{fmt(v)}%", sub=f"Ref: {ref}")
        else:
            kpi("Desemprego (PNAD)", "—", sub="BCB indisponível")

    # ── Gráficos ──────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Histórico — 12 meses'
        '<span style="font-size:10px;font-weight:400;color:#9ca3af;text-transform:none;'
        'letter-spacing:0;margin-left:4px">→ série completa em Gráficos</span></div>',
        unsafe_allow_html=True,
    )
    ca, cb = st.columns(2)
    with ca:
        if not df_sel.empty:
            st.plotly_chart(line_fig(df_sel,"Selic (% a.a.)","#1a2035",suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.warning("⚠️ Selic: indisponível.")
    with cb:
        if not df_ipca.empty:
            st.plotly_chart(bar_fig(df_ipca,"IPCA (% ao mês)",suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.warning("⚠️ IPCA: indisponível.")

    cc, cd = st.columns(2)
    with cc:
        df_cam30 = df_cam.tail(30) if not df_cam.empty else df_cam
        if not df_cam30.empty:
            st.plotly_chart(
                line_fig(df_cam30,"Dólar PTAX — 30 dias úteis (R$)","#d97706",suffix=" R$"),
                use_container_width=True, config=CHART_CFG)
        else: st.warning("⚠️ Dólar PTAX: indisponível.")
    with cd:
        if not df_ibc.empty:
            st.plotly_chart(line_fig(df_ibc,"IBC-Br","#0891b2",fill=False),
                            use_container_width=True, config=CHART_CFG)
        else: st.warning("⚠️ IBC-Br: indisponível.")

    ce, cf = st.columns(2)
    with ce:
        if not df_pib.empty:
            st.plotly_chart(bar_fig(df_pib,"PIB — variação trimestral (%)",suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else: st.warning("⚠️ PIB: indisponível.")
    with cf:
        if not df_des.empty:
            st.plotly_chart(
                line_fig(df_des,"Desemprego PNAD (%)","#dc2626",fill=True,suffix="%"),
                use_container_width=True, config=CHART_CFG)
        else: st.warning("⚠️ Desemprego: indisponível.")

    st.markdown(
        "<div style='text-align:center;color:#d1d5db;font-size:10px;"
        "margin-top:20px;margin-bottom:8px'>"
        "Yahoo Finance (↻60s) • BCB/SGS (↻1h)</div>",
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# 🌍 MERCADOS GLOBAIS
# ═════════════════════════════════════════════════════════════════════════════
elif pagina == "Mercados Globais":

    st.markdown(
        f"<div class='page-top'><h1>Mercados Globais</h1>"
        f"<div class='ts'>Atualizado<br>"
        f"<strong style='color:#374151'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    grupos = {
        "Brasil":       ["IBOVESPA","Dólar (USD/BRL)","Euro (EUR/BRL)"],
        "Índices EUA":  ["S&P 500","Nasdaq 100","Dow Jones"],
        "Europa":       ["FTSE 100","DAX"],
        "Energia":      ["Petróleo Brent","Petróleo WTI"],
        "Metais":       ["Ouro","Prata","Cobre"],
        "Cripto":       ["Bitcoin","Ethereum"],
    }

    for grupo, ativos in grupos.items():
        st.markdown(
            f'<div class="sec-title">{grupo}'
            '<span class="badge-live">↻ 60s</span></div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(ativos))
        for i, nome in enumerate(ativos):
            sym, unit, inv = GLOBAL[nome]
            d = get_quote(sym)
            with cols[i]:
                v       = d.get("price")
                prefix  = "R$ " if unit=="R$" else ("US$ " if "US$" in unit else "")
                dec     = 0 if unit=="pts" else 2
                val_str = f"{prefix}{fmt(v,dec)}" if v else "—"
                kpi(nome, val_str, d.get("chg_p"),
                    sub=f"Ant.: {prefix}{fmt(d.get('prev'),dec)}" if v else "",
                    invert=inv, d=d)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    st.markdown('<div class="sec-title">Histórico — 2 anos</div>', unsafe_allow_html=True)
    destaques = [
        ("IBOVESPA",       "^BVSP",  "#1a2035", "pts"),
        ("S&P 500",        "^GSPC",  "#0891b2", "pts"),
        ("Petróleo Brent", "BZ=F",   "#d97706", "US$"),
        ("Ouro",           "GC=F",   "#b45309", "US$"),
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
elif pagina == "Gráficos":

    st.markdown(
        "<div class='page-top'><h1>Gráficos</h1>"
        "<div class='ts'>Série completa · filtro por período</div></div>",
        unsafe_allow_html=True,
    )

    tab_bcb, tab_yahoo = st.tabs(["BCB — Indicadores Brasil", "Yahoo Finance — Ativos Globais"])

    with tab_bcb:
        col1, _ = st.columns([2, 3])
        with col1:
            ind = st.selectbox("Indicador", list(SGS.keys()), key="graf_ind")
        cod, unit, freq, tipo = SGS[ind]

        with st.spinner(f"Carregando série de {ind}..."):
            df_full = get_bcb_full(cod)

        if df_full.empty:
            st.warning("⚠️ Sem dados. A API BCB pode estar temporariamente indisponível.")
        else:
            date_min      = df_full["data"].min().date()
            date_max      = df_full["data"].max().date()
            default_start = max(date_min, (df_full["data"].max()-pd.DateOffset(months=12)).date())

            st.markdown(
                f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px 0'>"
                f"Disponível: <strong style='color:#374151'>{date_min.strftime('%d/%m/%Y')}</strong>"
                f" → <strong style='color:#374151'>{date_max.strftime('%d/%m/%Y')}</strong>"
                f" &nbsp;·&nbsp; {len(df_full)} obs.</div>",
                unsafe_allow_html=True,
            )
            c3, c4, c5 = st.columns([2, 2, 1])
            with c3:
                d_ini = st.date_input("De", value=default_start,
                                      min_value=date_min, max_value=date_max, key="graf_ini")
            with c4:
                d_fim = st.date_input("Até", value=date_max,
                                      min_value=date_min, max_value=date_max, key="graf_fim")
            with c5:
                st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                if st.button("Série completa", key="graf_reset"):
                    st.session_state["graf_ini"] = date_min
                    st.session_state["graf_fim"] = date_max
                    st.rerun()

            if d_ini >= d_fim:
                st.error("⚠️ Data início deve ser anterior à data fim.")
            else:
                mask = (df_full["data"].dt.date >= d_ini) & (df_full["data"].dt.date <= d_fim)
                df_g = df_full[mask].copy()
                if df_g.empty:
                    st.warning("Nenhuma observação no período selecionado.")
                else:
                    st.success(f"✅ {len(df_g)} observações · {ind} ({unit}) · {freq}")
                    titulo = f"{ind} ({unit})"
                    fig = (
                        bar_fig(df_g, titulo, suffix=f" {unit}", height=420, interactive=True)
                        if tipo == "bar"
                        else line_fig(df_g, titulo, "#1a2035", suffix=f" {unit}", height=420, interactive=True)
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                    config={**CHART_CFG, "scrollZoom": True})
                    df_dl = df_g.copy()
                    df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
                    csv = df_dl.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        f"💾 Baixar CSV ({len(df_dl)} linhas)", data=csv,
                        file_name=f"{ind.replace(' ','_')}_{d_ini}_{d_fim}.csv", mime="text/csv")

    with tab_yahoo:
        col1, col2 = st.columns([2, 1])
        with col1:
            ativo = st.selectbox("Ativo", list(GLOBAL.keys()), key="graf_ativo")
        with col2:
            anos = st.select_slider("Período (anos)", [1,2,3,5,10], value=5, key="graf_anos")

        sym, unit, _ = GLOBAL[ativo]
        with st.spinner(f"Carregando {ativo}..."):
            df_g = get_hist(sym, years=anos)

        if df_g.empty:
            st.warning("Sem dados históricos disponíveis.")
        else:
            st.success(f"✅ {len(df_g)} observações · {ativo}")
            fig = line_fig(df_g, f"{ativo} — {anos} ano(s)",
                           "#1a2035", suffix=f" {unit}", height=420, interactive=True)
            st.plotly_chart(fig, use_container_width=True,
                            config={**CHART_CFG, "scrollZoom": True})
            df_dl = df_g.copy()
            df_dl["data"] = df_dl["data"].dt.strftime("%d/%m/%Y")
            csv = df_dl.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                f"💾 Baixar CSV ({len(df_dl)} linhas)", data=csv,
                file_name=f"{ativo.replace(' ','_')}_{anos}a.csv", mime="text/csv")

# ═════════════════════════════════════════════════════════════════════════════
# 📥 EXPORTAR
# ═════════════════════════════════════════════════════════════════════════════
else:

    st.markdown(
        "<div class='page-top'><h1>Exportar dados</h1>"
        "<div class='ts'>BCB/SGS (Brasil) · Yahoo Finance (globais)</div></div>",
        unsafe_allow_html=True,
    )

    fonte = st.radio("Fonte:", ["BCB/SGS — Brasil", "Yahoo Finance — Globais"], horizontal=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if fonte == "BCB/SGS — Brasil":
        col1, col2, col3 = st.columns([2, 1.5, 1.5])
        with col1: ind   = st.selectbox("Indicador", list(SGS.keys()), index=1)
        with col2: d_ini = st.date_input("De", value=datetime.today()-timedelta(days=365))
        with col3: d_fim = st.date_input("Até", value=datetime.today())

        modo_b = st.radio("Período:", ["Usar datas acima", "Série completa desde o início"],
                          horizontal=True)

        if st.button("Gerar CSV", type="primary"):
            cod, unit, freq, _ = SGS[ind]
            with st.spinner(f"Buscando {ind}..."):
                if "completa" in modo_b:
                    df_exp = get_bcb_full(cod)
                else:
                    if d_ini >= d_fim:
                        st.error("Data início deve ser anterior à data fim.")
                        st.stop()
                    df_exp = get_bcb_range(cod, d_ini.strftime("%d/%m/%Y"), d_fim.strftime("%d/%m/%Y"))

            if df_exp.empty:
                st.warning("Nenhum dado encontrado. Verifique a disponibilidade da API BCB.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** — {ind} ({unit})")
                st.dataframe(
                    df_out.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),
                    use_container_width=True, height=min(380, 46+len(df_out)*35))
                csv  = df_out.to_csv(index=False).encode("utf-8-sig")
                suf  = "completo" if "completa" in modo_b else f"{d_ini}_{d_fim}"
                nome = f"{ind.replace(' ','_')}_{suf}.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")
    else:
        col1, col2 = st.columns([2, 1])
        with col1: ativo = st.selectbox("Ativo", list(GLOBAL.keys()))
        with col2: anos  = st.select_slider("Período (anos)", [1,2,3,5,10], value=5)

        if st.button("Gerar CSV", type="primary"):
            sym, unit, _ = GLOBAL[ativo]
            with st.spinner(f"Buscando {ativo}..."):
                df_exp = get_hist(sym, years=anos)

            if df_exp.empty:
                st.warning("Sem dados disponíveis.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ **{len(df_out)} registros** — {ativo}")
                st.dataframe(
                    df_out.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),
                    use_container_width=True, height=min(380, 46+len(df_out)*35))
                csv  = df_out.to_csv(index=False).encode("utf-8-sig")
                nome = f"{ativo.replace(' ','_')}_{anos}anos.csv"
                st.download_button(f"💾 Baixar {nome}", data=csv, file_name=nome, mime="text/csv")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    with st.expander("Ver todos os indicadores e ativos disponíveis"):
        st.markdown("**BCB/SGS — Indicadores Brasil**")
        st.dataframe(pd.DataFrame([
            {"Indicador":k,"Cód. SGS":v[0],"Unidade":v[1],"Freq.":v[2]}
            for k,v in SGS.items()
        ]), hide_index=True, use_container_width=False)
        st.markdown("<br>**Yahoo Finance — Ativos Globais**", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Ativo":k,"Símbolo":v[0],"Unidade":v[1]}
            for k,v in GLOBAL.items()
        ]), hide_index=True, use_container_width=False)
