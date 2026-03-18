"""
yahoo_fix.py  —  Drop-in replacement for the Yahoo Finance data functions.

Yahoo Finance now requires a crumb + authenticated cookie session for all
programmatic requests. Without it, every call returns 429 Too Many Requests,
even with a real User-Agent header.

HOW IT WORKS
────────────
1. Open a requests.Session and hit the Yahoo consent/cookie endpoint once.
2. Extract the `crumb` token from the crumb API.
3. Append ?crumb=<token> to every subsequent chart/quote request.
4. Cache the session+crumb in st.session_state so it survives Streamlit reruns
   without hitting the auth endpoint on every render.

USAGE
─────
Replace get_quote() and get_hist() in your app/data.py with the versions below,
or import them directly:

    from yahoo_fix import get_quote, get_hist
"""

import time
import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────
_COOKIE_URL = "https://fc.yahoo.com"
_CRUMB_URL  = "https://query1.finance.yahoo.com/v1/test/getcrumb"
_CHART_URL  = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
_SNAP_RANGE = "5d"

_HEADERS = {
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

# ── Session / crumb management ────────────────────────────────────────────────

def _build_session() -> tuple[requests.Session, str]:
    """
    Return (session, crumb).  Hits Yahoo once to get a valid cookie + crumb.
    Raises RuntimeError if auth fails so callers can handle gracefully.
    """
    s = requests.Session()
    s.headers.update(_HEADERS)

    # 1. Grab the initial cookie (Yahoo consent gate)
    try:
        s.get(_COOKIE_URL, timeout=10)
    except Exception:
        pass  # Cookie step can fail silently; crumb step will tell us for sure

    # 2. Fetch crumb  (returns plain text like  "AbCdEfGhIjK")
    r = s.get(_CRUMB_URL, timeout=10)
    if r.status_code != 200 or not r.text.strip():
        raise RuntimeError(f"Could not fetch Yahoo crumb (status {r.status_code})")

    crumb = r.text.strip()
    return s, crumb


def _get_yf_session() -> tuple[requests.Session, str]:
    """
    Return a cached (session, crumb) pair from st.session_state.
    Refreshes automatically when the crumb is stale or missing.
    """
    key = "_yf_session_cache"
    cache = st.session_state.get(key)

    # Refresh if older than 50 minutes (crumbs last ~1 hour)
    if cache and (time.time() - cache["ts"]) < 3000:
        return cache["session"], cache["crumb"]

    session, crumb = _build_session()
    st.session_state[key] = {"session": session, "crumb": crumb, "ts": time.time()}
    return session, crumb


# ── Public helpers ────────────────────────────────────────────────────────────

def _chart_request(sym: str, params: dict, retries: int = 3) -> dict | None:
    """
    Make an authenticated chart request.  Auto-refreshes session on 401/429.
    Returns the parsed JSON dict or None on failure.
    """
    for attempt in range(retries):
        try:
            session, crumb = _get_yf_session()
            p = {**params, "crumb": crumb}
            r = session.get(_CHART_URL.format(sym=sym), params=p, timeout=12)

            if r.status_code == 200:
                data = r.json()
                if data.get("chart", {}).get("result"):
                    return data

            # Stale crumb or rate-limit — force refresh on next attempt
            if r.status_code in (401, 429):
                st.session_state.pop("_yf_session_cache", None)
                time.sleep(2 ** attempt)          # 1s, 2s, 4s back-off
                continue

        except Exception:
            time.sleep(1)

    return None


# ── Drop-in replacements ──────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_quote(symbol: str) -> dict:
    """
    Fetch the latest quote for `symbol`.
    Returns a dict with keys: price, prev, chg_p, chg_v,
    market, is_live, is_extended, is_closed, close_date.
    Returns {} on failure.
    """
    data = _chart_request(symbol, {"interval": "1d", "range": _SNAP_RANGE})
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
            price = meta.get("previousClose") or meta.get("regularMarketPrice")
            prev  = meta.get("chartPreviousClose") or price
            ts_list    = result.get("timestamp", [])
            reg_ts     = meta.get("regularMarketTime")
            close_date = (
                datetime.fromtimestamp(ts_list[-1]).strftime("%d/%m/%Y") if ts_list
                else datetime.fromtimestamp(reg_ts).strftime("%d/%m/%Y") if reg_ts
                else None
            )

        if price is None:
            return {}

        chg_p = ((price - prev) / prev * 100) if (prev and prev != 0) else None
        chg_v = (price - prev) if prev else None
        return {
            "price": float(price), "prev": float(prev),
            "chg_p": chg_p, "chg_v": chg_v,
            "market": market_state,
            "is_live": is_live, "is_extended": is_extended,
            "is_closed": is_closed, "close_date": close_date,
        }
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def get_hist(symbol: str, years: int = 5) -> pd.DataFrame:
    """
    Fetch daily close history for `symbol` going back `years` years.
    Returns a DataFrame with columns [data, valor], or empty on failure.
    """
    data = _chart_request(symbol, {"interval": "1d", "range": f"{years}y"})
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
