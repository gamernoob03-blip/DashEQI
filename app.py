"""
Dashboard Macro Brasil — arquivo único, sem dependências locais
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

st.set_page_config(page_title="Macro Brasil", page_icon="🇧🇷",
                   layout="wide", initial_sidebar_state="expanded")

TZ_BRT = ZoneInfo("America/Sao_Paulo")
def now_brt(): return datetime.now(TZ_BRT)

# ── Constantes ────────────────────────────────────────────────────────────────
BCB_BASE   = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{c}/dados"
YAHOO_SNAP = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range=5d"
YAHOO_HIST = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range={y}y"
HDRS       = {"User-Agent":"Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36","Accept":"application/json"}
CHART_CFG  = {"displayModeBar": False, "scrollZoom": False}

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
NAV = [("⌂","Início"),("◎","Mercados Globais"),("⌇","Gráficos"),("↓","Exportar")]

# ── Session state ─────────────────────────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state.pagina = "Início"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*,[class*="css"]{font-family:'Inter',sans-serif!important}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f0f2f5!important}
.main .block-container{padding-top:0!important;padding-bottom:2rem;max-width:1400px}
footer,#MainMenu,header{visibility:hidden!important}
[data-testid="stToolbar"]{display:none!important}
[data-testid="stMetric"]{background:#fff!important;border:1px solid #e2e5e9!important;border-radius:12px!important;padding:16px!important;box-shadow:0 1px 3px rgba(0,0,0,.05)!important;text-align:center!important}
[data-testid="stMetricLabel"]>div{justify-content:center!important}
[data-testid="stMetricLabel"] p{font-size:10px!important;font-weight:700!important;color:#6b7280!important;text-transform:uppercase!important;letter-spacing:1.5px!important}
[data-testid="stMetricValue"]>div{justify-content:center!important}
[data-testid="stMetricValue"] p{font-size:22px!important;font-weight:700!important;color:#111827!important}
[data-testid="stMetricDelta"]>div{justify-content:center!important}
[data-testid="stMetricDelta"] p{font-size:12px!important;font-weight:600!important;color:#6b7280!important}
[data-testid="stCaptionContainer"] p{font-size:10px!important;color:#9ca3af!important;text-align:center!important;margin:0!important}
.page-top{background:#fff;border-bottom:1px solid #e8eaed;padding:15px 28px;margin:0 -3rem 22px -3rem;display:flex;align-items:center;justify-content:space-between}
.page-top h1{font-size:16px;font-weight:600;color:#111827;margin:0}
.page-top .ts{font-size:11px;color:#6b7280;text-align:right;line-height:1.5}
.sec-title{font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin:20px 0 12px;padding-bottom:8px;border-bottom:1px solid #e2e5e9;display:flex;align-items:center;gap:8px}
.badge-live{display:inline-block;background:#f0fdf4;border:1px solid #bbf7d0;color:#16a34a;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px}
.badge-daily{display:inline-block;background:#f5f3ff;border:1px solid #ddd6fe;color:#7c3aed;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px}
.main .stButton>button{background:#1a2035!important;color:#fff!important;border:none!important;border-radius:7px!important;font-weight:600!important;font-size:13px!important;padding:8px 18px!important}
.main .stButton>button:hover{background:#2d3a56!important}
.stDownloadButton>button{background:#fff!important;color:#374151!important;border:1px solid #e2e8f0!important;border-radius:7px!important}
[data-testid="stSelectbox"]>div>div{background:#fff!important;border:1px solid #e2e8f0!important;border-radius:7px!important}
[data-testid="stTabs"] [data-testid="stTabsTabList"]{background:transparent!important;border-bottom:1px solid #e8eaed!important}
[data-testid="stTabs"] button[role="tab"]{font-size:13px!important;color:#6b7280!important;padding:8px 20px!important;border:none!important;border-bottom:2px solid transparent!important;background:transparent!important}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#1a2035!important;border-bottom:2px solid #1a2035!important;font-weight:600!important}
div[data-testid="stExpander"]{background:#fff!important;border:1px solid #e8eaed!important;border-radius:10px!important}

/* ── Sidebar: largura fixa, sem redimensionamento ── */
section[data-testid="stSidebar"]{
    min-width:260px!important;
    max-width:260px!important;
    width:260px!important;
}
/* Oculta o handle de arrastar a sidebar */
[data-testid="stSidebarResizer"]{display:none!important}

/* ── Botão colapso: esconde texto Material Icons, substitui por ‹ › ── */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"]{
    position:fixed!important;
    top:12px!important;
    z-index:999!important;
}
[data-testid="stSidebarCollapseButton"]  { left:268px!important; }
[data-testid="stSidebarCollapsedControl"]{ left:8px!important; }

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button{
    width:28px!important; height:28px!important;
    padding:0!important; overflow:hidden!important;
    border:1px solid #e2e8f0!important;
    border-radius:6px!important;
    background:#ffffff!important;
    box-shadow:0 1px 3px rgba(0,0,0,.08)!important;
    position:relative!important;
}
/* Esconde o texto/ícone nativo dentro do botão */
[data-testid="stSidebarCollapseButton"] button *,
[data-testid="stSidebarCollapsedControl"] button *{
    font-size:0!important;
    color:transparent!important;
    fill:transparent!important;
}
/* Injeta seta via pseudo-elemento */
[data-testid="stSidebarCollapseButton"] button::after{
    content:"‹";
    font-size:18px!important;
    color:#6b7280!important;
    position:absolute; top:50%; left:50%;
    transform:translate(-50%,-50%);
    line-height:1;
}
[data-testid="stSidebarCollapsedControl"] button::after{
    content:"›";
    font-size:18px!important;
    color:#6b7280!important;
    position:absolute; top:50%; left:50%;
    transform:translate(-50%,-50%);
    line-height:1;
}
</style>""", unsafe_allow_html=True)

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
    st.markdown(f"<div class='page-top'><h1>{title}</h1><div class='ts'>Atualizado<br><strong style='color:#374151'>{ts} (Brasília)</strong></div></div>", unsafe_allow_html=True)

def kpi_card(label, value, chg_p=None, sub="", invert=False, d=None):
    d = d or {}
    cd, ms = d.get("close_date"), d.get("market","")
    if d.get("is_closed") and cd:   st.caption(f"🕐 Fechamento {cd}")
    elif d.get("is_closed"):        st.caption("🕐 Último fechamento")
    elif d.get("is_extended"):      st.caption(f"⏳ {'Pré' if 'PRE' in ms else 'Pós'}-mercado")
    delta = f"{'▲' if chg_p>=0 else '▼'} {abs(chg_p):.2f}%" if chg_p is not None else None
    st.metric(label=label, value=value, delta=delta, delta_color="off", help=sub or None)
    if sub: st.caption(sub)

# ── Helpers Plotly ────────────────────────────────────────────────────────────
_B = dict(paper_bgcolor="#fff",plot_bgcolor="#fff",font_color="#6b7280",font_family="Inter",
          margin=dict(l=0,r=4,t=36,b=0),
          xaxis=dict(gridcolor="#f1f5f9",showline=False,tickfont=dict(size=10,color="#9ca3af"),zeroline=False,fixedrange=True),
          yaxis=dict(gridcolor="#f1f5f9",showline=False,tickfont=dict(size=10,color="#9ca3af"),zeroline=False,fixedrange=True),
          title_font=dict(color="#374151",size=12,family="Inter"),
          hoverlabel=dict(bgcolor="#1a2035",font_size=12,font_color="#e2e8f0"),dragmode=False)
_I = {**_B,"xaxis":{**_B["xaxis"],"fixedrange":False},"yaxis":{**_B["yaxis"],"fixedrange":False},"dragmode":"pan"}

def _rng(fig, df, sfx="", pad=0.08):
    if df.empty: return fig
    mn,mx = df["valor"].min(),df["valor"].max()
    yd = (mx-mn)*pad if mx!=mn else abs(mx)*0.1 or 1
    xd = (df["data"].max()-df["data"].min())*0.02
    fig.update_xaxes(range=[df["data"].min()-xd, df["data"].max()+xd])
    fig.update_yaxes(range=[mn-yd,mx+yd],tickformat=".2f",ticksuffix=sfx.strip())
    return fig

def line_fig(df, title, color="#1a2035", fill=True, suffix="", height=260, inter=False):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["data"],y=df["valor"],mode="lines",line=dict(color=color,width=2),
        fill="tozeroy" if fill else "none",fillcolor=hex_rgba(color,.07),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>"))
    fig.update_layout(**(_I if inter else _B),title=title,height=height)
    return fig if inter else _rng(fig,df,suffix)

def bar_fig(df, title, suffix="", height=260, inter=False):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["data"],y=df["valor"],
        marker_color=["#16a34a" if v>=0 else "#dc2626" for v in df["valor"]],marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>"))
    fig.update_layout(**(_I if inter else _B),title=title,height=height)
    return fig if inter else _rng(fig,df,suffix,.15)

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

# ── Data Yahoo ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60,show_spinner=False)
def get_quote(sym):
    try:
        meta=requests.get(YAHOO_SNAP.format(s=sym),headers=HDRS,timeout=10).json()["chart"]["result"][0]["meta"]
        ms=meta.get("marketState","CLOSED"); live=ms=="REGULAR"; ext=ms in("PRE","POST","PREPRE","POSTPOST")
        if live or ext:
            price=meta.get("regularMarketPrice") or meta.get("previousClose")
            prev=meta.get("chartPreviousClose") or meta.get("previousClose",price); cd=None
        else:
            price=meta.get("previousClose") or meta.get("regularMarketPrice")
            prev=meta.get("chartPreviousClose") or price
            rt=meta.get("regularMarketTime"); cd=datetime.fromtimestamp(rt).strftime("%d/%m/%Y") if rt else None
        if price is None: return {}
        return {"price":price,"prev":prev,"chg_p":((price-prev)/prev*100) if prev else None,
                "chg_v":(price-prev) if prev else None,"market":ms,
                "is_live":live,"is_extended":ext,"is_closed":not(live or ext),"close_date":cd}
    except: return {}

@st.cache_data(ttl=3600,show_spinner=False)
def get_hist(sym,years=5):
    try:
        res=requests.get(YAHOO_HIST.format(s=sym,y=years),headers=HDRS,timeout=12).json()["chart"]["result"][0]
        df=pd.DataFrame({"data":pd.to_datetime(res["timestamp"],unit="s"),"valor":res["indicators"]["quote"][0]["close"]})
        return df.dropna().reset_index(drop=True)
    except: return pd.DataFrame(columns=["data","valor"])

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div style='padding:16px 0 4px 4px'>"
                "<span style='font-size:9px;font-weight:700;color:#aaa;letter-spacing:3px'>BR</span>"
                "<span style='font-size:16px;font-weight:700;color:#111827;margin-left:6px'>Macro Brasil</span>"
                "</div>", unsafe_allow_html=True)
    st.caption(f"🕐 {now_brt().strftime('%d/%m/%Y  %H:%M')} (Brasília)")
    st.divider()
    for icon, label in NAV:
        if st.button(f"{icon}  {label}", key=f"nav_{label}",
                     type="primary" if st.session_state.pagina==label else "secondary",
                     use_container_width=True):
            st.session_state.pagina = label
            st.rerun()
    st.divider()
    st.caption("Fontes: BCB/SGS · Yahoo Finance")
    st.caption("Mercados ↻60s · BCB ↻1h")

# ══════════════════════════════════════════════════════════════════════════════
# INÍCIO
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pagina == "Início":
    page_header("Dashboard Macro Brasil")
    with st.spinner("Carregando..."):
        ibov=get_quote("^BVSP"); usd=get_quote("USDBRL=X"); eur=get_quote("EURBRL=X")
        dsel=get_bcb(432,13); dipca=get_bcb(433,13); dibc=get_bcb(24363,13)
        dcam=get_bcb(1,50);   dpib=get_bcb(4380,8);  ddes=get_bcb(24369,8)

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
        kpi_card("Selic",f"{fmt(dsel['valor'].iloc[-1])}% a.a." if not dsel.empty else "—",
                 sub=f"Ref: {dsel['data'].iloc[-1].strftime('%b/%Y')}" if not dsel.empty else "BCB indisponível")
    with c5:
        if not dipca.empty:
            v=dipca["valor"].iloc[-1]
            d2=float(v-dipca["valor"].iloc[-2]) if len(dipca)>=2 else None
            kpi_card("IPCA",f"{fmt(v)}% mês",chg_p=d2,sub=f"Ref: {dipca['data'].iloc[-1].strftime('%b/%Y')}")
        else: kpi_card("IPCA","—",sub="BCB indisponível")
    with c6:
        kpi_card("Desemprego (PNAD)",f"{fmt(ddes['valor'].iloc[-1])}%" if not ddes.empty else "—",
                 sub=f"Ref: {ddes['data'].iloc[-1].strftime('%b/%Y')}" if not ddes.empty else "BCB indisponível")

    st.markdown('<div class="sec-title">Histórico — 12 meses <span style="font-size:10px;font-weight:400;color:#9ca3af;text-transform:none;letter-spacing:0;margin-left:4px">→ série completa em Gráficos</span></div>',unsafe_allow_html=True)
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
# MERCADOS GLOBAIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Mercados Globais":
    page_header("Mercados Globais")
    GRUPOS={"Brasil":["IBOVESPA","Dólar (USD/BRL)","Euro (EUR/BRL)"],
            "Índices EUA":["S&P 500","Nasdaq 100","Dow Jones"],
            "Europa":["FTSE 100","DAX"],"Energia":["Petróleo Brent","Petróleo WTI"],
            "Metais":["Ouro","Prata","Cobre"],"Cripto":["Bitcoin","Ethereum"]}
    for grupo,ativos in GRUPOS.items():
        sec_title(grupo,"↻ 60s","badge-live")
        cols=st.columns(len(ativos))
        for i,nome in enumerate(ativos):
            sym,unit,inv=GLOBAL[nome]; d=get_quote(sym)
            with cols[i]:
                v=d.get("price"); px="R$ " if unit=="R$" else ("US$ " if "US$" in unit else ""); dec=0 if unit=="pts" else 2
                kpi_card(nome,f"{px}{fmt(v,dec)}" if v else "—",d.get("chg_p"),
                         sub=f"Ant.: {px}{fmt(d.get('prev'),dec)}" if v else "",invert=inv,d=d)
    sec_title("Histórico — 2 anos")
    g1,g2=st.columns(2); g3,g4=st.columns(2)
    for col,(nome,sym,cor,unit) in zip([g1,g2,g3,g4],[
        ("IBOVESPA","^BVSP","#1a2035","pts"),("S&P 500","^GSPC","#0891b2","pts"),
        ("Petróleo Brent","BZ=F","#d97706","US$"),("Ouro","GC=F","#b45309","US$")]):
        with col:
            dfh=get_hist(sym,2)
            if not dfh.empty: st.plotly_chart(line_fig(dfh,f"{nome} — 2 anos",cor,suffix=f" {unit}"),use_container_width=True,config=CHART_CFG)
    time.sleep(60); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pagina == "Gráficos":
    page_header("Gráficos")
    t1,t2=st.tabs(["BCB — Indicadores Brasil","Yahoo Finance — Ativos Globais"])
    with t1:
        col1,_=st.columns([2,3])
        with col1: ind=st.selectbox("Indicador",list(SGS.keys()),key="gind")
        cod,unit,freq,tipo=SGS[ind]
        with st.spinner(f"Carregando {ind}..."): df_f=get_bcb_full(cod)
        if df_f.empty:
            st.warning("⚠️ API BCB temporariamente indisponível.")
        else:
            dmin=df_f["data"].min().date(); dmax=df_f["data"].max().date()
            ddef=max(dmin,(df_f["data"].max()-pd.DateOffset(months=12)).date())
            st.markdown(f"<div style='font-size:11px;color:#6b7280;margin:6px 0 14px'>Disponível: <strong>{dmin.strftime('%d/%m/%Y')}</strong> → <strong>{dmax.strftime('%d/%m/%Y')}</strong> · {len(df_f)} obs.</div>",unsafe_allow_html=True)
            c2,c3,c4=st.columns([2,2,1])
            with c2: d_ini=st.date_input("De",value=ddef,min_value=dmin,max_value=dmax,key="gini")
            with c3: d_fim=st.date_input("Até",value=dmax,min_value=dmin,max_value=dmax,key="gfim")
            with c4:
                st.markdown("<div style='height:26px'></div>",unsafe_allow_html=True)
                if st.button("Série completa",key="greset"):
                    st.session_state["gini"]=dmin; st.session_state["gfim"]=dmax; st.rerun()
            if d_ini<d_fim:
                mask=(df_f["data"].dt.date>=d_ini)&(df_f["data"].dt.date<=d_fim)
                dfg=df_f[mask].copy()
                if not dfg.empty:
                    st.success(f"✅ {len(dfg)} obs. · {ind} ({unit}) · {freq}")
                    fig=bar_fig(dfg,f"{ind} ({unit})",suffix=f" {unit}",height=420,inter=True) if tipo=="bar" else line_fig(dfg,f"{ind} ({unit})","#1a2035",suffix=f" {unit}",height=420,inter=True)
                    st.plotly_chart(fig,use_container_width=True,config={**CHART_CFG,"scrollZoom":True})
                    dlo=dfg.copy(); dlo["data"]=dlo["data"].dt.strftime("%d/%m/%Y")
                    st.download_button(f"💾 Baixar CSV ({len(dlo)} linhas)",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=f"{ind.replace(' ','_')}_{d_ini}_{d_fim}.csv",mime="text/csv")
    with t2:
        co1,co2=st.columns([2,1])
        with co1: ativo=st.selectbox("Ativo",list(GLOBAL.keys()),key="gativo")
        with co2: anos=st.select_slider("Período (anos)",[1,2,3,5,10],value=5,key="ganos")
        sym,unit,_=GLOBAL[ativo]
        with st.spinner(f"Carregando {ativo}..."): dfg=get_hist(sym,anos)
        if not dfg.empty:
            st.success(f"✅ {len(dfg)} obs. · {ativo}")
            st.plotly_chart(line_fig(dfg,f"{ativo} — {anos} ano(s)","#1a2035",suffix=f" {unit}",height=420,inter=True),use_container_width=True,config={**CHART_CFG,"scrollZoom":True})
            dlo=dfg.copy(); dlo["data"]=dlo["data"].dt.strftime("%d/%m/%Y")
            st.download_button(f"💾 Baixar CSV ({len(dlo)} linhas)",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=f"{ativo.replace(' ','_')}_{anos}a.csv",mime="text/csv")
        else: st.warning("Sem dados disponíveis.")

# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ══════════════════════════════════════════════════════════════════════════════
else:
    page_header("Exportar Dados")
    fonte=st.radio("Fonte:",["BCB/SGS — Brasil","Yahoo Finance — Globais"],horizontal=True)
    st.markdown("<div style='height:10px'></div>",unsafe_allow_html=True)
    if fonte=="BCB/SGS — Brasil":
        c1,c2,c3=st.columns([2,1.5,1.5])
        with c1: ind=st.selectbox("Indicador",list(SGS.keys()),index=1,key="eind")
        with c2: d_ini=st.date_input("De",value=datetime.today()-timedelta(days=365),key="eini")
        with c3: d_fim=st.date_input("Até",value=datetime.today(),key="efim")
        modo=st.radio("Período:",["Usar datas acima","Série completa desde o início"],horizontal=True,key="emodo")
        if st.button("Gerar CSV",type="primary",key="ebtn"):
            cod,unit,freq,_=SGS[ind]
            with st.spinner(f"Buscando {ind}..."):
                dfe=get_bcb_full(cod) if "completa" in modo else get_bcb_range(cod,d_ini.strftime("%d/%m/%Y"),d_fim.strftime("%d/%m/%Y"))
            if dfe.empty: st.warning("Nenhum dado encontrado.")
            else:
                dlo=dfe.copy(); dlo["data"]=dlo["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ {len(dlo)} registros — {ind} ({unit})")
                st.dataframe(dlo.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),use_container_width=True,height=min(380,46+len(dlo)*35))
                suf="completo" if "completa" in modo else f"{d_ini}_{d_fim}"
                nome=f"{ind.replace(' ','_')}_{suf}.csv"
                st.download_button(f"💾 Baixar {nome}",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=nome,mime="text/csv")
    else:
        co1,co2=st.columns([2,1])
        with co1: ativo=st.selectbox("Ativo",list(GLOBAL.keys()),key="eativo")
        with co2: anos=st.select_slider("Período (anos)",[1,2,3,5,10],value=5,key="eanos")
        if st.button("Gerar CSV",type="primary",key="ebtn2"):
            sym,unit,_=GLOBAL[ativo]
            with st.spinner(f"Buscando {ativo}..."): dfe=get_hist(sym,anos)
            if dfe.empty: st.warning("Sem dados disponíveis.")
            else:
                dlo=dfe.copy(); dlo["data"]=dlo["data"].dt.strftime("%d/%m/%Y")
                st.success(f"✅ {len(dlo)} registros — {ativo}")
                st.dataframe(dlo.rename(columns={"data":"Data","valor":f"Valor ({unit})"}),use_container_width=True,height=min(380,46+len(dlo)*35))
                nome=f"{ativo.replace(' ','_')}_{anos}anos.csv"
                st.download_button(f"💾 Baixar {nome}",data=dlo.to_csv(index=False).encode("utf-8-sig"),file_name=nome,mime="text/csv")
    st.markdown("<div style='height:24px'></div>",unsafe_allow_html=True)
    with st.expander("Ver todos os indicadores e ativos disponíveis"):
        st.markdown("**BCB/SGS — Indicadores Brasil**")
        st.dataframe(pd.DataFrame([{"Indicador":k,"Cód. SGS":v[0],"Unidade":v[1],"Freq.":v[2]} for k,v in SGS.items()]),hide_index=True)
        st.markdown("<br>**Yahoo Finance — Ativos Globais**",unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"Ativo":k,"Símbolo":v[0],"Unidade":v[1]} for k,v in GLOBAL.items()]),hide_index=True)
