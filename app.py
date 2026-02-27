import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# ─── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Macro Brasil",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid #1e2236;
    min-width: 200px !important;
    max-width: 200px !important;
}

.main .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
footer { visibility: hidden; }

.sec-title {
    font-size: 11px; font-weight: 700; color: #4b5563;
    text-transform: uppercase; letter-spacing: 2px;
    border-bottom: 1px solid #1e2236;
    padding-bottom: 8px; margin-bottom: 16px; margin-top: 8px;
}
.badge-live {
    display:inline-block; background:#052e16; border:1px solid #166534;
    color:#4ade80; font-size:10px; padding:2px 8px; border-radius:20px; margin-left:8px;
}
.badge-daily {
    display:inline-block; background:#1e1b4b; border:1px solid #3730a3;
    color:#818cf8; font-size:10px; padding:2px 8px; border-radius:20px; margin-left:8px;
}
.stDownloadButton > button {
    background: #1d4ed8 !important; color: white !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE  = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=5d"

SGS_CODES = {
    "Selic":        432,
    "IPCA":         433,
    "IBC-Br":       24363,
    "Dolar PTAX":   1,
    "PIB":          4380,
    "Desemprego":   24369,
    "IGP-M":        189,
    "Exportacoes":  2257,
}

PLOT_CFG = dict(
    paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
    font_color="#94a3b8", font_family="Inter",
    margin=dict(l=0, r=4, t=36, b=0),
    xaxis=dict(gridcolor="#1a1f35", showline=False,
               tickfont=dict(size=10), zeroline=False),
    yaxis=dict(gridcolor="#1a1f35", showline=False,
               tickfont=dict(size=10), zeroline=False),
    title_font=dict(color="#cbd5e1", size=13),
    hoverlabel=dict(bgcolor="#1e2236", font_size=12),
)

# ─── FUNÇÕES UTILITÁRIAS ─────────────────────────────────────────────────────
def hex_rgba(h, a=0.12):
    h = h.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{a})"

def fmt(v, dec=2):
    if v is None:
        return "—"
    s = f"{v:,.{dec}f}"
    # Formato brasileiro: . para milhar, , para decimal
    parts = s.split(".")
    integer_part = parts[0].replace(",", ".")
    decimal_part  = parts[1] if len(parts) > 1 else ""
    return f"{integer_part},{decimal_part}" if decimal_part else integer_part

# ─── FUNÇÕES DE DADOS ────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def get_yahoo(symbol: str):
    """Yahoo Finance — retorna preço atual ou último fechamento se mercado fechado."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(YAHOO_URL.format(symbol), headers=headers, timeout=8)
        data  = r.json()
        meta  = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        change_p = ((price - prev) / prev * 100) if (prev and price and prev != 0) else None
        change_v = (price - prev) if (prev and price) else None
        market   = meta.get("marketState", "CLOSED")
        return {
            "price": price, "prev": prev,
            "change_p": change_p, "change_v": change_v,
            "market": market,
        }
    except:
        return {}

@st.cache_data(ttl=3600)
def get_bcb(codigo: int, ultimos: int):
    try:
        url = BCB_BASE.format(codigo) + f"/ultimos/{ultimos}?formato=json"
        r   = requests.get(url, timeout=10)
        df  = pd.DataFrame(r.json())
        if df.empty:
            return df
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
        if df.empty:
            return df
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(subset=["valor"]).reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["data","valor"])

# ─── KPI CARD (via components.html — funciona dentro de st.columns) ───────────
import streamlit.components.v1 as components

def kpi(label, value, change_p=None, sub="", invert=False, closed=False):
    if change_p is not None:
        up  = (change_p >= 0) if not invert else (change_p < 0)
        cls = "pos" if up else "neg"
        arr = "▲" if change_p >= 0 else "▼"
        dlt = f'<div class="d-{cls}">{arr} {abs(change_p):.2f}%</div>'
    else:
        dlt = '<div class="d-neu"> </div>'

    closed_html = (
        '<div class="closed">Último fechamento disponível</div>' if closed else ""
    )

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:'Inter',sans-serif}}
.card{{
  background:linear-gradient(135deg,#141728,#1c2140);
  border:1px solid #252d4a;border-radius:14px;
  padding:16px;text-align:center;height:118px;
  display:flex;flex-direction:column;justify-content:center;gap:3px
}}
.lbl{{font-size:10px;font-weight:700;color:#5a6a8a;
       text-transform:uppercase;letter-spacing:1.4px}}
.val{{font-size:21px;font-weight:800;color:#e2e8f0;line-height:1.15}}
.d-pos{{font-size:12px;color:#4ade80}}
.d-neg{{font-size:12px;color:#f87171}}
.d-neu{{font-size:12px;color:#2a3050}}
.sub{{font-size:10px;color:#3d4f6e}}
.closed{{font-size:9px;color:#78350f;background:#1c1208;
          border:1px solid #451a03;display:inline-block;
          padding:1px 7px;border-radius:10px;margin-top:2px}}
</style></head><body>
<div class="card">
  <div class="lbl">{label}</div>
  <div class="val">{value}</div>
  {dlt}
  <div class="sub">{sub}</div>
  {closed_html}
</div>
</body></html>"""
    components.html(html, height=126)

# ─── CHART HELPERS ───────────────────────────────────────────────────────────
CHART_CFG = {"displayModeBar": False}

def line_fig(df, title, color="#6366f1", fill=True, suffix=""):
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
    fig.update_layout(**PLOT_CFG, title=title, height=255)
    return fig

def bar_fig(df, title, suffix=""):
    colors = ["#4ade80" if v >= 0 else "#f87171" for v in df["valor"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=colors, marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**PLOT_CFG, title=title, height=255)
    return fig

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🇧🇷 Macro Brasil")
    st.markdown("---")
    pagina = st.radio(
        "nav",
        options=["📊  Dashboard", "📥  Exportar CSV"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<div style='font-size:10px;color:#2d3748;line-height:1.8'>"
        "Fontes de dados:<br>• BCB/SGS<br>• Yahoo Finance<br><br>"
        "Mercado: ↻ 60s<br>BCB: ↻ 1h"
        "</div>",
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
if pagina == "📊  Dashboard":

    col_t, col_h = st.columns([4, 1])
    with col_t:
        st.markdown("## 🇧🇷 Dashboard Macro Brasil")
    with col_h:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.markdown(
            f"<div style='text-align:right;color:#2d3748;font-size:11px;padding-top:16px'>"
            f"Atualizado em<br><b style='color:#4b5a7a'>{now}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='border-color:#1a1f35;margin:4px 0 12px 0'>", unsafe_allow_html=True)

    # Carregar dados
    with st.spinner("Carregando indicadores..."):
        ibov_d  = get_yahoo("^BVSP")
        usd_d   = get_yahoo("USDBRL=X")
        eur_d   = get_yahoo("EURBRL=X")
        df_sel  = get_bcb(432,   14)
        df_ipca = get_bcb(433,   14)
        df_ibc  = get_bcb(24363, 14)
        df_cam  = get_bcb(1,     50)   # busca 50 para garantir 30 dias úteis
        df_pib  = get_bcb(4380,  10)
        df_des  = get_bcb(24369, 10)

    # ── KPIs Mercado ─────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec-title">Indicadores de Mercado'
        '<span class="badge-live">↻ 60s</span></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        v = ibov_d.get("price")
        is_closed = ibov_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Ibovespa",
            fmt(v, 0) + " pts" if v else "—",
            ibov_d.get("change_p"),
            f"Var. dia: {fmt(ibov_d.get('change_v'), 0)} pts" if v else "—",
            closed=is_closed)
    with c2:
        v = usd_d.get("price")
        is_closed = usd_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Dólar (USD/BRL)",
            f"R$ {fmt(v,4)}" if v else "—",
            usd_d.get("change_p"),
            f"Ant.: R$ {fmt(usd_d.get('prev'),4)}" if v else "—",
            invert=True, closed=is_closed)
    with c3:
        v = eur_d.get("price")
        is_closed = eur_d.get("market","CLOSED") not in ("REGULAR","PRE","POST")
        kpi("Euro (EUR/BRL)",
            f"R$ {fmt(v,4)}" if v else "—",
            eur_d.get("change_p"),
            f"Ant.: R$ {fmt(eur_d.get('prev'),4)}" if v else "—",
            invert=True, closed=is_closed)

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
        kpi("IPCA", f"{fmt(v)}% mês" if v else "—", change_p=delta, sub=f"Ref: {ref}")

    with c6:
        v   = float(df_des["valor"].iloc[-1])  if not df_des.empty  else None
        ref = df_des["data"].iloc[-1].strftime("%b/%Y") if not df_des.empty else ""
        kpi("Desemprego (PNAD)", f"{fmt(v)}%" if v else "—", sub=f"Ref: {ref}")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-title">Histórico</div>', unsafe_allow_html=True)

    ca, cb = st.columns(2)
    with ca:
        if not df_sel.empty:
            st.plotly_chart(line_fig(df_sel, "Selic — 12 meses (% a.a.)", "#6366f1", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.info("Selic: sem dados.")
    with cb:
        if not df_ipca.empty:
            st.plotly_chart(bar_fig(df_ipca, "IPCA — 12 meses (% ao mês)", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.info("IPCA: sem dados.")

    cc, cd = st.columns(2)
    with cc:
        df_cam30 = df_cam.tail(30) if not df_cam.empty else df_cam
        if not df_cam30.empty:
            st.plotly_chart(line_fig(df_cam30, "Dólar PTAX — 30 dias úteis (R$)", "#f59e0b", suffix=" R$"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.info("Dólar PTAX: sem dados.")
    with cd:
        if not df_ibc.empty:
            st.plotly_chart(line_fig(df_ibc, "IBC-Br — 12 meses", "#22d3ee", fill=False),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.info("IBC-Br: sem dados.")

    ce, cf = st.columns(2)
    with ce:
        if not df_pib.empty:
            st.plotly_chart(bar_fig(df_pib, "PIB — variação trimestral (%)", suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.info("PIB: sem dados.")
    with cf:
        if not df_des.empty:
            st.plotly_chart(line_fig(df_des, "Desemprego PNAD (%)", "#f87171", fill=True, suffix="%"),
                            use_container_width=True, config=CHART_CFG)
        else:
            st.info("Desemprego: sem dados.")

    st.markdown(
        "<div style='text-align:center;color:#1a1f35;font-size:10px;margin-top:20px'>"
        "Mercado: Yahoo Finance (↻ 60s) • Econômicos: BCB/SGS (cache 1h)"
        "</div>",
        unsafe_allow_html=True,
    )

    # Auto-refresh
    time.sleep(60)
    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — EXPORTAR CSV
# ═════════════════════════════════════════════════════════════════════════════
else:
    st.markdown("## 📥 Exportar Dados")
    st.markdown(
        "<p style='color:#5a6a8a;font-size:13px;margin-bottom:16px'>"
        "Selecione o indicador e o período. Os dados são buscados diretamente do "
        "Banco Central (BCB/SGS) e exportados em CSV com codificação UTF-8.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#1a1f35'>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1.5, 1.5])
    with col1:
        ind_sel = st.selectbox("Indicador", list(SGS_CODES.keys()), index=1)
    with col2:
        d_ini = st.date_input(
            "Data início",
            value=datetime.today() - timedelta(days=365),
            max_value=datetime.today(),
        )
    with col3:
        d_fim = st.date_input(
            "Data fim",
            value=datetime.today(),
            max_value=datetime.today(),
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    gerar = st.button("⬇  Gerar CSV", type="primary")

    if gerar:
        if d_ini >= d_fim:
            st.error("A data de início deve ser anterior à data fim.")
        else:
            with st.spinner(f"Buscando dados de {ind_sel}..."):
                cod     = SGS_CODES[ind_sel]
                ini_str = d_ini.strftime("%d/%m/%Y")
                fim_str = d_fim.strftime("%d/%m/%Y")
                df_exp  = get_bcb_range(cod, ini_str, fim_str)

            if df_exp.empty:
                st.warning("Nenhum dado encontrado. Tente outro período ou indicador.")
            else:
                df_out = df_exp.copy()
                df_out["data"] = df_out["data"].dt.strftime("%d/%m/%Y")

                st.success(f"✅ **{len(df_out)} registros** — {ind_sel} de {ini_str} a {fim_str}")

                st.dataframe(
                    df_out.rename(columns={"data": "Data", "valor": "Valor"}),
                    use_container_width=True,
                    height=min(420, 46 + len(df_out) * 35),
                )

                csv_bytes = df_out.to_csv(index=False).encode("utf-8-sig")
                nome      = f"{ind_sel.replace(' ','_')}_{d_ini}_{d_fim}.csv"
                st.download_button(
                    label=f"💾  Baixar {nome}",
                    data=csv_bytes,
                    file_name=nome,
                    mime="text/csv",
                )

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.markdown("#### Códigos SGS disponíveis neste app")
    st.dataframe(
        pd.DataFrame([{"Indicador": k, "Código SGS": v, "Fonte": "BCB/SGS"}
                      for k, v in SGS_CODES.items()]),
        hide_index=True,
        use_container_width=False,
    )
    st.markdown(
        "<p style='font-size:11px;color:#3d4f6e;margin-top:8px'>"
        "Outros códigos em: "
        "<a href='https://www3.bcb.gov.br/sgspub' target='_blank' "
        "style='color:#4b6fa8'>www3.bcb.gov.br/sgspub</a></p>",
        unsafe_allow_html=True,
    )
