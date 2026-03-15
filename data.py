"""
data.py — Camada de dados: BCB/SGS, IBGE/SIDRA, Yahoo Finance.
Todas as funções retornam DataFrames ou dicts prontos para consumo pelas páginas.
Nenhuma lógica de UI aqui.
"""
import re, time, warnings
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



# ── Yahoo Finance — sessão autenticada com cookie ─────────────────────────────

def _yf_session() -> requests.Session:
    """
    Cria sessão com cookie do Yahoo Finance para evitar rate limit em IPs de nuvem.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })
    try:
        session.get("https://fc.yahoo.com", timeout=5, verify=False)
        session.get("https://finance.yahoo.com", timeout=5, verify=False)
    except Exception:
        pass
    return session


def _fetch_quotes_http(symbols: list[str]) -> dict[str, dict]:
    """Busca cotações via Yahoo Finance v7 com sessão autenticada (batch)."""
    session  = _yf_session()
    syms_str = ",".join(symbols)
    for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
        try:
            r = session.get(
                f"{base}/v7/finance/quote?symbols={syms_str}"
                "&fields=regularMarketPrice,regularMarketPreviousClose,"
                "regularMarketDayHigh,regularMarketDayLow,regularMarketTime",
                timeout=15, verify=False,
            )
            if r.status_code != 200:
                continue
            results = r.json().get("quoteResponse", {}).get("result", [])
            if not results:
                continue
            out = {}
            for q in results:
                sym   = q.get("symbol", "")
                price = q.get("regularMarketPrice")
                if not price:
                    continue
                price = float(price)
                prev  = float(q["regularMarketPreviousClose"]) if q.get("regularMarketPreviousClose") else price
                rt    = q.get("regularMarketTime")
                last_date = datetime.fromtimestamp(rt).date() if rt else now_brt().date()
                is_today  = (last_date == now_brt().date())
                chg_p     = ((price - prev) / prev * 100) if prev else None
                out[sym] = {
                    "price": price, "prev": prev, "chg_p": chg_p,
                    "chg_v": (price - prev) if prev else None,
                    "day_high":  float(h) if (h := q.get("regularMarketDayHigh")) else None,
                    "day_low":   float(l) if (l := q.get("regularMarketDayLow"))  else None,
                    "market":    "REGULAR" if is_today else "CLOSED",
                    "is_live":   is_today, "is_extended": False, "is_closed": not is_today,
                    "close_date": last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None,
                }
            if out:
                return out
        except Exception as e:
            logger.warning("Yahoo v7 (%s): %s", base, e)
    return {}


def _fetch_quotes_yfinance(symbols: list[str]) -> dict[str, dict]:
    """Fallback: yfinance Tickers com sessão autenticada."""
    try:
        import yfinance as yf
        session = _yf_session()
        out     = {}
        tickers = yf.Tickers(" ".join(symbols), session=session)
        for sym in symbols:
            try:
                tk   = tickers.tickers[sym]
                hist = tk.history(period="5d", auto_adjust=True)
                if hist.empty:
                    continue
                price     = float(hist["Close"].iloc[-1])
                prev      = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
                last_date = pd.Timestamp(hist.index[-1]).tz_localize(None).date()
                is_today  = (last_date == now_brt().date())
                chg_p     = ((price - prev) / prev * 100) if prev else None
                out[sym] = {
                    "price": price, "prev": prev, "chg_p": chg_p,
                    "chg_v": (price - prev),
                    "day_high":  float(hist["High"].iloc[-1]),
                    "day_low":   float(hist["Low"].iloc[-1]),
                    "market":    "REGULAR" if is_today else "CLOSED",
                    "is_live":   is_today, "is_extended": False, "is_closed": not is_today,
                    "close_date": last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None,
                }
            except Exception:
                continue
        return out
    except Exception as e:
        logger.warning("yfinance Tickers: %s", e)
        return {}


@st.cache_data(ttl=TTL_MERCADOS, show_spinner=False)
def get_all_quotes(symbols: tuple) -> dict:
    """Cotações em batch com fallback. Usa tuple para ser hashável pelo cache."""
    syms   = list(symbols)
    result = _fetch_quotes_http(syms)
    if not result:
        logger.warning("Yahoo HTTP falhou, tentando yfinance com sessão...")
        result = _fetch_quotes_yfinance(syms)
    for sym in symbols:
        if sym not in result:
            logger.warning("Yahoo Finance: cotação indisponível para %s", sym)
    return result


def get_quote(sym: str) -> dict:
    """Cotação individual — usa o cache batch internamente."""
    from settings import GLOBAL
    all_syms = tuple(s for s, _, _ in GLOBAL.values())
    return get_all_quotes(all_syms).get(sym, {})


@st.cache_data(ttl=TTL_HIST, show_spinner=False)
def get_hist(sym: str, years: int = 5) -> pd.DataFrame:
    """Histórico de fechamento com sessão autenticada."""
    session = _yf_session()
    try:
        import yfinance as yf
        tk  = yf.Ticker(sym, session=session)
        df  = tk.history(period=f"{years}y", auto_adjust=True)
        if not df.empty:
            result = pd.DataFrame({"data": df.index, "valor": df["Close"].values.flatten()})
            result["data"] = pd.to_datetime(result["data"]).dt.tz_localize(None)
            return result.dropna().reset_index(drop=True)
    except Exception as e:
        logger.warning("yfinance hist %s: %s", sym, e)
    try:
        r = session.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range={years}y",
            timeout=15, verify=False,
        )
        res = r.json()["chart"]["result"][0]
        df  = pd.DataFrame({
            "data":  pd.to_datetime(res["timestamp"], unit="s"),
            "valor": res["indicators"]["quote"][0]["close"],
        })
        return df.dropna().reset_index(drop=True)
    except Exception as e:
        logger.warning("Yahoo HTTP hist %s: %s", sym, e)
        return pd.DataFrame(columns=["data", "valor"])
