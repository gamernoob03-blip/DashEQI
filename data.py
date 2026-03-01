"""
data.py — Camada de dados (BCB/SGS + Yahoo Finance)
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

# Silencia warnings de SSL (BCB usa certificado que falha em alguns ambientes)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS")

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
BCB_BASE   = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
YAHOO_SNAP = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
YAHOO_HIST = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range={y}y"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

SGS = {
    "Selic":       (432,   "% a.a.",  "Mensal",     "line"),
    "IPCA":        (433,   "% mês",   "Mensal",     "bar"),
    "IBC-Br":      (24363, "índice",  "Mensal",     "line"),
    "Dólar PTAX":  (1,     "R$",      "Diário",     "line"),
    "PIB":         (4380,  "% trim.", "Trimestral", "bar"),
    "Desemprego":  (24369, "%",       "Trimestral", "line"),
    "IGP-M":       (189,   "% mês",   "Mensal",     "bar"),
    "IPCA-15":     (7478,  "% mês",   "Mensal",     "bar"),
    "Exportações": (2257,  "US$ mi",  "Mensal",     "bar"),
    "Importações": (2258,  "US$ mi",  "Mensal",     "bar"),
    "Dívida/PIB":  (4513,  "%",       "Mensal",     "line"),
}

GLOBAL = {
    "IBOVESPA":        ("^BVSP",    "pts",    False),
    "Dólar (USD/BRL)": ("USDBRL=X", "R$",     True),
    "Euro (EUR/BRL)":  ("EURBRL=X", "R$",     True),
    "S&P 500":         ("^GSPC",    "pts",    False),
    "Nasdaq 100":      ("^NDX",     "pts",    False),
    "Dow Jones":       ("^DJI",     "pts",    False),
    "FTSE 100":        ("^FTSE",    "pts",    False),
    "DAX":             ("^GDAXI",   "pts",    False),
    "Petróleo Brent":  ("BZ=F",     "US$",    True),
    "Petróleo WTI":    ("CL=F",     "US$",    True),
    "Ouro":            ("GC=F",     "US$",    False),
    "Prata":           ("SI=F",     "US$",    False),
    "Cobre":           ("HG=F",     "US$/lb", True),
    "Bitcoin":         ("BTC-USD",  "US$",    False),
    "Ethereum":        ("ETH-USD",  "US$",    False),
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

# ─── YAHOO FINANCE ────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def get_quote(symbol: str) -> dict:
    try:
        r = requests.get(YAHOO_SNAP.format(sym=symbol), headers=HEADERS, timeout=10)
        r.raise_for_status()
        data   = r.json()
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
            if ts_list:
                close_date = datetime.fromtimestamp(ts_list[-1]).strftime("%d/%m/%Y")
            else:
                reg_ts     = meta.get("regularMarketTime")
                close_date = datetime.fromtimestamp(reg_ts).strftime("%d/%m/%Y") if reg_ts else None

        if price is None:
            return {}

        chg_p = ((price - prev) / prev * 100) if (prev and prev != 0) else None
        chg_v = (price - prev) if prev else None
        return {
            "price": price, "prev": prev, "chg_p": chg_p, "chg_v": chg_v,
            "market": market_state, "is_live": is_live,
            "is_extended": is_extended, "is_closed": is_closed, "close_date": close_date,
        }
    except Exception:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(symbol: str, years: int = 5) -> pd.DataFrame:
    try:
        r = requests.get(YAHOO_HIST.format(sym=symbol, y=years), headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        res  = data["chart"]["result"][0]
        ts   = res["timestamp"]
        vals = res["indicators"]["quote"][0]["close"]
        df   = pd.DataFrame({"data": pd.to_datetime(ts, unit="s"), "valor": vals})
        return df.dropna().reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["data", "valor"])
