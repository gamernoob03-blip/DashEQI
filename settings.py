"""
config.py — Constantes, TTLs e configuração de logging.
Nenhuma dependência de Streamlit ou lógica de negócio aqui.
"""
import logging
from zoneinfo import ZoneInfo

# ── Timezone ──────────────────────────────────────────────────────────────────
TZ_BRT = ZoneInfo("America/Sao_Paulo")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("eqi_dash")

# ── TTL de cache por tipo de fonte ────────────────────────────────────────────
TTL_MERCADOS = 60        # cotações Yahoo Finance: 1 minuto
TTL_BCB      = 3_600     # séries BCB/SGS: 1 hora
TTL_IBGE     = 86_400    # grupos IPCA IBGE (mensal): 24 horas
TTL_HIST     = 3_600     # histórico Yahoo Finance: 1 hora

# ── URLs das APIs ─────────────────────────────────────────────────────────────
BCB_BASE   = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{c}/dados"
YAHOO_SNAP = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range=5d"
YAHOO_HIST = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1d&range={y}y"
IBGE_SIDRA = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos/{periodos}"
    "/variaveis/{var}?localidades=N1[all]&classificacao={cls}"
)

# ── Headers HTTP comuns ───────────────────────────────────────────────────────
HDRS = {
    "User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36",
    "Accept":     "application/json",
}

# ── Configuração dos gráficos Plotly ─────────────────────────────────────────
# Config único — todos os gráficos usam o mesmo padrão interativo.
# Para gráficos de snapshot (sem eixo de tempo), render_chart em components.py
# passa staticPlot=True automaticamente.
CHART_CFG = {
    "displayModeBar":           True,
    "scrollZoom":               True,
    "modeBarButtonsToRemove":   ["select2d", "lasso2d", "autoScale2d", "resetScale2d"],
    "modeBarButtonsToAdd":      ["zoomIn2d", "zoomOut2d"],
    "displaylogo":              False,
    "toImageButtonOptions":     {"format": "png", "scale": 2},
    "responsive":               True,
}

# Alias para compatibilidade — ambos apontam para o mesmo dict
CHART_CFG_INT = CHART_CFG

# ── Séries BCB/SGS ────────────────────────────────────────────────────────────
# Formato: nome → (código SGS, unidade, frequência, tipo de gráfico, cor hex)
SGS = {
    # Indicadores gerais
    "Selic":              (432,   "% a.a.",  "Mensal",     "line", "#1a2035"),
    "IPCA":               (433,   "% mês",   "Mensal",     "bar",  "#dc2626"),
    "IBC-Br":             (24363, "índice",  "Mensal",     "line", "#0891b2"),
    "Dólar PTAX":         (1,     "R$",      "Diário",     "line", "#d97706"),
    "PIB":                (4380,  "% trim.", "Trimestral", "bar",  "#16a34a"),
    "Desemprego":         (24369, "%",       "Trimestral", "line", "#dc2626"),
    "IGP-M":              (189,   "% mês",   "Mensal",     "bar",  "#7c3aed"),
    "IPCA-15":            (7478,  "% mês",   "Mensal",     "bar",  "#d97706"),
    "Exportações":        (2257,  "US$ mi",  "Mensal",     "bar",  "#16a34a"),
    "Importações":        (2258,  "US$ mi",  "Mensal",     "bar",  "#dc2626"),
    "Dívida/PIB":         (4513,  "%",       "Mensal",     "line", "#374151"),
    # Expectativas Focus (Relatório de Mercado)
    "Focus: IPCA 12M":    (13522, "%",       "Diário",     "line", "#0891b2"),
    "Focus: IPCA ano":    (13521, "%",       "Diário",     "line", "#06b6d4"),
    "Focus: Selic ano":   (13426, "% a.a.",  "Diário",     "line", "#1a2035"),
    "Focus: PIB ano":     (13291, "%",       "Diário",     "line", "#16a34a"),
    "Focus: Câmbio ano":  (13290, "R$",      "Diário",     "line", "#d97706"),
    # Câmbio e swaps
    "Swap DI×Pré 360d":   (7814,  "% a.a.",  "Diário",     "line", "#7c3aed"),
}

# ── KPIs da página Início ─────────────────────────────────────────────────────
# Formato: (nome_no_SGS, label_exibição, formato_valor)
# formato_valor: string Python com {v} para o valor e {u} para a unidade
HOME_KPIS = [
    ("Selic",      "Selic",           "{v}% a.a."),
    ("IPCA",       "IPCA",            "{v}% mês"),
    ("Desemprego", "Desemprego (PNAD)", "{v}%"),
]
# Formato: (nome_no_SGS, meses_exibidos)
# A série é sempre carregada completa do cache — só a janela de exibição varia.
HOME_CHARTS = [
    ("Selic",       13),   # mensal   — últimos 13 meses
    ("IPCA",        13),   # mensal   — últimos 13 meses
    ("Dólar PTAX",   1),   # diário   — último mês (~30 dias úteis)
    ("IBC-Br",      13),   # mensal   — últimos 13 meses
    ("PIB",         24),   # trimestral — últimos 24 meses (8 trimestres)
    ("Desemprego",  24),   # trimestral — últimos 24 meses
]

# ── Ativos globais ────────────────────────────────────────────────────────────
# Formato: nome → (símbolo interno, unidade, sinal_invertido)
GLOBAL = {
    "IBOVESPA":        ("^BVSP",   "pts",    False),
    "Dólar (USD/BRL)": ("usdbrl",  "R$",     True),
    "Euro (EUR/BRL)":  ("eurbrl",  "R$",     True),
    "S&P 500":         ("^spx",    "pts",    False),
    "Nasdaq 100":      ("^ndx",    "pts",    False),
    "Dow Jones":       ("^dji",    "pts",    False),
    "FTSE 100":        ("^ukx",    "pts",    False),
    "DAX":             ("^dax",    "pts",    False),
    "Petróleo Brent":  ("sc.f",    "US$",    True),
    "Petróleo WTI":    ("cl.f",    "US$",    True),
    "Ouro":            ("gc.f",    "US$",    False),
    "Prata":           ("si.f",    "US$",    False),
    "Cobre":           ("hg.f",    "US$/lb", True),
    "Bitcoin":         ("btc.v",   "US$",    False),
    "Ethereum":        ("eth.v",   "US$",    False),
}

# ── Núcleos de inflação BCB ───────────────────────────────────────────────────
# Formato: sigla → (código SGS, descrição, cor hex)
NUCLEO_SGS = {
    "MA-S": (4466,  "Médias Aparadas c/ Suavização", "#0891b2"),
    "MA":   (11426, "Médias Aparadas s/ Suavização", "#06b6d4"),
    "DP":   (4467,  "Dupla Ponderação",              "#16a34a"),
    "EX":   (11427, "Exclusão",                      "#d97706"),
    "P55":  (28750, "Percentil 55",                  "#7c3aed"),
}

# ── Metas BCB ─────────────────────────────────────────────────────────────────
BCB_META = {2020: 4.0, 2021: 3.75, 2022: 3.5, 2023: 3.25, 2024: 3.0, 2025: 3.0, 2026: 3.0}
BCB_TOLE = 1.5  # tolerância ± pp

# ── Grupos IPCA (IBGE SIDRA — classificação 315) ──────────────────────────────
IPCA_GRUPOS_IDS = "7170,7445,7486,7558,7625,7660,7712,7766,7786"

IPCA_GRUPOS_CORES = {
    "Alimentação e bebidas":     "#d97706",
    "Habitação":                 "#0891b2",
    "Artigos de residência":     "#64748b",
    "Vestuário":                 "#ec4899",
    "Transportes":               "#7c3aed",
    "Saúde e cuidados pessoais": "#16a34a",
    "Despesas pessoais":         "#f59e0b",
    "Educação":                  "#dc2626",
    "Comunicação":               "#0ea5e9",
}

# ── Navegação ─────────────────────────────────────────────────────────────────
NAV = ["Início", "Monitor Inflação", "Mercados Globais", "Gráficos", "Exportar"]
NAV_SLUGS = {
    "Início":          "inicio",
    "Monitor Inflação": "ipca",
    "Mercados Globais": "mercados",
    "Gráficos":         "graficos",
    "Exportar":         "exportar",
}
