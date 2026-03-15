"""
settings.py — Constantes, TTLs e configuração declarativa do dashboard.
Nenhuma dependência de Streamlit ou lógica de negócio aqui.
"""
import logging
from zoneinfo import ZoneInfo
from typing import NamedTuple

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
CHART_CFG = {
    "displayModeBar":           True,
    "scrollZoom":               True,
    "modeBarButtonsToRemove":   ["select2d", "lasso2d", "autoScale2d", "resetScale2d"],
    "modeBarButtonsToAdd":      ["zoomIn2d", "zoomOut2d"],
    "displaylogo":              False,
    "toImageButtonOptions":     {"format": "png", "scale": 2},
    "responsive":               True,
}
CHART_CFG_INT = CHART_CFG  # alias de compatibilidade

# ── Transformações disponíveis por série (períodos) ───────────────────────────
# Constantes de string para evitar repetição literal em app.py
P_ORIGINAL      = "Original"
P_MENSAL        = "Mensal (original)"
P_NIVEL         = "Nível (original)"
P_TRIM_ORIG     = "Var. trimestral (original)"
P_ACUM_12M      = "Acumulado 12M"
P_ACUM_ANO      = "Acumulado no ano"
P_VAR_MM        = "Var. mensal (m/m)"
P_VAR_TT        = "Var. trimestral (t/t)"
P_VAR_AA        = "Var. anual (a/a)"
P_ACUM_4TRI     = "Acumulado 4 trimestres"

# Períodos que representam a série "original" (sem transformação acumulada)
PERIODOS_ORIGINAIS = {P_ORIGINAL, P_MENSAL, P_NIVEL, P_TRIM_ORIG}

# Mapeamento série → transformações disponíveis (única fonte da verdade)
SGS_PERIODOS = {
    "Selic":             [P_ORIGINAL],
    "IPCA":              [P_MENSAL,    P_ACUM_12M, P_ACUM_ANO],
    "IBC-Br":            [P_NIVEL,     P_VAR_MM,   P_VAR_TT,   P_VAR_AA],
    "Dólar PTAX":        [P_ORIGINAL],
    "PIB":               [P_TRIM_ORIG, P_VAR_AA,   P_ACUM_4TRI],
    "Desemprego":        [P_ORIGINAL],
    "IGP-M":             [P_MENSAL,    P_ACUM_12M],
    "IPCA-15":           [P_MENSAL,    P_ACUM_12M],
    "Exportações":       [P_ORIGINAL,  P_VAR_MM,   P_VAR_AA],
    "Importações":       [P_ORIGINAL,  P_VAR_MM,   P_VAR_AA],
    "Dívida/PIB":        [P_ORIGINAL,  P_VAR_MM],
    "Focus: IPCA 12M":   [P_ORIGINAL],
    "Focus: IPCA ano":   [P_ORIGINAL],
    "Focus: Selic ano":  [P_ORIGINAL],
    "Focus: PIB ano":    [P_ORIGINAL],
    "Focus: Câmbio ano": [P_ORIGINAL],
    "Swap DI×Pré 360d":  [P_ORIGINAL],
}

# ── Séries BCB/SGS ────────────────────────────────────────────────────────────
class SerieSGS(NamedTuple):
    codigo:    int
    unidade:   str
    frequencia: str
    tipo:      str   # "line" | "bar"
    cor:       str   # hex

SGS = {
    # Indicadores gerais
    "Selic":              SerieSGS(432,   "% a.a.",  "Mensal",     "line", "#1a2035"),
    "IPCA":               SerieSGS(433,   "% mês",   "Mensal",     "bar",  "#dc2626"),
    "IBC-Br":             SerieSGS(24363, "índice",  "Mensal",     "line", "#0891b2"),
    "Dólar PTAX":         SerieSGS(1,     "R$",      "Diário",     "line", "#d97706"),
    "PIB":                SerieSGS(4380,  "% trim.", "Trimestral", "bar",  "#16a34a"),
    "Desemprego":         SerieSGS(24369, "%",       "Trimestral", "line", "#dc2626"),
    "IGP-M":              SerieSGS(189,   "% mês",   "Mensal",     "bar",  "#7c3aed"),
    "IPCA-15":            SerieSGS(7478,  "% mês",   "Mensal",     "bar",  "#d97706"),
    "Exportações":        SerieSGS(2257,  "US$ mi",  "Mensal",     "bar",  "#16a34a"),
    "Importações":        SerieSGS(2258,  "US$ mi",  "Mensal",     "bar",  "#dc2626"),
    "Dívida/PIB":         SerieSGS(4513,  "%",       "Mensal",     "line", "#374151"),
    # Expectativas Focus
    "Focus: IPCA 12M":    SerieSGS(13522, "%",       "Diário",     "line", "#0891b2"),
    "Focus: IPCA ano":    SerieSGS(13521, "%",       "Diário",     "line", "#06b6d4"),
    "Focus: Selic ano":   SerieSGS(13426, "% a.a.",  "Diário",     "line", "#1a2035"),
    "Focus: PIB ano":     SerieSGS(13291, "%",       "Diário",     "line", "#16a34a"),
    "Focus: Câmbio ano":  SerieSGS(13290, "R$",      "Diário",     "line", "#d97706"),
    # Câmbio e swaps
    "Swap DI×Pré 360d":   SerieSGS(7814,  "% a.a.",  "Diário",     "line", "#7c3aed"),
}

# ── KPIs e gráficos da página Início ─────────────────────────────────────────
HOME_KPIS = [
    ("Selic",      "Selic",            "{v}% a.a."),
    ("IPCA",       "IPCA",             "{v}% mês"),
    ("Desemprego", "Desemprego (PNAD)", "{v}%"),
]
HOME_CHARTS = [
    ("Selic",      13),
    ("IPCA",       13),
    ("Dólar PTAX",  1),
    ("IBC-Br",     13),
    ("PIB",        24),
    ("Desemprego", 24),
]

# ── Ativos globais ────────────────────────────────────────────────────────────
class AtivoGlobal(NamedTuple):
    simbolo:  str
    unidade:  str
    invertido: bool   # True = queda de preço é positivo (ex: USD/BRL)
    cor:      str

GLOBAL = {
    "IBOVESPA":        AtivoGlobal("^BVSP",  "pts",    False, "#0891b2"),
    "Dólar (USD/BRL)": AtivoGlobal("usdbrl", "R$",     True,  "#7c3aed"),
    "Euro (EUR/BRL)":  AtivoGlobal("eurbrl", "R$",     True,  "#d97706"),
    "S&P 500":         AtivoGlobal("^spx",   "pts",    False, "#16a34a"),
    "Nasdaq 100":      AtivoGlobal("^ndx",   "pts",    False, "#6366f1"),
    "Dow Jones":       AtivoGlobal("^dji",   "pts",    False, "#0891b2"),
    "FTSE 100":        AtivoGlobal("^ukx",   "pts",    False, "#374151"),
    "DAX":             AtivoGlobal("^dax",   "pts",    False, "#374151"),
    "Petróleo Brent":  AtivoGlobal("sc.f",   "US$",    True,  "#d97706"),
    "Petróleo WTI":    AtivoGlobal("cl.f",   "US$",    True,  "#f59e0b"),
    "Ouro":            AtivoGlobal("gc.f",   "US$",    False, "#b45309"),
    "Prata":           AtivoGlobal("si.f",   "US$",    False, "#64748b"),
    "Cobre":           AtivoGlobal("hg.f",   "US$/lb", True,  "#dc2626"),
    "Bitcoin":         AtivoGlobal("btc.v",  "US$",    False, "#f59e0b"),
    "Ethereum":        AtivoGlobal("eth.v",  "US$",    False, "#6366f1"),
}

MERCADOS_HIST = ["IBOVESPA", "S&P 500", "Petróleo Brent", "Ouro", "Dólar (USD/BRL)", "Bitcoin"]
CORES_COMP    = ["#1a2035", "#dc2626", "#0891b2", "#16a34a", "#d97706", "#7c3aed"]

# ── Alturas dos gráficos (px) ─────────────────────────────────────────────────
H_SMALL   = 260   # gráficos pequenos (página Início)
H_MEDIUM  = 320   # gráficos médios (Mercados histórico, acumulado 12M)
H_LARGE   = 440   # gráficos grandes (aba Gráficos)
H_XLARGE  = 480   # gráficos extra grandes (Monitor Inflação — núcleos)
H_MONITOR = 360   # Monitor Inflação — média núcleos
H_ACUM    = 320   # acumulado 12M vs meta (alias de H_MEDIUM)
H_COMP    = 460   # comparação de séries
H_GROUP   = 340   # grupos snapshot
H_GRUPOS  = 420   # grupos evolução

# ── Cores fixas Monitor Inflação ──────────────────────────────────────────────
COR_IPCA_LINHA = "#1a2035"
COR_MEDIA_NUCL = "#7c3aed"

# ── Núcleos de inflação BCB ───────────────────────────────────────────────────
class NucleoSGS(NamedTuple):
    codigo:    int
    descricao: str
    cor:       str

NUCLEO_SGS = {
    "MA-S": NucleoSGS(4466,  "Médias Aparadas c/ Suavização", "#0891b2"),
    "MA":   NucleoSGS(11426, "Médias Aparadas s/ Suavização", "#06b6d4"),
    "DP":   NucleoSGS(4467,  "Dupla Ponderação",              "#16a34a"),
    "EX":   NucleoSGS(11427, "Exclusão",                      "#d97706"),
    "P55":  NucleoSGS(28750, "Percentil 55",                  "#7c3aed"),
}

# ── Metas BCB ─────────────────────────────────────────────────────────────────
BCB_META = {2020: 4.0, 2021: 3.75, 2022: 3.5, 2023: 3.25, 2024: 3.0, 2025: 3.0, 2026: 3.0}
BCB_TOLE = 1.5

# ── Grupos IPCA (IBGE SIDRA) ──────────────────────────────────────────────────
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


# ── Glossário dos indicadores ─────────────────────────────────────────────────
SGS_DESCRICAO = {
    "Selic":             "Taxa básica de juros da economia brasileira, definida pelo Copom (Comitê de Política Monetária do BCB) a cada 45 dias.",
    "IPCA":              "Índice de Preços ao Consumidor Amplo — inflação oficial do Brasil, medida pelo IBGE mensalmente.",
    "IBC-Br":            "Índice de Atividade Econômica do BCB — proxy mensal do PIB, divulgado com ~45 dias de defasagem.",
    "Dólar PTAX":        "Taxa de câmbio oficial USD/BRL apurada pelo BCB pela média das operações no mercado interbancário.",
    "PIB":               "Produto Interno Bruto — soma de todos os bens e serviços produzidos no país. Divulgado trimestralmente pelo IBGE.",
    "Desemprego":        "Taxa de desocupação da PNAD Contínua (IBGE) — percentual da força de trabalho sem emprego e procurando trabalho.",
    "IGP-M":             "Índice Geral de Preços – Mercado (FGV) — usado em reajustes de contratos de aluguel e energia elétrica.",
    "IPCA-15":           "Prévia do IPCA, calculada entre o dia 16 do mês anterior e o 15 do mês corrente. Antecipa a tendência do IPCA.",
    "Exportações":       "Valor total das exportações brasileiras em US$ milhões (FOB), divulgado mensalmente pelo MDIC.",
    "Importações":       "Valor total das importações brasileiras em US$ milhões (FOB), divulgado mensalmente pelo MDIC.",
    "Dívida/PIB":        "Dívida Bruta do Governo Geral como percentual do PIB — indicador de solvência fiscal do Estado brasileiro.",
    "Focus: IPCA 12M":   "Mediana das expectativas do mercado para o IPCA acumulado nos próximos 12 meses (Boletim Focus/BCB).",
    "Focus: IPCA ano":   "Mediana das expectativas do mercado para o IPCA do ano corrente (Boletim Focus/BCB).",
    "Focus: Selic ano":  "Mediana das expectativas do mercado para a taxa Selic ao final do ano corrente (Boletim Focus/BCB).",
    "Focus: PIB ano":    "Mediana das expectativas do mercado para o crescimento do PIB no ano corrente (Boletim Focus/BCB).",
    "Focus: Câmbio ano": "Mediana das expectativas do mercado para o câmbio USD/BRL ao final do ano corrente (Boletim Focus/BCB).",
    "Swap DI×Pré 360d":  "Taxa do swap DI x pré-fixado com vencimento em 360 dias — proxy da expectativa de juros futuros.",
}

GLOBAL_DESCRICAO = {
    "IBOVESPA":        "Principal índice da Bolsa de Valores brasileira (B3), composto pelas ações de maior liquidez.",
    "Dólar (USD/BRL)": "Taxa de câmbio entre o Dólar americano e o Real brasileiro.",
    "Euro (EUR/BRL)":  "Taxa de câmbio entre o Euro e o Real brasileiro.",
    "S&P 500":         "Índice das 500 maiores empresas listadas nas bolsas americanas (NYSE e NASDAQ).",
    "Nasdaq 100":      "Índice das 100 maiores empresas de tecnologia e crescimento listadas na NASDAQ.",
    "Dow Jones":       "Índice das 30 maiores empresas industriais americanas, um dos mais antigos do mundo.",
    "FTSE 100":        "Índice das 100 maiores empresas listadas na Bolsa de Londres (LSE).",
    "DAX":             "Índice das 40 maiores empresas listadas na Bolsa de Frankfurt, principal índice alemão.",
    "Petróleo Brent":  "Preço do petróleo bruto Brent (Mar do Norte) em USD por barril — referência global.",
    "Petróleo WTI":    "Preço do petróleo West Texas Intermediate em USD por barril — referência americana.",
    "Ouro":            "Preço spot do ouro em USD por onça troy — ativo de proteção e reserva de valor.",
    "Prata":           "Preço spot da prata em USD por onça troy — metal precioso com uso industrial.",
    "Cobre":           "Preço do cobre em USD por libra-peso — indicador da atividade industrial global.",
    "Bitcoin":         "Maior criptomoeda por capitalização de mercado, cotada em USD.",
    "Ethereum":        "Segunda maior criptomoeda, base de contratos inteligentes e DeFi, cotada em USD.",
}

# ── Focus API (BCB/Expectativas) ──────────────────────────────────────────────
FOCUS_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
TTL_FOCUS  = 86_400  # 24h — divulgado semanalmente

# Indicadores disponíveis na API Focus
FOCUS_INDICADORES = [
    "IPCA",
    "IGP-M",
    "PIB Total",
    "Taxa de câmbio",
    "Meta para taxa over-selic",
    "IPCA-15",
    "IGP-DI",
    "IPC-Fipe",
    "Balança comercial",
    "Conta corrente",
    "Investimento direto no país",
    "Produção industrial",
    "Selic",
]

# ── Navegação ─────────────────────────────────────────────────────────────────
NAV = ["Início", "Monitor Inflação", "Expectativas", "Mercados Globais", "Gráficos", "Exportar"]
NAV_SLUGS = {
    "Início":           "inicio",
    "Monitor Inflação": "ipca",
    "Mercados Globais": "mercados",
    "Gráficos":         "graficos",
    "Expectativas":     "expectativas",
    "Exportar":         "exportar",
}
