"""
app.py — Ponto de entrada da aplicação
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(
    page_title="Macro Brasil",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)

import sidebar
from pages import inicio, mercados, graficos, exportar

sidebar.init_state()

# ─── CSS GLOBAL ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* ── Layout ── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: #f0f2f5 !important; }

.main .block-container {
    padding-top: 0 !important;
    padding-bottom: 2rem;
    max-width: 1400px;
}

footer, #MainMenu, header       { visibility: hidden !important; }
[data-testid="stToolbar"]       { display: none !important; }
[data-testid="stMain"],
[data-testid="stVerticalBlock"] { animation: none !important; transition: none !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background:   #ffffff !important;
    border-right: 1px solid #e8eaed !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}

/* Botões da sidebar — base */
section[data-testid="stSidebar"] .stButton > button {
    background:    transparent !important;
    border:        none !important;
    border-radius: 7px !important;
    color:         #6b7280 !important;
    font-size:     13px !important;
    font-weight:   500 !important;
    width:         100% !important;
    text-align:    left !important;
    padding:       9px 14px !important;
    height:        auto !important;
    min-height:    38px !important;
    box-shadow:    none !important;
    display:       flex !important;
    align-items:   center !important;
    gap:           10px !important;
    transition:    background 0.12s, color 0.12s !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #f5f6f8 !important;
    color:      #111827 !important;
}
section[data-testid="stSidebar"] .stButton > button:focus,
section[data-testid="stSidebar"] .stButton > button:focus-visible {
    box-shadow: none !important;
    outline:    none !important;
}

/* Botão ativo */
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
    background:    #f0f2ff !important;
    color:         #1a2035 !important;
    font-weight:   600 !important;
    border-left:   3px solid #1a2035 !important;
    border-radius: 0 7px 7px 0 !important;
    padding-left:  11px !important;
}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
    background: #e8ebff !important;
}

/* Toggle collapse/expand */
.sb-toggle-btn .stButton > button {
    width:           32px !important;
    height:          28px !important;
    min-height:      28px !important;
    padding:         0 !important;
    border:          1px solid #e2e8f0 !important;
    border-radius:   6px !important;
    font-size:       16px !important;
    justify-content: center !important;
    text-align:      center !important;
}

/* ── st.metric customizado para KPI cards ── */
[data-testid="stMetric"] {
    background:    #ffffff !important;
    border:        1px solid #e2e5e9 !important;
    border-radius: 12px !important;
    padding:       16px !important;
    box-shadow:    0 1px 3px rgba(0,0,0,0.05) !important;
    text-align:    center !important;
}
[data-testid="stMetricLabel"] {
    font-size:      10px !important;
    font-weight:    700 !important;
    color:          #6b7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.5px !important;
    justify-content: center !important;
}
[data-testid="stMetricLabel"] > div {
    justify-content: center !important;
}
[data-testid="stMetricValue"] {
    font-size:   22px !important;
    font-weight: 700 !important;
    color:       #111827 !important;
    justify-content: center !important;
}
[data-testid="stMetricValue"] > div {
    justify-content: center !important;
}
[data-testid="stMetricDelta"] {
    justify-content: center !important;
}
[data-testid="stMetricDelta"] > div {
    justify-content: center !important;
    font-size:   12px !important;
    font-weight: 600 !important;
    color:       #6b7280 !important;
}

/* ── Cabeçalho de página ── */
.page-top {
    background:      #ffffff;
    border-bottom:   1px solid #e8eaed;
    padding:         15px 28px;
    margin:          0 -3rem 22px -3rem;
    display:         flex;
    align-items:     center;
    justify-content: space-between;
}
.page-top h1 { font-size: 16px; font-weight: 600; color: #111827; margin: 0; }
.page-top .ts { font-size: 11px; color: #6b7280; text-align: right; line-height: 1.5; }

/* ── Títulos de seção ── */
.sec-title {
    font-size:      10px;
    font-weight:    700;
    color:          #6b7280;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin:         20px 0 12px 0;
    padding-bottom: 8px;
    border-bottom:  1px solid #e2e5e9;
    display:        flex;
    align-items:    center;
    gap:            8px;
}

/* ── Badges ── */
.badge-live {
    display:        inline-block;
    background:     #f0fdf4;
    border:         1px solid #bbf7d0;
    color:          #16a34a;
    font-size:      9px;
    font-weight:    600;
    padding:        2px 8px;
    border-radius:  20px;
    text-transform: none;
    letter-spacing: 0;
}
.badge-daily {
    display:        inline-block;
    background:     #f5f3ff;
    border:         1px solid #ddd6fe;
    color:          #7c3aed;
    font-size:      9px;
    font-weight:    600;
    padding:        2px 8px;
    border-radius:  20px;
    text-transform: none;
    letter-spacing: 0;
}

/* ── Botões do conteúdo principal ── */
.main .stButton > button {
    background:      #1a2035 !important;
    color:           #ffffff !important;
    border:          none !important;
    border-radius:   7px !important;
    font-weight:     600 !important;
    font-size:       13px !important;
    padding:         8px 18px !important;
    height:          auto !important;
    min-height:      auto !important;
    width:           auto !important;
    display:         inline-flex !important;
    justify-content: center !important;
}
.main .stButton > button:hover { background: #2d3a56 !important; }
.stDownloadButton > button {
    background:    #ffffff !important;
    color:         #374151 !important;
    border:        1px solid #e2e8f0 !important;
    border-radius: 7px !important;
    font-weight:   500 !important;
    font-size:     12px !important;
}

/* ── Selectboxes ── */
[data-testid="stSelectbox"] > div > div {
    background:    #ffffff !important;
    border:        1px solid #e2e8f0 !important;
    border-radius: 7px !important;
    color:         #111827 !important;
}
.main [data-testid="stSelectbox"] label,
.main [data-testid="stDateInput"] label,
.main [data-testid="stSlider"] label,
.main [data-testid="stRadio"] > label {
    font-size:   12px !important;
    font-weight: 500 !important;
    color:       #4b5563 !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-testid="stTabsTabList"] {
    background:    transparent !important;
    border-bottom: 1px solid #e8eaed !important;
    gap:           0 !important;
}
[data-testid="stTabs"] button[role="tab"] {
    font-size:     13px !important;
    font-weight:   500 !important;
    color:         #6b7280 !important;
    padding:       8px 20px !important;
    border-radius: 0 !important;
    border:        none !important;
    border-bottom: 2px solid transparent !important;
    background:    transparent !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color:         #1a2035 !important;
    border-bottom: 2px solid #1a2035 !important;
    font-weight:   600 !important;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
    background:    #ffffff !important;
    border:        1px solid #e8eaed !important;
    border-radius: 10px !important;
}

/* ── Alertas ── */
[data-testid="stAlert"] { border-radius: 8px !important; font-size: 13px !important; }

/* ── st.caption ── */
[data-testid="stCaptionContainer"] p {
    font-size:   10px !important;
    color:       #9ca3af !important;
    text-align:  center !important;
    margin:      0 !important;
    padding:     0 !important;
}
</style>
""", unsafe_allow_html=True)

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
sidebar.render()

# ─── ROTEAMENTO ──────────────────────────────────────────────────────────────
pagina = st.session_state.pagina

if pagina == "Início":
    inicio.render()
elif pagina == "Mercados Globais":
    mercados.render()
elif pagina == "Gráficos":
    graficos.render()
else:
    exportar.render()
