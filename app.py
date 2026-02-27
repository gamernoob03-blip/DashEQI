import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time

# ─── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Macro Brasil",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS CUSTOMIZADO ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main { background-color: #0f1117; }

    .kpi-card {
        background: linear-gradient(135deg, #1a1d2e, #252840);
        border: 1px solid #2d3057;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        min-height: 110px;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 600;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        color: #e2e8f0;
        line-height: 1.1;
    }
    .kpi-delta-pos { font-size: 13px; color: #4ade80; margin-top: 6px; }
    .kpi-delta-neg { font-size: 13px; color: #f87171; margin-top: 6px; }
    .kpi-delta-neu { font-size: 13px; color: #94a3b8; margin-top: 6px; }
    .kpi-ref { font-size: 11px; color: #64748b; margin-top: 4px; }

    .section-title {
        font-size: 13px;
        font-weight: 600;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        padding: 16px 0 8px 0;
        border-bottom: 1px solid #2d3057;
        margin-bottom: 16px;
    }

    .update-badge {
        display: inline-block;
        background: #1e2d1e;
        border: 1px solid #2d5a2d;
        color: #4ade80;
        font-size: 11px;
        padding: 3px 10px;
        border-radius: 20px;
        margin-left: 8px;
    }
    .update-badge-slow {
        background: #1e1e2d;
        border: 1px solid #2d2d5a;
        color: #818cf8;
    }

    div[data-testid="stMetric"] { display: none; }

    footer { visibility: hidden; }

    .stDownloadButton button {
        background: #1d4ed8 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .stDownloadButton button:hover {
        background: #2563eb !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"
BRAPI_URL = "https://brapi.dev/api/quote/^BVSP,USDBRL=X,EURBRL=X?token=demo"

SGS_CODES = {
    "Selic":      432,
    "IPCA":       433,
    "IBC-Br":     24363,
    "Dólar PTAX": 1,
    "PIB":        4380,
    "Desemprego": 24369,
    "IGP-M":      189,
}

PLOT_THEME = dict(
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font_color="#94a3b8",
    font_family="Inter",
    title_font_color="#e2e8f0",
    title_font_size=14,
    margin=dict(l=0, r=0, t=40, b=0),
    xaxis=dict(gridcolor="#1e2236", showline=False, tickfont=dict(size=11)),
    yaxis=dict(gridcolor="#1e2236", showline=False, tickfont=dict(size=11)),
)

# ─── FUNÇÕES DE DADOS ────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def get_brapi():
    try:
        r = requests.get(BRAPI_URL, timeout=8)
        return r.json().get("results", [])
    except:
        return []

@st.cache_data(ttl=3600)
def get_bcb_serie(codigo: int, ultimos: int = 13):
    try:
        url = BCB_BASE.format(codigo) + f"/ultimos/{ultimos}?formato=json"
        r = requests.get(url, timeout=10)
        df = pd.DataFrame(r.json())
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=["data", "valor"])

@st.cache_data(ttl=3600)
def get_bcb_intervalo(codigo: int, data_ini: str, data_fim: str):
    """Busca série BCB em intervalo específico para exportação."""
    try:
        url = (BCB_BASE.format(codigo)
               + f"?formato=json&dataInicial={data_ini}&dataFinal={data_fim}")
        r = requests.get(url, timeout=15)
        df = pd.DataFrame(r.json())
        if df.empty:
            return df
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=["data", "valor"])

def fmt_brl(v, decimals=2):
    return f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def delta_html(val, invert=False):
    if val is None:
        return '<div class="kpi-delta-neu">—</div>'
    up = val >= 0
    if invert:
        up = not up
    cls = "kpi-delta-pos" if up else "kpi-delta-neg"
    arrow = "▲" if val >= 0 else "▼"
    return f'<div class="{cls}">{arrow} {abs(val):.2f}%</div>'

def kpi_card(label, value, delta_str="", ref=""):
    """Renderiza um KPI card usando components.html para garantir renderização dentro de colunas."""
    import streamlit.components.v1 as components
    html = f"""
    <style>
    .kpi-card {{
        background: linear-gradient(135deg, #1a1d2e, #252840);
        border: 1px solid #2d3057;
        border-radius: 12px;
        padding: 18px 20px;
        text-align: center;
        font-family: 'Inter', sans-serif;
    }}
    .kpi-label {{
        font-size: 10px; font-weight: 600; color: #8892b0;
        text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 8px;
    }}
    .kpi-value {{
        font-size: 24px; font-weight: 700; color: #e2e8f0; line-height: 1.1;
    }}
    .kpi-delta-pos {{ font-size: 12px; color: #4ade80; margin-top: 5px; }}
    .kpi-delta-neg {{ font-size: 12px; color: #f87171; margin-top: 5px; }}
    .kpi-delta-neu {{ font-size: 12px; color: #94a3b8; margin-top: 5px; }}
    .kpi-ref {{ font-size: 10px; color: #64748b; margin-top: 4px; }}
    body {{ background: transparent; margin: 0; padding: 0; }}
    </style>
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {delta_str}
        <div class="kpi-ref">{ref}</div>
    </div>
    """
    components.html(html, height=130)

# ─── GRÁFICO HELPERS ─────────────────────────────────────────────────────────
def hex_to_rgba(hex_color, alpha=0.08):
    """Converte cor hex (#rrggbb) para rgba(r,g,b,a)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def line_chart(df, label, color="#6366f1", fill=True):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines", name=label,
        line=dict(color=color, width=2.5),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_to_rgba(color, 0.12),
    ))
    fig.update_layout(**PLOT_THEME, showlegend=False, height=280)
    return fig

def bar_chart(df, label, pos_color="#4ade80", neg_color="#f87171"):
    colors = [pos_color if v >= 0 else neg_color for v in df["valor"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        name=label, marker_color=colors,
        marker_line_width=0,
    ))
    fig.update_layout(**PLOT_THEME, showlegend=False, height=280)
    return fig

# ─── HEADER ──────────────────────────────────────────────────────────────────
col_title, col_time = st.columns([3, 1])
with col_title:
    st.markdown("## 🇧🇷 Dashboard Macro Brasil")
with col_time:
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(f"<div style='text-align:right;color:#64748b;font-size:12px;padding-top:14px'>Atualizado em<br><b style='color:#94a3b8'>{now}</b></div>", unsafe_allow_html=True)

st.markdown("<hr style='border-color:#2d3057;margin:0 0 8px 0'>", unsafe_allow_html=True)

# ─── CARREGAR DADOS ──────────────────────────────────────────────────────────
with st.spinner("Carregando indicadores..."):
    brapi   = get_brapi()
    df_sel  = get_bcb_serie(432, 13)   # Selic
    df_ipca = get_bcb_serie(433, 13)   # IPCA
    df_ibc  = get_bcb_serie(24363, 13) # IBC-Br
    df_cam  = get_bcb_serie(1, 30)     # Dólar PTAX
    df_pib  = get_bcb_serie(4380, 8)   # PIB
    df_des  = get_bcb_serie(24369, 8)  # Desemprego

# ─── KPI CARDS ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Indicadores de Mercado <span class="update-badge"> ↻ 30s</span></div>', unsafe_allow_html=True)

def brapi_val(results, idx):
    try: return results[idx]
    except: return {}

c1, c2, c3 = st.columns(3)
ibov = brapi_val(brapi, 0)
usd  = brapi_val(brapi, 1)
eur  = brapi_val(brapi, 2)

with c1:
    v = ibov.get("regularMarketPrice")
    d = ibov.get("regularMarketChangePercent")
    kpi_card("Ibovespa",
             fmt_brl(v, 0) + " pts" if v else "—",
             delta_html(d),
             f"Var. dia: {fmt_brl(ibov.get('regularMarketChange',0),2) if v else '—'}")

with c2:
    v = usd.get("regularMarketPrice")
    d = usd.get("regularMarketChangePercent")
    kpi_card("Dólar (USD/BRL)",
             f"R$ {fmt_brl(v, 4)}" if v else "—",
             delta_html(d, invert=True),
             f"Abertura: R$ {fmt_brl(usd.get('regularMarketOpen',0),4) if v else '—'}")

with c3:
    v = eur.get("regularMarketPrice")
    d = eur.get("regularMarketChangePercent")
    kpi_card("Euro (EUR/BRL)",
             f"R$ {fmt_brl(v, 4)}" if v else "—",
             delta_html(d, invert=True),
             f"Abertura: R$ {fmt_brl(eur.get('regularMarketOpen',0),4) if v else '—'}")

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-title">Indicadores Econômicos <span class="update-badge update-badge-slow"> ↻ diário</span></div>', unsafe_allow_html=True)

c4, c5, c6 = st.columns(3)

with c4:
    v = df_sel["valor"].iloc[-1] if not df_sel.empty else None
    ref = df_sel["data"].iloc[-1].strftime("%b/%Y") if not df_sel.empty else ""
    kpi_card("Selic",
             f"{fmt_brl(v)}% a.a." if v else "—",
             "",
             f"Ref: {ref}")

with c5:
    v = df_ipca["valor"].iloc[-1] if not df_ipca.empty else None
    ref = df_ipca["data"].iloc[-1].strftime("%b/%Y") if not df_ipca.empty else ""
    delta = None
    if not df_ipca.empty and len(df_ipca) >= 2:
        delta = float(df_ipca["valor"].iloc[-1]) - float(df_ipca["valor"].iloc[-2])
    kpi_card("IPCA",
             f"{fmt_brl(v)}% mês" if v else "—",
             f'<div class="{"kpi-delta-neg" if (delta or 0)>0 else "kpi-delta-pos"}">{"▲" if (delta or 0)>0 else "▼"} {abs(delta):.2f}pp vs mês ant.</div>' if delta is not None else "",
             f"Ref: {ref}")

with c6:
    v = df_des["valor"].iloc[-1] if not df_des.empty else None
    ref = df_des["data"].iloc[-1].strftime("%b/%Y") if not df_des.empty else ""
    kpi_card("Desemprego (PNAD)",
             f"{fmt_brl(v)}%" if v else "—",
             "",
             f"Ref: {ref}")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ─── GRÁFICOS ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Histórico</div>', unsafe_allow_html=True)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Selic — últimos 12 meses (% a.a.)**")
    if not df_sel.empty:
        st.plotly_chart(line_chart(df_sel, "Selic", "#6366f1"), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sem dados disponíveis.")

with col_b:
    st.markdown("**IPCA — últimos 12 meses (% ao mês)**")
    if not df_ipca.empty:
        st.plotly_chart(bar_chart(df_ipca, "IPCA"), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sem dados disponíveis.")

col_c, col_d = st.columns(2)

with col_c:
    st.markdown("**Dólar PTAX — últimos 30 dias (R$)**")
    if not df_cam.empty:
        st.plotly_chart(line_chart(df_cam, "USD/BRL", "#f59e0b"), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sem dados disponíveis.")

with col_d:
    st.markdown("**IBC-Br — últimos 12 meses**")
    if not df_ibc.empty:
        st.plotly_chart(line_chart(df_ibc, "IBC-Br", "#22d3ee", fill=False), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sem dados disponíveis.")

col_e, col_f = st.columns(2)

with col_e:
    st.markdown("**PIB — variação trimestral (%)**")
    if not df_pib.empty:
        st.plotly_chart(bar_chart(df_pib, "PIB"), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sem dados disponíveis.")

with col_f:
    st.markdown("**Desemprego PNAD (%)**")
    if not df_des.empty:
        st.plotly_chart(line_chart(df_des, "Desemprego", "#f87171", fill=True), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sem dados disponíveis.")

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ─── EXPORTAÇÃO CSV ──────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📥 Exportar Dados</div>', unsafe_allow_html=True)

with st.container():
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])

    with col1:
        indicador_sel = st.selectbox(
            "Indicador",
            options=list(SGS_CODES.keys()),
            index=1,
        )

    with col2:
        data_ini = st.date_input(
            "Data início",
            value=datetime.today() - timedelta(days=365),
            max_value=datetime.today(),
        )

    with col3:
        data_fim = st.date_input(
            "Data fim",
            value=datetime.today(),
            max_value=datetime.today(),
        )

    with col4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        gerar = st.button("⬇ Gerar CSV", use_container_width=True, type="primary")

    if gerar:
        if data_ini >= data_fim:
            st.error("A data de início deve ser anterior à data fim.")
        else:
            with st.spinner(f"Buscando dados de {indicador_sel}..."):
                codigo = SGS_CODES[indicador_sel]
                ini_str = data_ini.strftime("%d/%m/%Y")
                fim_str = data_fim.strftime("%d/%m/%Y")
                df_exp = get_bcb_intervalo(codigo, ini_str, fim_str)

            if df_exp.empty:
                st.warning("Nenhum dado encontrado para o período selecionado.")
            else:
                df_exp["data"] = df_exp["data"].dt.strftime("%d/%m/%Y")
                csv_bytes = df_exp.to_csv(index=False).encode("utf-8-sig")
                nome_arq = f"{indicador_sel.replace(' ','_')}_{data_ini}_{data_fim}.csv"

                st.success(f"✅ {len(df_exp)} registros encontrados.")
                st.download_button(
                    label=f"💾 Baixar {nome_arq}",
                    data=csv_bytes,
                    file_name=nome_arq,
                    mime="text/csv",
                    use_container_width=False,
                )

# ─── AUTO-REFRESH (indicadores de mercado a cada 30s) ────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center;color:#2d3057;font-size:11px'>"
    "Ibovespa, Dólar e Euro atualizam automaticamente a cada 30s • "
    "Indicadores BCB: cache de 1h • Fonte: BCB/SGS + Brapi.dev"
    "</div>",
    unsafe_allow_html=True
)

# Auto-refresh a cada 30 segundos
time.sleep(30)
st.rerun()
