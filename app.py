"""
app.py — Ponto de entrada
"""
import sys, os, importlib.util

def _load(name: str, filepath: str):
    """Carrega um módulo Python a partir do caminho absoluto do arquivo."""
    spec   = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

_ROOT = os.path.dirname(os.path.abspath(__file__))

import streamlit as st

st.set_page_config(
    page_title="Macro Brasil",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Carrega módulos pelo caminho absoluto — funciona em qualquer ambiente
data     = _load("data",     os.path.join(_ROOT, "data.py"))
ui       = _load("ui",       os.path.join(_ROOT, "ui.py"))
sidebar  = _load("sidebar",  os.path.join(_ROOT, "sidebar.py"))
inicio   = _load("inicio",   os.path.join(_ROOT, "views", "inicio.py"))
mercados = _load("mercados", os.path.join(_ROOT, "views", "mercados.py"))
graficos = _load("graficos", os.path.join(_ROOT, "views", "graficos.py"))
exportar = _load("exportar", os.path.join(_ROOT, "views", "exportar.py"))

sidebar.init_state()

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #f0f2f5 !important;
}
.main .block-container {
    padding-top: 0 !important; padding-bottom: 2rem; max-width: 1400px;
}
footer, #MainMenu, header { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }

[data-testid="stMetric"] {
    background: #ffffff !important; border: 1px solid #e2e5e9 !important;
    border-radius: 12px !important; padding: 16px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important; text-align: center !important;
}
[data-testid="stMetricLabel"] > div { justify-content: center !important; }
[data-testid="stMetricLabel"] p {
    font-size: 10px !important; font-weight: 700 !important; color: #6b7280 !important;
    text-transform: uppercase !important; letter-spacing: 1.5px !important;
}
[data-testid="stMetricValue"] > div { justify-content: center !important; }
[data-testid="stMetricValue"] p {
    font-size: 22px !important; font-weight: 700 !important; color: #111827 !important;
}
[data-testid="stMetricDelta"] > div { justify-content: center !important; }
[data-testid="stMetricDelta"] p {
    font-size: 12px !important; font-weight: 600 !important; color: #6b7280 !important;
}
[data-testid="stCaptionContainer"] p {
    font-size: 10px !important; color: #9ca3af !important;
    text-align: center !important; margin: 0 !important;
}
.page-top {
    background: #ffffff; border-bottom: 1px solid #e8eaed;
    padding: 15px 28px; margin: 0 -3rem 22px -3rem;
    display: flex; align-items: center; justify-content: space-between;
}
.page-top h1 { font-size: 16px; font-weight: 600; color: #111827; margin: 0; }
.page-top .ts { font-size: 11px; color: #6b7280; text-align: right; line-height: 1.5; }
.sec-title {
    font-size: 10px; font-weight: 700; color: #6b7280;
    text-transform: uppercase; letter-spacing: 2px;
    margin: 20px 0 12px 0; padding-bottom: 8px;
    border-bottom: 1px solid #e2e5e9;
    display: flex; align-items: center; gap: 8px;
}
.badge-live {
    display: inline-block; background: #f0fdf4; border: 1px solid #bbf7d0;
    color: #16a34a; font-size: 9px; font-weight: 600; padding: 2px 8px; border-radius: 20px;
}
.badge-daily {
    display: inline-block; background: #f5f3ff; border: 1px solid #ddd6fe;
    color: #7c3aed; font-size: 9px; font-weight: 600; padding: 2px 8px; border-radius: 20px;
}
.main .stButton > button {
    background: #1a2035 !important; color: #ffffff !important;
    border: none !important; border-radius: 7px !important;
    font-weight: 600 !important; font-size: 13px !important; padding: 8px 18px !important;
}
.main .stButton > button:hover { background: #2d3a56 !important; }
.stDownloadButton > button {
    background: #ffffff !important; color: #374151 !important;
    border: 1px solid #e2e8f0 !important; border-radius: 7px !important;
}
[data-testid="stSelectbox"] > div > div {
    background: #ffffff !important; border: 1px solid #e2e8f0 !important;
    border-radius: 7px !important; color: #111827 !important;
}
[data-testid="stTabs"] [data-testid="stTabsTabList"] {
    background: transparent !important; border-bottom: 1px solid #e8eaed !important;
}
[data-testid="stTabs"] button[role="tab"] {
    font-size: 13px !important; color: #6b7280 !important;
    padding: 8px 20px !important; border: none !important;
    border-bottom: 2px solid transparent !important; background: transparent !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #1a2035 !important; border-bottom: 2px solid #1a2035 !important;
    font-weight: 600 !important;
}
div[data-testid="stExpander"] {
    background: #ffffff !important; border: 1px solid #e8eaed !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── SIDEBAR + ROTEAMENTO ─────────────────────────────────────────────────────
sidebar.render()

pagina = st.session_state.pagina
if   pagina == "Início":           inicio.render()
elif pagina == "Mercados Globais": mercados.render()
elif pagina == "Gráficos":         graficos.render()
else:                              exportar.render()
