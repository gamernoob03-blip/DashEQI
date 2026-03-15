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

# ── Cotações de mercado — Twelve Data + CoinGecko ─────────────────────────────
#
# Twelve Data (plano gratuito): 8 créditos/minuto, 800/dia
# Solução para 15 símbolos > 8/min:
#   Grupo A (7 syms) → busca imediata
#   sleep(62s)        → aguarda janela do rate limit zerar
#   Grupo B (8 syms) → busca na segunda janela
#   Cache de 130s    → todo esse processo roda 1x a cada ~2 minutos
#
# CoinGecko: BTC e ETH (gratuito, sem chave, sem limite relevante)
#
# Secret necessário: TWELVE_DATA_KEY = "..."

TD_QUOTE = "https://api.twelvedata.com/quote?symbol={syms}&apikey={key}"
TD_HIST  = "https://api.twelvedata.com/time_series?symbol={sym}&interval=1day&outputsize={n}&apikey={key}"
CG_PRICE = "https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
CG_HIST  = "https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days={days}"

_HDRS_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Grupos para respeitar 8 créditos/minuto
# Grupo A: 7 símbolos prioritários (câmbio, índices BR e EUA principais)
# Grupo B: 8 símbolos secundários (Europa, energia, metais)
_GROUP_A = {
    "^BVSP":  "BVSP",      # Bovespa
    "usdbrl": "USD/BRL",   # Dólar/Real
    "eurbrl": "EUR/BRL",   # Euro/Real
    "^spx":   "SPX",       # S&P 500
    "^ndx":   "NDX",       # Nasdaq 100
    "^dji":   "DJI",       # Dow Jones
    "gc.f":   "XAU/USD",   # Ouro
}
_GROUP_B = {
    "^ukx":   "FTSE",      # FTSE 100
    "^dax":   "GDAXI",     # DAX
    "sc.f":   "XBR/USD",   # Brent
    "cl.f":   "WTI/USD",   # WTI
    "si.f":   "XAG/USD",   # Prata
    "hg.f":   "HG1",       # Cobre
}
_CG_IDS = {"btc.v": "bitcoin", "eth.v": "ethereum"}


def _get_td_key() -> str:
    try:    return st.secrets.get("TWELVE_DATA_KEY", "")
    except: return os.environ.get("TWELVE_DATA_KEY", "")


def _make_quote(price, prev, high, low, last_date) -> dict:
    price = float(price or 0)
    prev  = float(prev  or price)
    if not price:
        return {}
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


def _fetch_td_batch(group: dict, key: str) -> dict:
    """Busca um grupo de até 8 símbolos via Twelve Data."""
    td_syms = list(group.values())
    sym_map = {v: k for k, v in group.items()}
    try:
        r = requests.get(
            TD_QUOTE.format(syms=",".join(td_syms), key=key),
            headers=_HDRS_JSON, timeout=20, verify=False,
        )
        if r.status_code != 200:
            logger.warning("Twelve Data HTTP %s", r.status_code)
            return {}
        data = r.json()
        if isinstance(data, dict) and data.get("code") == 429:
            logger.warning("Twelve Data rate limit: %s", data.get("message", ""))
            return {}
        out = {}
        # Resposta única (1 símbolo) ou múltipla (dict de dicts)
        if "symbol" in data:
            data = {data["symbol"]: data}
        for td_sym, q in data.items():
            if not isinstance(q, dict):
                continue
            if q.get("status") == "error":
                logger.warning("Twelve Data erro %s: %s", td_sym, q.get("message"))
                continue
            try:
                price     = float(q.get("close") or 0)
                prev      = float(q.get("previous_close") or price)
                high      = q.get("high")
                low       = q.get("low")
                dt_str    = q.get("datetime", "")
                last_date = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
                internal  = sym_map.get(td_sym)
                if internal and price:
                    out[internal] = _make_quote(price, prev, high, low, last_date)
            except Exception as e:
                logger.warning("Twelve Data parse %s: %s", td_sym, e)
        return out
    except Exception as e:
        logger.warning("Twelve Data batch: %s", e)
        return {}


@st.cache_data(ttl=130, show_spinner=False)
def _all_quotes_td(key: str) -> dict:
    """
    Busca os 13 símbolos Twelve Data em dois grupos sequenciais
    com 62s de intervalo — respeita o limite de 8 créditos/minuto.
    Cache de 130s: roda ~1x a cada 2 minutos.
    """
    out = {}
    # Grupo A: 7 símbolos
    a = _fetch_td_batch(_GROUP_A, key)
    out.update(a)
    if a:
        logger.warning("Twelve Data Grupo A: %d/%d", len(a), len(_GROUP_A))
    # Aguarda a janela de rate limit do Twelve Data zerar (60s + margem)
    time.sleep(62)
    # Grupo B: 6 símbolos
    b = _fetch_td_batch(_GROUP_B, key)
    out.update(b)
    if b:
        logger.warning("Twelve Data Grupo B: %d/%d", len(b), len(_GROUP_B))
    return out


@st.cache_data(ttl=65, show_spinner=False)
def _all_quotes_crypto() -> dict:
    """BTC e ETH via CoinGecko — gratuito."""
    try:
        r = requests.get(
            CG_PRICE.format(ids=",".join(_CG_IDS.values())),
            headers=_HDRS_JSON, timeout=10, verify=False,
        )
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
            chg_p = float(q.get("usd_24h_change") or 0)
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


def get_all_quotes(symbols: tuple) -> dict:
    """Cotações de todos os ativos: Twelve Data + CoinGecko."""
    key = _get_td_key()
    out = {}
    if key:
        out.update(_all_quotes_td(key))
    else:
        logger.warning("TWELVE_DATA_KEY não configurado nos Secrets do Streamlit")
    out.update(_all_quotes_crypto())
    for sym in symbols:
        if sym not in out:
            logger.warning("Cotação indisponível para %s", sym)
    return out


def get_quote(sym: str) -> dict:
    """Cotação individual — usa cache batch interno."""
    from settings import GLOBAL
    return get_all_quotes(tuple(s for s, _, _ in GLOBAL.values())).get(sym, {})


@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(sym: str, years: int = 5) -> pd.DataFrame:
    """Histórico de fechamento via Twelve Data ou CoinGecko."""
    key    = _get_td_key()
    td_sym = {**_GROUP_A, **_GROUP_B}.get(sym)

    # Twelve Data para índices/forex/commodities
    if key and td_sym:
        try:
            outputsize = min(years * 260, 5000)
            r = requests.get(
                TD_HIST.format(sym=td_sym, n=outputsize, key=key),
                headers=_HDRS_JSON, timeout=20, verify=False,
            )
            if r.status_code == 200:
                values = r.json().get("values", [])
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
                    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        except Exception as e:
            logger.warning("Twelve Data hist %s: %s", sym, e)

    # CoinGecko para cripto
    cg_id = _CG_IDS.get(sym)
    if cg_id:
        try:
            r = requests.get(
                CG_HIST.format(id=cg_id, days=years * 365),
                headers=_HDRS_JSON, timeout=20, verify=False,
            )
            if r.status_code == 200:
                rows = [{"data": datetime.fromtimestamp(p[0] / 1000), "valor": float(p[1])}
                        for p in r.json().get("prices", [])]
                if rows:
                    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        except Exception as e:
            logger.warning("CoinGecko hist %s: %s", sym, e)

    return pd.DataFrame(columns=["data", "valor"])
