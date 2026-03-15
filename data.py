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
# URL de histórico: https://stooq.com/q/d/l/?s=SYMBOL&i=d

# ── Cotações de mercado — Twelve Data + CoinGecko ─────────────────────────────
#
# Twelve Data (twelvedata.com):
#   - Plano gratuito: 800 créditos/dia, sem cartão de crédito
#   - Configure em Streamlit Cloud → Manage app → Secrets:
#       TWELVE_DATA_KEY = "sua_chave_aqui"
#   - Cobre: índices, forex, commodities, cripto
#
# CoinGecko: BTC e ETH como fallback (completamente gratuito, sem chave)

TD_BATCH    = "https://api.twelvedata.com/quote?symbol={syms}&apikey={key}"
TD_HIST     = "https://api.twelvedata.com/time_series?symbol={sym}&interval=1day&outputsize={n}&apikey={key}"
CG_PRICE    = "https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
CG_HIST     = "https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days={days}"

_HDRS_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Mapa símbolo → id CoinGecko (para BTC e ETH)
_COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
}

# Mapa símbolo Stooq/interno → símbolo Twelve Data
_TD_SYMBOLS = {
    "^BVSP":  "IBOV:Index",
    "usdbrl": "USD/BRL:Forex",
    "eurbrl": "EUR/BRL:Forex",
    "^spx":   "SPX:Index",
    "^ndx":   "NDX:Index",
    "^dji":   "DJI:Index",
    "^ukx":   "UKX:Index",
    "^dax":   "DAX:Index",
    "sc.f":   "USOIL:Commodity",
    "cl.f":   "WTI:Commodity",
    "gc.f":   "XAU/USD:Forex",
    "si.f":   "XAG/USD:Forex",
    "hg.f":   "XCU/USD:Forex",
    "btc.v":  "BTC/USD:Forex",
    "eth.v":  "ETH/USD:Forex",
}


def _get_td_key() -> str:
    """Lê a chave Twelve Data dos secrets do Streamlit (ou variável de ambiente)."""
    try:
        return st.secrets.get("TWELVE_DATA_KEY", "")
    except Exception:
        return os.environ.get("TWELVE_DATA_KEY", "")


def _parse_td_quote(sym_internal: str, q: dict) -> dict | None:
    """Converte resposta Twelve Data para o formato padrão."""
    try:
        price = float(q.get("close") or q.get("price") or 0)
        prev  = float(q.get("previous_close") or price)
        if not price:
            return None
        dt_str    = q.get("datetime", "")
        try:
            last_date = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
        except Exception:
            last_date = now_brt().date()
        is_today  = (last_date == now_brt().date())
        chg_p     = ((price - prev) / prev * 100) if prev else None
        return {
            "price":      price, "prev": prev,
            "chg_p":      chg_p, "chg_v": (price - prev) if prev else None,
            "day_high":   float(q["high"])  if q.get("high")  else None,
            "day_low":    float(q["low"])   if q.get("low")   else None,
            "market":     "REGULAR" if is_today else "CLOSED",
            "is_live":    is_today, "is_extended": False, "is_closed": not is_today,
            "close_date": last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None,
        }
    except Exception:
        return None


def _fetch_td_quotes(symbols_internal: list[str], key: str) -> dict[str, dict]:
    """Busca cotações em batch via Twelve Data."""
    td_syms   = [_TD_SYMBOLS[s] for s in symbols_internal if s in _TD_SYMBOLS]
    sym_map   = {_TD_SYMBOLS[s]: s for s in symbols_internal if s in _TD_SYMBOLS}
    if not td_syms or not key:
        return {}
    try:
        r = requests.get(
            TD_BATCH.format(syms=",".join(td_syms), key=key),
            headers=_HDRS_JSON, timeout=20, verify=False,
        )
        if r.status_code != 200:
            logger.warning("Twelve Data HTTP %s", r.status_code)
            return {}
        data = r.json()
        out  = {}
        # Resposta pode ser dict único (1 símbolo) ou dict de dicts (vários)
        if "symbol" in data:
            data = {data["symbol"]: data}
        for td_sym, q in data.items():
            if isinstance(q, dict) and q.get("status") != "error":
                internal = sym_map.get(td_sym)
                if internal:
                    parsed = _parse_td_quote(internal, q)
                    if parsed:
                        out[internal] = parsed
        return out
    except Exception as e:
        logger.warning("Twelve Data batch: %s", e)
        return {}


def _fetch_coingecko_quotes(syms_btc_eth: list[str]) -> dict[str, dict]:
    """Cotações de BTC e ETH via CoinGecko (gratuito, sem chave)."""
    id_map = {}
    for s in syms_btc_eth:
        # btc.v → BTC, eth.v → ETH
        ticker = s.split(".")[0].upper()
        if ticker in _COINGECKO_IDS:
            id_map[_COINGECKO_IDS[ticker]] = s
    if not id_map:
        return {}
    try:
        r = requests.get(
            CG_PRICE.format(ids=",".join(id_map.keys())),
            headers=_HDRS_JSON, timeout=10, verify=False,
        )
        if r.status_code != 200:
            logger.warning("CoinGecko HTTP %s", r.status_code)
            return {}
        data = r.json()
        out  = {}
        for cg_id, internal_sym in id_map.items():
            q = data.get(cg_id, {})
            price = float(q.get("usd", 0))
            if not price:
                continue
            chg_p = float(q.get("usd_24h_change", 0))
            prev  = price / (1 + chg_p / 100) if chg_p else price
            out[internal_sym] = {
                "price":      price, "prev": prev,
                "chg_p":      chg_p, "chg_v": (price - prev),
                "day_high":   None, "day_low": None,
                "market":     "REGULAR",
                "is_live":    True, "is_extended": False, "is_closed": False,
                "close_date": None,
            }
        return out
    except Exception as e:
        logger.warning("CoinGecko: %s", e)
        return {}


@st.cache_data(ttl=TTL_MERCADOS, show_spinner=False)
def get_all_quotes(symbols: tuple) -> dict:
    """
    Cotações em batch.
    - Twelve Data (requer TWELVE_DATA_KEY nos secrets) para índices/forex/commodities
    - CoinGecko como fallback gratuito para BTC e ETH
    """
    key  = _get_td_key()
    syms = list(symbols)
    out  = {}

    if key:
        out = _fetch_td_quotes(syms, key)
    else:
        logger.warning("TWELVE_DATA_KEY não configurado — sem cotações de mercado")

    # CoinGecko para cripto (gratuito, independente da chave)
    crypto_syms = [s for s in syms if s in ("btc.v", "eth.v")]
    if crypto_syms:
        cg = _fetch_coingecko_quotes(crypto_syms)
        out.update(cg)

    for sym in symbols:
        if sym not in out:
            logger.warning("Cotação indisponível para %s", sym)
    return out


def get_quote(sym: str) -> dict:
    """Cotação individual via cache batch."""
    from settings import GLOBAL
    all_syms = tuple(s for s, _, _ in GLOBAL.values())
    return get_all_quotes(all_syms).get(sym, {})


@st.cache_data(ttl=TTL_HIST, show_spinner=False)
def get_hist(sym: str, years: int = 5) -> pd.DataFrame:
    """
    Histórico de fechamento.
    - Twelve Data para todos os ativos (requer TWELVE_DATA_KEY)
    - CoinGecko como fallback para BTC e ETH
    """
    key = _get_td_key()
    td_sym = _TD_SYMBOLS.get(sym)

    # Twelve Data
    if key and td_sym:
        try:
            outputsize = min(years * 260, 5000)  # ~260 dias úteis/ano, max 5000
            r = requests.get(
                TD_HIST.format(sym=td_sym, n=outputsize, key=key),
                headers=_HDRS_JSON, timeout=20, verify=False,
            )
            if r.status_code == 200:
                data   = r.json()
                values = data.get("values", [])
                rows   = []
                for v in values:
                    try:
                        rows.append({
                            "data":  datetime.strptime(v["datetime"][:10], "%Y-%m-%d"),
                            "valor": float(v["close"]),
                        })
                    except Exception:
                        continue
                if rows:
                    return (pd.DataFrame(rows)
                              .sort_values("data")
                              .reset_index(drop=True))
        except Exception as e:
            logger.warning("Twelve Data hist %s: %s", sym, e)

    # CoinGecko fallback para cripto
    ticker = sym.split(".")[0].upper()
    cg_id  = _COINGECKO_IDS.get(ticker)
    if cg_id:
        try:
            days = years * 365
            r = requests.get(
                CG_HIST.format(id=cg_id, days=days),
                headers=_HDRS_JSON, timeout=20, verify=False,
            )
            if r.status_code == 200:
                prices = r.json().get("prices", [])
                rows   = [{"data": datetime.fromtimestamp(p[0]/1000), "valor": float(p[1])}
                          for p in prices]
                if rows:
                    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        except Exception as e:
            logger.warning("CoinGecko hist %s: %s", sym, e)

    return pd.DataFrame(columns=["data", "valor"])
