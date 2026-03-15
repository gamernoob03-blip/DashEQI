"""
data.py — Camada de dados: BCB/SGS, IBGE/SIDRA, mercados via Twelve Data + CoinGecko.
Todas as funções retornam DataFrames ou dicts prontos para consumo pelas páginas.
Nenhuma lógica de UI aqui.
"""
import re, time, warnings, os
import requests, urllib3
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

from settings import (
    logger, HDRS,
    TTL_BCB, TTL_IBGE, TTL_MERCADOS, TTL_HIST,
    BCB_BASE, IBGE_SIDRA,
    IPCA_GRUPOS_IDS, TZ_BRT,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS")


def now_brt():
    from datetime import datetime
    return datetime.now(TZ_BRT)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _limpa_nome_grupo(nome: str) -> str:
    """Remove prefixo numérico ('9.Educação' → 'Educação') e espaços extras."""
    nome = str(nome).strip()
    nome = re.sub(r"^\d+[\.\-\s]+", "", nome)
    return nome.strip()


def _parse(v):
    """Converte string de valor BCB para float, tratando vírgula como decimal."""
    if v is None:
        return None
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _build(raw: list) -> pd.DataFrame:
    """Constrói DataFrame padronizado [data, valor] a partir da resposta BCB."""
    if not raw:
        return pd.DataFrame(columns=["data", "valor"])
    df = pd.DataFrame(raw)
    if "data" not in df.columns:
        return pd.DataFrame(columns=["data", "valor"])
    df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = df["valor"].apply(_parse)
    return (df.dropna(subset=["data", "valor"])
              .sort_values("data")
              .reset_index(drop=True)
              [["data", "valor"]])


def _fetch(url: str, retries: int = 3, timeout: int = 20) -> list:
    """Faz até `retries` tentativas de GET e retorna lista JSON ou []."""
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HDRS, timeout=timeout, verify=False)
            if r.status_code == 200 and "html" not in r.headers.get("Content-Type", "").lower():
                data = r.json()
                if isinstance(data, list) and data:
                    return data
            time.sleep(0.8)
        except Exception as e:
            logger.warning("BCB fetch erro: %s", e)
            time.sleep(1)
    return []


def aplicar_periodo(df: pd.DataFrame, periodo: str, ind_nome: str) -> tuple[pd.DataFrame, str]:
    """
    Aplica transformação temporal a uma série BCB.
    Retorna (df_transformado, unidade_label).
    """
    df = df.copy().sort_values("data").reset_index(drop=True)
    if periodo in ("Original", "Mensal (original)", "Var. trimestral (original)", "Nível (original)"):
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


# ── Cache de fallback (dados antigos quando API está fora) ────────────────────
# Armazena sempre a série completa — get_bcb_full é a única função de fetch.
_bcb_stale_cache: dict[int, tuple[pd.DataFrame, datetime]] = {}


def _build_with_fallback(raw: list, c: int) -> pd.DataFrame:
    """
    Constrói DataFrame. Se raw estiver vazio, retorna a última série completa
    do cache com o atributo 'stale_since' para exibir o aviso ao usuário.
    """
    df = _build(raw)
    if not df.empty:
        _bcb_stale_cache[c] = (df.copy(), datetime.now())
        return df
    if c in _bcb_stale_cache:
        df_old, fetched_at = _bcb_stale_cache[c]
        df_old = df_old.copy()
        df_old.attrs["stale_since"] = fetched_at
        logger.warning("BCB: série %s usando cache stale de %s", c, fetched_at.strftime("%d/%m/%Y %H:%M"))
        return df_old
    return df


# ── BCB/SGS ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=TTL_BCB, show_spinner=False)
def get_bcb_full(c: int) -> pd.DataFrame:
    """
    Série BCB c — tenta série completa com fallbacks progressivos.
    Toda filtragem por período é feita em memória nas páginas.
    """
    hoje = datetime.today()

    # Tenta série completa primeiro (3 retries, timeout 20s)
    raw = _fetch(BCB_BASE.format(c=c) + "?formato=json")

    # Fallbacks progressivos com timeout reduzido (1 retry, 12s)
    for anos in [10, 5, 2]:
        if raw:
            break
        ini = (hoje - timedelta(days=365 * anos)).strftime("%d/%m/%Y")
        fim = hoje.strftime("%d/%m/%Y")
        raw = _fetch(BCB_BASE.format(c=c) + f"?formato=json&dataInicial={ini}&dataFinal={fim}",
                     retries=1, timeout=12)
        if raw:
            logger.info("BCB: série %s obtida via fallback %da", c, anos)

    if not raw:
        logger.warning("BCB: série completa %s indisponível", c)
    return _build_with_fallback(raw, c)


# ── IBGE/SIDRA ────────────────────────────────────────────────────────────────

def _parse_sidra_resultado(resultado: dict) -> tuple[str, str, dict] | None:
    """Extrai grupo_id, grupo_nome e série de um resultado SIDRA."""
    cats = resultado.get("classificacoes", [])
    if not cats:
        return None
    cat_dict   = cats[0].get("categoria", {})
    grupo_id   = str(next(iter(cat_dict), ""))
    raw_nome   = next(iter(cat_dict.values()), "")
    grupo_nome = _limpa_nome_grupo(raw_nome)
    series_list = resultado.get("series", [])
    if not series_list or not grupo_nome:
        return None
    return grupo_id, grupo_nome, series_list[0].get("serie", {})


@st.cache_data(ttl=TTL_IBGE, show_spinner=False)
def get_ipca_grupos(n_periodos: int = 60) -> pd.DataFrame:
    """
    Variação mensal do IPCA por grupo — IBGE SIDRA tabela 7060, variável 63.
    Retorna colunas: [data, grupo_id, grupo, valor].
    """
    url = IBGE_SIDRA.format(
        tabela="7060", periodos=f"-{n_periodos}",
        var="63", cls=f"315[{IPCA_GRUPOS_IDS}]",
    )
    try:
        r = requests.get(url, headers=HDRS, timeout=30)
        r.raise_for_status()
        rows = []
        for variavel in r.json():
            for resultado in variavel.get("resultados", []):
                parsed = _parse_sidra_resultado(resultado)
                if not parsed:
                    continue
                grupo_id, grupo_nome, serie = parsed
                for periodo, valor in serie.items():
                    try:
                        rows.append({
                            "data":     pd.to_datetime(periodo, format="%Y%m"),
                            "grupo_id": grupo_id,
                            "grupo":    grupo_nome,
                            "valor":    float(str(valor).replace(",", ".")),
                        })
                    except Exception:
                        pass
        if not rows:
            return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])
        return pd.DataFrame(rows).sort_values(["data", "grupo"]).reset_index(drop=True)
    except Exception as e:
        logger.warning("IBGE SIDRA: falha na variação mensal por grupo — %s", e)
        return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])


@st.cache_data(ttl=TTL_IBGE, show_spinner=False)
def get_ipca_acum_grupo(n_periodos: int = 60) -> pd.DataFrame:
    """
    Variação acumulada 12M do IPCA por grupo — IBGE SIDRA tabela 7060, variável 2266.
    Retorna colunas: [data, grupo_id, grupo, valor].
    """
    url = IBGE_SIDRA.format(
        tabela="7060", periodos=f"-{n_periodos}",
        var="2266", cls=f"315[{IPCA_GRUPOS_IDS}]",
    )
    try:
        r = requests.get(url, headers=HDRS, timeout=30)
        r.raise_for_status()
        rows = []
        for variavel in r.json():
            for resultado in variavel.get("resultados", []):
                parsed = _parse_sidra_resultado(resultado)
                if not parsed:
                    continue
                grupo_id, grupo_nome, serie = parsed
                for periodo, valor in serie.items():
                    try:
                        rows.append({
                            "data":     pd.to_datetime(periodo, format="%Y%m"),
                            "grupo_id": grupo_id,
                            "grupo":    grupo_nome,
                            "valor":    float(str(valor).replace(",", ".")),
                        })
                    except Exception:
                        pass
        if not rows:
            return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])
        return pd.DataFrame(rows).sort_values(["data", "grupo"]).reset_index(drop=True)
    except Exception as e:
        logger.warning("IBGE SIDRA: falha no acumulado 12M por grupo — %s", e)
        return pd.DataFrame(columns=["data", "grupo_id", "grupo", "valor"])




# ── Cotações de mercado — yfinance + cache de servidor ────────────────────────
#
# Estratégia: background thread renova o cache a cada 13 minutos.
# yfinance só é chamado pelo servidor, nunca por page load de usuário.
# Resultado: zero rate limit — qualquer usuário recebe dados do cache.

import threading as _threading
import yfinance as _yf

_HDRS_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Mapa símbolo interno → símbolo Yahoo Finance
_YF_SYMBOLS = {
    "^BVSP":  "^BVSP",
    "usdbrl": "USDBRL=X",
    "eurbrl": "EURBRL=X",
    "^spx":   "^GSPC",
    "^ndx":   "^NDX",
    "^dji":   "^DJI",
    "^ukx":   "^FTSE",
    "^dax":   "^GDAXI",
    "sc.f":   "BZ=F",
    "cl.f":   "CL=F",
    "gc.f":   "GC=F",
    "si.f":   "SI=F",
    "hg.f":   "HG=F",
    "btc.v":  "BTC-USD",
    "eth.v":  "ETH-USD",
}
# Inverso para lookup rápido
_YF_INV = {v: k for k, v in _YF_SYMBOLS.items()}


def _fetch_yf_quotes() -> dict:
    """
    Busca cotações via yfinance em batch sequencial (threads=False).
    Evita esgotamento do connection pool e rate limit por requisições simultâneas.
    """
    yf_syms = list(_YF_SYMBOLS.values())
    for attempt in range(3):
        try:
            df = _yf.download(
                yf_syms,
                period="5d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=False,   # sequencial — evita connection pool overflow
            )
            if df.empty:
                logger.warning("yfinance: download retornou vazio (tentativa %d)", attempt+1)
                time.sleep(15 * (attempt + 1))  # backoff: 15s, 30s, 45s
                continue

            out = {}
            for yf_sym in yf_syms:
                try:
                    if isinstance(df.columns, pd.MultiIndex):
                        closes = df[yf_sym]["Close"].dropna()
                        highs  = df[yf_sym]["High"].dropna()
                        lows   = df[yf_sym]["Low"].dropna()
                    else:
                        closes = df["Close"].dropna()
                        highs  = df["High"].dropna()
                        lows   = df["Low"].dropna()

                    if closes.empty:
                        continue

                    price     = float(closes.iloc[-1])
                    prev      = float(closes.iloc[-2]) if len(closes) >= 2 else price
                    high      = float(highs.iloc[-1]) if not highs.empty else None
                    low       = float(lows.iloc[-1])  if not lows.empty  else None
                    last_date = pd.Timestamp(closes.index[-1]).tz_localize(None).date()
                    is_today  = (last_date == now_brt().date())
                    chg_p     = ((price - prev) / prev * 100) if prev else None

                    internal = _YF_INV.get(yf_sym)
                    if internal:
                        out[internal] = {
                            "price":       price, "prev": prev,
                            "chg_p":       chg_p, "chg_v": price - prev,
                            "day_high":    high,  "day_low": low,
                            "market":      "REGULAR" if is_today else "CLOSED",
                            "is_live":     is_today, "is_extended": False,
                            "is_closed":   not is_today,
                            "close_date":  last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None,
                        }
                except Exception as e:
                    logger.warning("yfinance parse %s: %s", yf_sym, e)

            logger.info("yfinance: %d/%d símbolos obtidos", len(out), len(yf_syms))
            return out

        except Exception as e:
            logger.warning("yfinance download (tentativa %d): %s", attempt+1, e)
            time.sleep(15 * (attempt + 1))

    return {}


# ── Cache compartilhado (15 min) ──────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def _cached_quotes() -> dict:
    """Cache de 15 min compartilhado entre todos os usuários."""
    return _fetch_yf_quotes()


# ── Background refresher ──────────────────────────────────────────────────────

def _prewarm_home_bcb() -> None:
    """
    Pré-aquece as séries BCB usadas na página Início.
    Busca somente as séries de HOME_CHARTS + HOME_KPIS — não todas do SGS.
    TTL de 1h — renova a cada 55min para nunca expirar durante o uso.
    """
    from settings import HOME_CHARTS, HOME_KPIS, SGS
    # Códigos únicos das séries da página Início
    codigos = list(dict.fromkeys(
        SGS[nome][0]
        for nome, *_ in list(HOME_CHARTS) + list(HOME_KPIS)
        if nome in SGS
    ))
    for cod in codigos:
        try:
            get_bcb_full(cod)
        except Exception as e:
            logger.warning("Pré-aquecimento BCB %s: %s", cod, e)
    logger.info("Pré-aquecimento BCB: %d séries da página Início prontas", len(codigos))


def _bg_refresh_loop():
    """
    Thread de fundo: renova cotações (13 min) e séries BCB do Início (55 min).
    Zero latência para qualquer usuário — cache sempre quente.
    """
    time.sleep(30)  # aguarda app inicializar completamente
    _prewarm_home_bcb()  # pré-aquece BCB logo na primeira vez

    _bcb_counter = 0
    while True:
        try:
            # Cotações yfinance — a cada 13 min
            data = _fetch_yf_quotes()
            if data:
                # Limpa só o cache de cotações, preserva BCB e histórico
                _cached_quotes.clear()
                _cached_quotes()  # força re-população imediata
            logger.info("Background refresh: %d cotações renovadas", len(data))
        except Exception as e:
            logger.warning("Background refresh cotações: %s", e)

        _bcb_counter += 1
        if _bcb_counter >= 4:  # 4 × 13 min = 52 min ≈ antes do TTL de 1h
            try:
                _prewarm_home_bcb()
            except Exception as e:
                logger.warning("Background refresh BCB: %s", e)
            _bcb_counter = 0

        time.sleep(780)  # 13 minutos


@st.cache_resource
def _start_bg_refresher():
    """Inicia o thread de fundo uma única vez por processo Streamlit."""
    t = _threading.Thread(target=_bg_refresh_loop, daemon=True)
    t.start()
    logger.info("Background refresher iniciado (cotações 13min · BCB Início 55min)")
    return t

_start_bg_refresher()


# ── Interface pública ─────────────────────────────────────────────────────────

def get_all_quotes(symbols: tuple) -> dict:
    """
    Retorna cotações do cache compartilhado.
    Background thread garante cache sempre quente — zero latência para o usuário.
    """
    out = _cached_quotes()
    for sym in symbols:
        if sym not in out:
            logger.warning("Cotação indisponível para %s", sym)
    return out


def get_quote(sym: str) -> dict:
    """Cotação individual — usa cache batch interno."""
    from settings import GLOBAL
    return get_all_quotes(tuple(a.simbolo for a in GLOBAL.values())).get(sym, {})


@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(sym: str, years: int = 5) -> pd.DataFrame:
    """Histórico de fechamento via yfinance."""
    yf_sym = _YF_SYMBOLS.get(sym)
    if not yf_sym:
        return pd.DataFrame(columns=["data", "valor"])
    try:
        tk  = _yf.Ticker(yf_sym)
        df  = tk.history(period=f"{years}y", auto_adjust=True)
        if df.empty:
            logger.warning("yfinance hist vazio para %s", yf_sym)
            return pd.DataFrame(columns=["data", "valor"])
        result = pd.DataFrame({
            "data":  pd.to_datetime(df.index).tz_localize(None),
            "valor": df["Close"].values.flatten(),
        })
        return result.dropna().sort_values("data").reset_index(drop=True)
    except Exception as e:
        logger.warning("yfinance hist %s: %s", yf_sym, e)
        return pd.DataFrame(columns=["data", "valor"])


# ── Boletim Focus (BCB/Expectativas) ─────────────────────────────────────────

@st.cache_data(ttl=86_400, show_spinner=False)
def get_focus_anual(indicador: str, anos: int = 5) -> pd.DataFrame:
    """
    Expectativas anuais do Boletim Focus para um indicador.
    Retorna mediana por data de referência (ano) e data de divulgação.
    Colunas: data, ano_ref, mediana, desvio_padrao, minimo, maximo.
    """
    from settings import FOCUS_BASE
    import urllib.parse
    hoje = datetime.today()
    ini  = (hoje - timedelta(days=anos * 365)).strftime("%Y-%m-%d")
    filtro = (
        f"Indicador eq '{indicador}' and "
        f"Data ge '{ini}' and "
        f"baseCalculo eq 0"
    )
    url = (
        f"{FOCUS_BASE}/ExpectativasMercadoAnuais"
        f"?$filter={urllib.parse.quote(filtro)}"
        f"&$select=Indicador,Data,DataReferencia,Mediana,DesvioPadrao,Minimo,Maximo"
        f"&$orderby=Data desc"
        f"&$format=json"
        f"&$top=5000"
    )
    try:
        r = requests.get(url, headers=HDRS, timeout=20, verify=False)
        r.raise_for_status()
        rows = r.json().get("value", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["data"]     = pd.to_datetime(df["Data"])
        df["ano_ref"]  = df["DataReferencia"].astype(str)
        df["mediana"]  = pd.to_numeric(df["Mediana"],      errors="coerce")
        df["desvio"]   = pd.to_numeric(df["DesvioPadrao"], errors="coerce")
        df["minimo"]   = pd.to_numeric(df["Minimo"],       errors="coerce")
        df["maximo"]   = pd.to_numeric(df["Maximo"],       errors="coerce")
        return df[["data","ano_ref","mediana","desvio","minimo","maximo"]].dropna(subset=["mediana"]).sort_values("data").reset_index(drop=True)
    except Exception as e:
        logger.warning("Focus anual %s: %s", indicador, e)
        return pd.DataFrame()


@st.cache_data(ttl=86_400, show_spinner=False)
def get_focus_12m(indicador: str, anos: int = 3) -> pd.DataFrame:
    """
    Expectativas do Boletim Focus para os próximos 12 meses (suavizado).
    Retorna mediana por data de divulgação.
    """
    from settings import FOCUS_BASE
    import urllib.parse
    hoje = datetime.today()
    ini  = (hoje - timedelta(days=anos * 365)).strftime("%Y-%m-%d")
    filtro = (
        f"Indicador eq '{indicador}' and "
        f"Data ge '{ini}' and "
        f"Suavizado eq 'S'"
    )
    url = (
        f"{FOCUS_BASE}/ExpectativasMercadoInflacao12Meses"
        f"?$filter={urllib.parse.quote(filtro)}"
        f"&$select=Indicador,Data,Suavizado,Mediana,DesvioPadrao,Minimo,Maximo"
        f"&$orderby=Data desc"
        f"&$format=json"
        f"&$top=2000"
    )
    try:
        r = requests.get(url, headers=HDRS, timeout=20, verify=False)
        r.raise_for_status()
        rows = r.json().get("value", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["data"]    = pd.to_datetime(df["Data"])
        df["mediana"] = pd.to_numeric(df["Mediana"],      errors="coerce")
        df["desvio"]  = pd.to_numeric(df["DesvioPadrao"], errors="coerce")
        df["minimo"]  = pd.to_numeric(df["Minimo"],       errors="coerce")
        df["maximo"]  = pd.to_numeric(df["Maximo"],       errors="coerce")
        return df[["data","mediana","desvio","minimo","maximo"]].dropna(subset=["mediana"]).sort_values("data").reset_index(drop=True)
    except Exception as e:
        logger.warning("Focus 12M %s: %s", indicador, e)
        return pd.DataFrame()
