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
    BCB_BASE, YAHOO_SNAP, YAHOO_HIST, IBGE_SIDRA,
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


def _fetch(url: str) -> list:
    """Faz até 3 tentativas de GET e retorna lista JSON ou []."""
    for _ in range(3):
        try:
            r = requests.get(url, headers=HDRS, timeout=20, verify=False)
            if r.status_code == 200 and "html" not in r.headers.get("Content-Type", "").lower():
                data = r.json()
                if isinstance(data, list) and data:
                    return data
            time.sleep(0.8)
        except Exception:
            time.sleep(1)
    return []


def aplicar_periodo(df: pd.DataFrame, periodo: str, ind_nome: str):
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
_bcb_stale_cache: dict[int, tuple[pd.DataFrame, datetime]] = {}

def _build_with_fallback(raw: list, c: int) -> pd.DataFrame:
    """
    Constrói DataFrame. Se raw estiver vazio, tenta retornar dado anterior em cache.
    O DataFrame retornado em fallback terá o atributo 'stale_since' com a data do dado.
    """
    df = _build(raw)
    if not df.empty:
        _bcb_stale_cache[c] = (df.copy(), datetime.now())
        return df
    # Fallback: retorna dado anterior se existir
    if c in _bcb_stale_cache:
        df_old, fetched_at = _bcb_stale_cache[c]
        df_old = df_old.copy()
        df_old.attrs["stale_since"] = fetched_at
        logger.warning("BCB: série %s usando cache stale de %s", c, fetched_at.strftime("%d/%m/%Y %H:%M"))
        return df_old
    return df


# ── BCB/SGS ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=TTL_BCB, show_spinner=False)
def get_bcb(c: int, n: int) -> pd.DataFrame:
    """Últimos n registros da série BCB c."""
    raw = _fetch(BCB_BASE.format(c=c) + f"/ultimos/{n}?formato=json")
    if not raw:
        hoje = datetime.today()
        raw = _fetch(
            BCB_BASE.format(c=c) +
            f"?formato=json"
            f"&dataInicial={(hoje - timedelta(days=n * 45)).strftime('%d/%m/%Y')}"
            f"&dataFinal={hoje.strftime('%d/%m/%Y')}"
        )
    if not raw:
        logger.warning("BCB: série %s indisponível (últimos %s registros)", c, n)
    return _build_with_fallback(raw, c)


@st.cache_data(ttl=TTL_BCB, show_spinner=False)
def get_bcb_full(c: int) -> pd.DataFrame:
    """Série completa BCB c."""
    raw = _fetch(BCB_BASE.format(c=c) + "?formato=json")
    if not raw:
        logger.warning("BCB: série completa %s indisponível", c)
    return _build_with_fallback(raw, c)


@st.cache_data(ttl=TTL_BCB, show_spinner=False)
def get_bcb_range(c: int, ini: str, fim: str) -> pd.DataFrame:
    """Série BCB c no intervalo [ini, fim] (formato dd/mm/YYYY)."""
    raw = _fetch(BCB_BASE.format(c=c) + f"?formato=json&dataInicial={ini}&dataFinal={fim}")
    if not raw:
        logger.warning("BCB: série %s indisponível para %s→%s", c, ini, fim)
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



# ── Stooq — cotações e histórico ──────────────────────────────────────────────
# Stooq é gratuito, sem chave de API, sem bloqueio de IP de nuvem.
# URL de cotação:  https://stooq.com/q/l/?s=SYMBOL&f=sd2t2ohlcv&h&e=csv

# ── Cotações de mercado ────────────────────────────────────────────────────────
#
# Twelve Data  → IBOVESPA (1 crédito/req — plano gratuito: 800/dia)
# Polygon.io   → todos os internacionais (sem rate limit no gratuito)
# CoinGecko    → BTC e ETH (completamente gratuito, sem chave)
#
# Secrets necessários no Streamlit Cloud:
#   TWELVE_DATA_KEY = "..."
#   POLYGON_KEY     = "..."

TD_QUOTE  = "https://api.twelvedata.com/quote?symbol={sym}&apikey={key}"
TD_HIST   = "https://api.twelvedata.com/time_series?symbol={sym}&interval=1day&outputsize={n}&apikey={key}"

PG_SNAP   = "https://api.polygon.io/v2/snapshot/locale/global/markets/forex/tickers?tickers={tickers}&apiKey={key}"
PG_IDX    = "https://api.polygon.io/v3/snapshot?ticker.any_of={tickers}&apiKey={key}"
PG_PREV   = "https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?adjusted=true&apiKey={key}"
PG_HIST   = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_d}/{to_d}?adjusted=true&sort=asc&limit=5000&apiKey={key}"

CG_PRICE  = "https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
CG_HIST   = "https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days={days}"

_HDRS_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Twelve Data: só IBOVESPA ──────────────────────────────────────────────────
_TD_SYM = "BVSP"   # símbolo Twelve Data para o Bovespa

# ── Polygon.io: todos os internacionais ───────────────────────────────────────
# Formato: símbolo interno → ticker Polygon
# Índices:    I:SPX    Forex: C:USDBRL    Commodities: C:XAUUSD    Crypto: X:BTCUSD
_PG_SYMBOLS = {
    "usdbrl": ("C:USDBRL",  "forex"),
    "eurbrl": ("C:EURBRL",  "forex"),
    "^spx":   ("I:SPX",     "index"),
    "^ndx":   ("I:NDX",     "index"),
    "^dji":   ("I:DJI",     "index"),
    "^ukx":   ("I:FTSE",    "index"),
    "^dax":   ("I:DAX",     "index"),
    "sc.f":   ("C:XBRUSD",  "forex"),   # Brent Spot
    "cl.f":   ("C:WTIUSD",  "forex"),   # WTI Spot
    "gc.f":   ("C:XAUUSD",  "forex"),   # Ouro
    "si.f":   ("C:XAGUSD",  "forex"),   # Prata
    "hg.f":   ("C:XPTUSD",  "forex"),   # Cobre (usando platina como proxy se não disponível)
}

# CoinGecko IDs para cripto
_CG_IDS = {"btc.v": "bitcoin", "eth.v": "ethereum"}


def _get_td_key() -> str:
    try:    return st.secrets.get("TWELVE_DATA_KEY", "")
    except: return os.environ.get("TWELVE_DATA_KEY", "")


def _get_pg_key() -> str:
    try:    return st.secrets.get("POLYGON_KEY", "")
    except: return os.environ.get("POLYGON_KEY", "")


def _make_quote(price, prev, high, low, last_date) -> dict:
    """Monta dict de cotação no formato padrão."""
    price, prev = float(price), float(prev or price)
    is_today = (last_date == now_brt().date()) if last_date else False
    chg_p    = ((price - prev) / prev * 100) if prev else None
    return {
        "price":      price, "prev": prev,
        "chg_p":      chg_p, "chg_v": (price - prev) if prev else None,
        "day_high":   float(high) if high else None,
        "day_low":    float(low)  if low  else None,
        "market":     "REGULAR" if is_today else "CLOSED",
        "is_live":    is_today, "is_extended": False, "is_closed": not is_today,
        "close_date": last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None,
    }


# ── Twelve Data: IBOVESPA ─────────────────────────────────────────────────────

@st.cache_data(ttl=TTL_MERCADOS, show_spinner=False)
def _quote_bovespa(key: str) -> dict:
    """Cotação do IBOVESPA via Twelve Data."""
    try:
        r = requests.get(TD_QUOTE.format(sym=_TD_SYM, key=key),
                         headers=_HDRS_JSON, timeout=10, verify=False)
        if r.status_code != 200:
            logger.warning("Twelve Data BVSP HTTP %s", r.status_code)
            return {}
        q = r.json()
        if q.get("status") == "error" or q.get("code") == 429:
            logger.warning("Twelve Data BVSP: %s", q.get("message", ""))
            return {}
        price = float(q.get("close") or 0)
        if not price:
            return {}
        dt_str    = q.get("datetime", "")
        last_date = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
        return _make_quote(price, q.get("previous_close") or price,
                           q.get("high"), q.get("low"), last_date)
    except Exception as e:
        logger.warning("Twelve Data BVSP: %s", e)
        return {}


# ── Polygon.io: internacionais ────────────────────────────────────────────────

def _pg_parse_prev(ticker_pg: str, data: dict) -> dict | None:
    """Parseia resposta do endpoint /prev do Polygon.io."""
    try:
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        price     = float(r.get("c", 0))  # close
        prev      = float(r.get("o", 0))  # open como proxy do prev close
        high      = r.get("h")
        low       = r.get("l")
        ts        = r.get("t", 0)
        last_date = datetime.fromtimestamp(ts / 1000).date() if ts else None
        if not price:
            return None
        return _make_quote(price, prev, high, low, last_date)
    except Exception:
        return None


@st.cache_data(ttl=TTL_MERCADOS, show_spinner=False)
def _quotes_polygon(key: str) -> dict:
    """Cotações de todos os internacionais via Polygon.io (prev close endpoint)."""
    out = {}
    for sym_int, (pg_ticker, _) in _PG_SYMBOLS.items():
        try:
            r = requests.get(PG_PREV.format(ticker=pg_ticker, key=key),
                             headers=_HDRS_JSON, timeout=10, verify=False)
            if r.status_code == 200:
                parsed = _pg_parse_prev(pg_ticker, r.json())
                if parsed:
                    out[sym_int] = parsed
                else:
                    logger.warning("Polygon: sem dados para %s (%s)", sym_int, pg_ticker)
            elif r.status_code == 403:
                logger.warning("Polygon: acesso negado para %s — verifique o plano", pg_ticker)
            else:
                logger.warning("Polygon: HTTP %s para %s", r.status_code, pg_ticker)
        except Exception as e:
            logger.warning("Polygon %s: %s", pg_ticker, e)
    return out


# ── CoinGecko: cripto ─────────────────────────────────────────────────────────

@st.cache_data(ttl=TTL_MERCADOS, show_spinner=False)
def _quotes_crypto() -> dict:
    """BTC e ETH via CoinGecko — gratuito, sem chave."""
    try:
        ids = ",".join(_CG_IDS.values())
        r   = requests.get(CG_PRICE.format(ids=ids),
                           headers=_HDRS_JSON, timeout=10, verify=False)
        if r.status_code != 200:
            logger.warning("CoinGecko HTTP %s", r.status_code)
            return {}
        data = r.json()
        out  = {}
        for sym, cg_id in _CG_IDS.items():
            q = data.get(cg_id, {})
            price = float(q.get("usd", 0))
            if not price:
                continue
            chg_p = float(q.get("usd_24h_change", 0) or 0)
            prev  = price / (1 + chg_p / 100) if chg_p else price
            out[sym] = {
                "price": price, "prev": prev,
                "chg_p": chg_p, "chg_v": price - prev,
                "day_high": None, "day_low": None,
                "market": "REGULAR", "is_live": True,
                "is_extended": False, "is_closed": False, "close_date": None,
            }
        return out
    except Exception as e:
        logger.warning("CoinGecko: %s", e)
        return {}


# ── Interface pública ─────────────────────────────────────────────────────────

def get_all_quotes(symbols: tuple) -> dict:
    """
    Cotações de todos os ativos:
    - IBOVESPA → Twelve Data (1 crédito/req)
    - Internacionais → Polygon.io (sem rate limit)
    - BTC, ETH → CoinGecko (gratuito)
    """
    td_key = _get_td_key()
    pg_key = _get_pg_key()
    out    = {}

    if td_key:
        bvsp = _quote_bovespa(td_key)
        if bvsp:
            out["^BVSP"] = bvsp
    else:
        logger.warning("TWELVE_DATA_KEY não configurado")

    if pg_key:
        out.update(_quotes_polygon(pg_key))
    else:
        logger.warning("POLYGON_KEY não configurado")

    out.update(_quotes_crypto())

    for sym in symbols:
        if sym not in out:
            logger.warning("Cotação indisponível para %s", sym)
    return out


def get_quote(sym: str) -> dict:
    """Cotação individual — usa cache batch interno."""
    from settings import GLOBAL
    return get_all_quotes(tuple(s for s, _, _ in GLOBAL.values())).get(sym, {})


@st.cache_data(ttl=TTL_HIST, show_spinner=False)
def get_hist(sym: str, years: int = 5) -> pd.DataFrame:
    """
    Histórico de fechamento.
    - IBOVESPA → Twelve Data
    - Internacionais → Polygon.io
    - Cripto → CoinGecko
    """
    td_key = _get_td_key()
    pg_key = _get_pg_key()

    # IBOVESPA via Twelve Data
    if sym == "^BVSP" and td_key:
        try:
            outputsize = min(years * 260, 5000)
            r = requests.get(TD_HIST.format(sym=_TD_SYM, n=outputsize, key=td_key),
                             headers=_HDRS_JSON, timeout=20, verify=False)
            if r.status_code == 200:
                values = r.json().get("values", [])
                rows   = []
                for v in values:
                    try:
                        rows.append({"data":  datetime.strptime(v["datetime"][:10], "%Y-%m-%d"),
                                     "valor": float(v["close"])})
                    except Exception:
                        continue
                if rows:
                    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        except Exception as e:
            logger.warning("Twelve Data hist BVSP: %s", e)

    # Cripto via CoinGecko
    cg_id = _CG_IDS.get(sym)
    if cg_id:
        try:
            r = requests.get(CG_HIST.format(id=cg_id, days=years*365),
                             headers=_HDRS_JSON, timeout=20, verify=False)
            if r.status_code == 200:
                prices = r.json().get("prices", [])
                rows   = [{"data": datetime.fromtimestamp(p[0]/1000), "valor": float(p[1])}
                          for p in prices]
                if rows:
                    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        except Exception as e:
            logger.warning("CoinGecko hist %s: %s", sym, e)

    # Internacionais via Polygon.io
    pg_ticker = _PG_SYMBOLS.get(sym, (None,))[0]
    if pg_ticker and pg_key:
        try:
            to_d   = datetime.now().strftime("%Y-%m-%d")
            from_d = (datetime.now() - timedelta(days=years*365+10)).strftime("%Y-%m-%d")
            r = requests.get(PG_HIST.format(ticker=pg_ticker, from_d=from_d, to_d=to_d, key=pg_key),
                             headers=_HDRS_JSON, timeout=20, verify=False)
            if r.status_code == 200:
                results = r.json().get("results", [])
                rows    = []
                for v in results:
                    try:
                        rows.append({"data":  datetime.fromtimestamp(v["t"]/1000),
                                     "valor": float(v["c"])})
                    except Exception:
                        continue
                if rows:
                    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        except Exception as e:
            logger.warning("Polygon hist %s: %s", pg_ticker, e)

    return pd.DataFrame(columns=["data", "valor"])
