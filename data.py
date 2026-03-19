"""
data.py — Camada de dados do EQI Dashboard Macro

Fontes:
  - BCB/SGS        : indicadores macro brasileiros
  - BCB/Focus      : expectativas de mercado (Boletim Focus)
  - IBGE/SIDRA     : IPCA por grupos
  - Yahoo Finance  : cotações e histórico de ativos globais

Correção 429 / YFRateLimitError:
  O Yahoo Finance exige um crumb token em todas as requisições programáticas.
  _build_yf_session() autentica uma vez (cookie + crumb) e reutiliza a sessão
  via st.session_state, renovando automaticamente a cada 50 minutos ou em 401/429.
  Remove dependência do yfinance (era a fonte dos rate limits no Streamlit Cloud).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
import requests
import urllib3
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS")

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE      = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
FOCUS_ANUAL   = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativaMercadoAnuais"
FOCUS_12M     = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoInflacao12Meses"
SIDRA_BASE    = "https://servicodados.ibge.gov.br/api/v3/agregados"

# Yahoo Finance
_YF_COOKIE_URL = "https://fc.yahoo.com"
_YF_CRUMB_URL  = "https://query1.finance.yahoo.com/v1/test/getcrumb"
_YF_CHART_URL  = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin":          "https://finance.yahoo.com",
    "Referer":         "https://finance.yahoo.com/",
}

# ─── UTILS ───────────────────────────────────────────────────────────────────
def parse_bcb_valor(valor_str):
    if valor_str is None:
        return None
    s = str(valor_str).strip().replace("\xa0", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

def _build_df(raw: list) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["data", "valor"])
    df = pd.DataFrame(raw)
    if "data" not in df.columns or "valor" not in df.columns:
        return pd.DataFrame(columns=["data", "valor"])
    df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = df["valor"].apply(parse_bcb_valor)
    df = df.dropna(subset=["data", "valor"]).sort_values("data").reset_index(drop=True)
    return df[["data", "valor"]]

# ─── BCB/SGS ─────────────────────────────────────────────────────────────────
def _bcb_fetch(url: str) -> list:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
            if r.status_code != 200:
                time.sleep(1); continue
            if "html" in r.headers.get("Content-Type", "").lower():
                time.sleep(1); continue
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return data
            time.sleep(0.5)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < 2:
                time.sleep(1)
        except Exception:
            break
    return []

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb(codigo: int, ultimos: int) -> pd.DataFrame:
    url = BCB_BASE.format(codigo=codigo) + f"/ultimos/{ultimos}?formato=json"
    raw = _bcb_fetch(url)
    if not raw:
        hoje = datetime.today()
        ini  = (hoje - timedelta(days=ultimos * 45)).strftime("%d/%m/%Y")
        fim  = hoje.strftime("%d/%m/%Y")
        raw  = _bcb_fetch(BCB_BASE.format(codigo=codigo) + f"?formato=json&dataInicial={ini}&dataFinal={fim}")
    return _build_df(raw)

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb_full(codigo: int) -> pd.DataFrame:
    return _build_df(_bcb_fetch(BCB_BASE.format(codigo=codigo) + "?formato=json"))

@st.cache_data(ttl=3600, show_spinner=False)
def get_bcb_range(codigo: int, ini: str, fim: str) -> pd.DataFrame:
    return _build_df(_bcb_fetch(
        BCB_BASE.format(codigo=codigo) + f"?formato=json&dataInicial={ini}&dataFinal={fim}"))

# ─── BCB/FOCUS — Expectativas de Mercado ─────────────────────────────────────
def _focus_fetch(url: str, params: dict) -> list:
    """Busca dados da API Olinda (Focus) com paginação automática."""
    resultados = []
    params = {**params, "$format": "json", "$top": 10000, "$skip": 0}
    for _ in range(10):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                break
            data = r.json().get("value", [])
            if not data:
                break
            resultados.extend(data)
            if len(data) < params["$top"]:
                break
            params["$skip"] += params["$top"]
        except Exception:
            break
    return resultados

@st.cache_data(ttl=3600, show_spinner=False)
def get_focus_anual(indicador: str, anos: int = 5) -> pd.DataFrame:
    """
    Expectativas anuais do Boletim Focus para um indicador.
    Retorna DataFrame com colunas: data, ano_ref, mediana, minimo, maximo, desvio.
    """
    data_ini = (datetime.today() - timedelta(days=anos * 365)).strftime("%Y-%m-%d")
    params = {
        "$filter": (
            f"Indicador eq '{indicador}' and baseCalculo eq '0' "
            f"and Data ge '{data_ini}'"
        ),
        "$select": "Data,DataReferencia,Mediana,Minimo,Maximo,DesvioPadrao",
        "$orderby": "Data asc",
    }
    raw = _focus_fetch(FOCUS_ANUAL, params)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df = df.rename(columns={
        "Data":           "data",
        "DataReferencia": "ano_ref",
        "Mediana":        "mediana",
        "Minimo":         "minimo",
        "Maximo":         "maximo",
        "DesvioPadrao":   "desvio",
    })
    df["data"]    = pd.to_datetime(df["data"], errors="coerce")
    df["ano_ref"] = pd.to_numeric(df["ano_ref"], errors="coerce")
    for col in ["mediana", "minimo", "maximo", "desvio"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["data", "mediana"]).sort_values("data").reset_index(drop=True)

@st.cache_data(ttl=3600, show_spinner=False)
def get_focus_12m(indicador: str, anos: int = 3) -> pd.DataFrame:
    """
    Expectativas para os próximos 12 meses do Boletim Focus.
    Disponível para: IPCA, IPCA-15, IGP-M, IGP-DI, IPC-Fipe.
    Retorna DataFrame com colunas: data, mediana, minimo, maximo, desvio.
    """
    data_ini = (datetime.today() - timedelta(days=anos * 365)).strftime("%Y-%m-%d")
    params = {
        "$filter": (
            f"Indicador eq '{indicador}' and baseCalculo eq '0' "
            f"and Data ge '{data_ini}'"
        ),
        "$select": "Data,Mediana,Minimo,Maximo,DesvioPadrao",
        "$orderby": "Data asc",
    }
    raw = _focus_fetch(FOCUS_12M, params)
    if not raw:
        # Fallback: expectativas anuais como proxy
        return get_focus_anual(indicador, anos=anos)
    df = pd.DataFrame(raw)
    df = df.rename(columns={
        "Data":         "data",
        "Mediana":      "mediana",
        "Minimo":       "minimo",
        "Maximo":       "maximo",
        "DesvioPadrao": "desvio",
    })
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    for col in ["mediana", "minimo", "maximo", "desvio"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["data", "mediana"]).sort_values("data").reset_index(drop=True)

# ─── IBGE/SIDRA — IPCA por Grupos ────────────────────────────────────────────
# Tabela 7060 · Variável 63 = var. mensal · Variável 2265 = acum. 12 meses
# Classificação 315: grupos do IPCA (códigos SIDRA)
_SIDRA_GRUPOS = "7169,7170,7445,7486,7625,7626,7627,7628,7629"

def _sidra_fetch(tabela: int, variavel: int, periodos: int) -> pd.DataFrame:
    """
    Busca IPCA por grupos no IBGE/SIDRA.
    Retorna DataFrame com colunas: data, grupo_id, grupo, valor.
    """
    url = (
        f"{SIDRA_BASE}/{tabela}/periodos/-{periodos}/variaveis/{variavel}"
        f"?localidades=N1[all]&classificacao=315[{_SIDRA_GRUPOS}]"
    )
    raw = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                raw = r.json()
                break
            time.sleep(1)
        except Exception:
            time.sleep(1)

    if not raw:
        return pd.DataFrame()

    rows = []
    for bloco in raw:
        # SIDRA retorna período em D3C (formato YYYYMM) e grupo em D4C/D5C
        periodo_str = str(bloco.get("D3C") or bloco.get("D2C", ""))
        grupo_id    = str(bloco.get("D4C") or bloco.get("D5C", ""))
        grupo_nome  = str(bloco.get("D4N") or bloco.get("D5N", grupo_id))
        valor_str   = str(bloco.get("V", "")).strip()

        if not periodo_str or valor_str in ("...", "-", "", "X"):
            continue
        try:
            dt    = pd.to_datetime(periodo_str, format="%Y%m")
            valor = float(valor_str.replace(",", "."))
        except Exception:
            continue

        rows.append({
            "data":     dt,
            "grupo_id": grupo_id,
            "grupo":    grupo_nome,
            "valor":    valor,
        })

    if not rows:
        return pd.DataFrame()

    return (pd.DataFrame(rows)
            .sort_values(["data", "grupo_id"])
            .reset_index(drop=True))

@st.cache_data(ttl=3600, show_spinner=False)
def get_ipca_grupos(meses: int = 60) -> pd.DataFrame:
    """
    Variação mensal do IPCA por grupos — IBGE/SIDRA tabela 7060, variável 63.
    Retorna DataFrame com colunas: data, grupo_id, grupo, valor.
    """
    return _sidra_fetch(tabela=7060, variavel=63, periodos=meses)

@st.cache_data(ttl=3600, show_spinner=False)
def get_ipca_acum_grupo(meses: int = 60) -> pd.DataFrame:
    """
    Variação acumulada em 12 meses do IPCA por grupos — IBGE/SIDRA tabela 7060, variável 2265.
    Retorna DataFrame com colunas: data, grupo_id, grupo, valor.
    """
    return _sidra_fetch(tabela=7060, variavel=2265, periodos=meses)

# ─── TRANSFORMAÇÕES DE SÉRIE ──────────────────────────────────────────────────
def aplicar_periodo(df: pd.DataFrame, periodo: str, ind_nome: str) -> tuple:
    """
    Aplica transformação à série temporal.
    Retorna (df_transformado, label_unidade).
    """
    df = df.copy().sort_values("data").reset_index(drop=True)
    originais = {"Original", "Mensal (original)", "Var. trimestral (original)", "Nível (original)"}
    if periodo in originais:
        return df, df.attrs.get("unit", "")
    elif periodo == "Acumulado 12M":
        df["valor"] = df["valor"].rolling(12).sum()
        return df.dropna(), "% acum. 12M"
    elif periodo == "Acumulado no ano":
        df["valor"] = df.groupby(df["data"].dt.year)["valor"].cumsum()
        return df, "% acum. ano"
    elif periodo == "Var. mensal (m/m)":
        df["valor"] = df["valor"].pct_change(1) * 100
        return df.dropna(), "% m/m"
    elif periodo == "Var. trimestral (t/t)":
        df["valor"] = df["valor"].pct_change(3) * 100
        return df.dropna(), "% t/t"
    elif periodo == "Var. anual (a/a)":
        df["valor"] = df["valor"].pct_change(12) * 100
        return df.dropna(), "% a/a"
    elif periodo == "Acumulado 4 trimestres":
        df["valor"] = df["valor"].rolling(4).sum()
        return df.dropna(), "% acum. 4 tri"
    return df, ""

# ─── YAHOO FINANCE — sessão autenticada com crumb ─────────────────────────────
def _build_yf_session() -> tuple:
    """
    Abre requests.Session autenticada com cookie + crumb do Yahoo Finance.
    Retorna (session, crumb) ou lança RuntimeError se falhar.
    """
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get(_YF_COOKIE_URL, timeout=10)
    except Exception:
        pass
    r = s.get(_YF_CRUMB_URL, timeout=10)
    if r.status_code != 200 or not r.text.strip():
        raise RuntimeError(f"Yahoo crumb indisponível (status {r.status_code})")
    return s, r.text.strip()

def _get_yf_session() -> tuple:
    """
    Retorna (session, crumb) do cache em st.session_state.
    Renova automaticamente se expirado (>50min) ou ausente.
    """
    key   = "_yf_session_cache"
    cache = st.session_state.get(key)
    if cache and (time.time() - cache["ts"]) < 3000:
        return cache["session"], cache["crumb"]
    session, crumb = _build_yf_session()
    st.session_state[key] = {"session": session, "crumb": crumb, "ts": time.time()}
    return session, crumb

def _yf_request(sym: str, params: dict, retries: int = 3) -> dict | None:
    """
    Requisição autenticada ao Yahoo Finance chart endpoint.
    Renova sessão automaticamente em 401/429 com back-off exponencial.
    Retorna JSON parseado ou None em falha.
    """
    for attempt in range(retries):
        try:
            session, crumb = _get_yf_session()
            r = session.get(
                _YF_CHART_URL.format(sym=sym),
                params={**params, "crumb": crumb},
                timeout=12,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("chart", {}).get("result"):
                    return data
            if r.status_code in (401, 429):
                st.session_state.pop("_yf_session_cache", None)
                time.sleep(2 ** attempt)  # 1s → 2s → 4s
                continue
        except Exception:
            time.sleep(1)
    return None

# ─── YAHOO FINANCE — funções públicas ────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def get_quote(symbol: str) -> dict:
    """
    Cotação atual do ativo. Cache de 15min (alinhado com st.fragment run_every=900).
    Retorna dict com: price, prev, chg_p, chg_v, day_high, day_low,
    market, is_live, is_extended, is_closed, close_date.
    Retorna {} em caso de falha.
    """
    data = _yf_request(symbol, {"interval": "1d", "range": "5d"})
    if not data:
        return {}
    try:
        result = data["chart"]["result"][0]
        meta   = result["meta"]

        market_state = meta.get("marketState", "CLOSED")
        is_live      = market_state == "REGULAR"
        is_extended  = market_state in ("PRE", "POST", "PREPRE", "POSTPOST")
        is_closed    = not (is_live or is_extended)

        if is_live or is_extended:
            price      = meta.get("regularMarketPrice") or meta.get("previousClose")
            prev       = meta.get("chartPreviousClose") or meta.get("previousClose", price)
            close_date = None
        else:
            price   = meta.get("previousClose") or meta.get("regularMarketPrice")
            prev    = meta.get("chartPreviousClose") or price
            ts_list = result.get("timestamp", [])
            reg_ts  = meta.get("regularMarketTime")
            close_date = (
                datetime.fromtimestamp(ts_list[-1]).strftime("%d/%m/%Y") if ts_list
                else datetime.fromtimestamp(reg_ts).strftime("%d/%m/%Y") if reg_ts
                else None
            )

        if price is None:
            return {}

        chg_p    = ((price - prev) / prev * 100) if (prev and prev != 0) else None
        chg_v    = (price - prev) if prev else None
        day_high = meta.get("regularMarketDayHigh")
        day_low  = meta.get("regularMarketDayLow")

        return {
            "price":       float(price),
            "prev":        float(prev),
            "chg_p":       chg_p,
            "chg_v":       chg_v,
            "day_high":    float(day_high) if day_high else None,
            "day_low":     float(day_low)  if day_low  else None,
            "market":      market_state,
            "is_live":     is_live,
            "is_extended": is_extended,
            "is_closed":   is_closed,
            "close_date":  close_date,
        }
    except Exception:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(symbol: str, years: int = 5) -> pd.DataFrame:
    """
    Histórico diário de fechamento. Cache de 1h.
    Retorna DataFrame com colunas [data, valor], ou vazio em caso de falha.
    """
    data = _yf_request(symbol, {"interval": "1d", "range": f"{years}y"})
    if not data:
        return pd.DataFrame(columns=["data", "valor"])
    try:
        res    = data["chart"]["result"][0]
        ts     = res["timestamp"]
        closes = res["indicators"]["quote"][0]["close"]
        df = pd.DataFrame({
            "data":  pd.to_datetime(ts, unit="s"),
            "valor": closes,
        })
        return df.dropna().reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["data", "valor"])
