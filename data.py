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



# ── Stooq — cotações e histórico ──────────────────────────────────────────────
# Stooq é gratuito, sem chave de API, sem bloqueio de IP de nuvem.
# URL de cotação:  https://stooq.com/q/l/?s=SYMBOL&f=sd2t2ohlcv&h&e=csv
# URL de histórico: https://stooq.com/q/d/l/?s=SYMBOL&i=d

STOOQ_QUOTE = "https://stooq.com/q/l/?s={s}&f=sd2t2ohlcv&h&e=csv"
STOOQ_HIST  = "https://stooq.com/q/d/l/?s={s}&i=d"

_STOOQ_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def _parse_stooq_quote(sym: str, row: dict) -> dict | None:
    """Converte uma linha CSV do Stooq para o formato padrão de cotação."""
    try:
        price = float(row.get("Close") or row.get("close") or 0)
        if not price:
            return None
        prev  = float(row.get("Open")  or row.get("open")  or price)
        high  = float(row.get("High")  or row.get("high")  or price)
        low   = float(row.get("Low")   or row.get("low")   or price)
        date_str = row.get("Date") or row.get("date") or ""
        try:
            last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            last_date = now_brt().date()
        is_today = (last_date == now_brt().date())
        chg_p    = ((price - prev) / prev * 100) if prev else None
        return {
            "price":      price, "prev": prev,
            "chg_p":      chg_p, "chg_v": (price - prev) if prev else None,
            "day_high":   high,  "day_low": low,
            "market":     "REGULAR" if is_today else "CLOSED",
            "is_live":    is_today, "is_extended": False, "is_closed": not is_today,
            "close_date": last_date.strftime("%d/%m/%Y") if (last_date and not is_today) else None,
        }
    except Exception:
        return None


@st.cache_data(ttl=TTL_MERCADOS, show_spinner=False)
def get_all_quotes(symbols: tuple) -> dict:
    """
    Busca cotações de todos os símbolos via Stooq (uma requisição por símbolo,
    mas Stooq não tem rate limit agressivo como o Yahoo Finance).
    """
    out = {}
    for sym in symbols:
        try:
            r = requests.get(STOOQ_QUOTE.format(s=sym),
                             headers=_STOOQ_HDRS, timeout=10, verify=False)
            if r.status_code != 200:
                logger.warning("Stooq: HTTP %s para %s", r.status_code, sym)
                continue
            lines = r.text.strip().splitlines()
            if len(lines) < 2:
                logger.warning("Stooq: resposta vazia para %s", sym)
                continue
            headers = [h.strip() for h in lines[0].split(",")]
            values  = [v.strip() for v in lines[1].split(",")]
            row     = dict(zip(headers, values))
            parsed  = _parse_stooq_quote(sym, row)
            if parsed:
                out[sym] = parsed
            else:
                logger.warning("Stooq: cotação indisponível para %s — %s", sym, row)
        except Exception as e:
            logger.warning("Stooq: erro para %s — %s", sym, e)
    return out


def get_quote(sym: str) -> dict:
    """Cotação individual via cache batch do Stooq."""
    from settings import GLOBAL
    all_syms = tuple(s for s, _, _ in GLOBAL.values())
    return get_all_quotes(all_syms).get(sym, {})


@st.cache_data(ttl=TTL_HIST, show_spinner=False)
def get_hist(sym: str, years: int = 5) -> pd.DataFrame:
    """Histórico de fechamento via Stooq."""
    try:
        r = requests.get(STOOQ_HIST.format(s=sym),
                         headers=_STOOQ_HDRS, timeout=20, verify=False)
        if r.status_code != 200:
            logger.warning("Stooq hist: HTTP %s para %s", r.status_code, sym)
            return pd.DataFrame(columns=["data", "valor"])
        lines = r.text.strip().splitlines()
        if len(lines) < 2:
            return pd.DataFrame(columns=["data", "valor"])
        headers = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            vals = [v.strip() for v in line.split(",")]
            row  = dict(zip(headers, vals))
            try:
                dt    = datetime.strptime(row.get("Date",""), "%Y-%m-%d")
                close = float(row.get("Close", 0))
                if close:
                    rows.append({"data": dt, "valor": close})
            except Exception:
                continue
        if not rows:
            return pd.DataFrame(columns=["data", "valor"])
        df = pd.DataFrame(rows).sort_values("data").reset_index(drop=True)
        # Filtra pelo período solicitado
        cutoff = datetime.now() - timedelta(days=years * 365 + 5)
        df = df[df["data"] >= cutoff].reset_index(drop=True)
        return df
    except Exception as e:
        logger.warning("Stooq hist %s: %s", sym, e)
        return pd.DataFrame(columns=["data", "valor"])
