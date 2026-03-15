"""
components.py — Widgets reutilizáveis de UI e CSS global.
Todos dependem de st.*; nenhuma lógica de dados ou cálculo aqui.
"""
import streamlit as st
from datetime import datetime
from settings import logger, TZ_BRT, NAV, NAV_SLUGS


def now_brt() -> datetime:
    """Retorna datetime atual no fuso de Brasília."""
    return datetime.now(TZ_BRT)


# ── CSS global ────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*,[class*="css"]{font-family:'Inter',sans-serif!important}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f0f2f5!important}
.main .block-container{padding-top:0!important;padding-bottom:2rem;max-width:1400px}
footer,#MainMenu,header{visibility:hidden!important}
[data-testid="stToolbar"]{display:none!important}
[data-testid="stCaptionContainer"] p{font-size:10px!important;color:#9ca3af!important;text-align:center!important;margin:0!important}
.sec-title{font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin:20px 0 12px;padding-bottom:8px;border-bottom:1px solid #e2e5e9;display:flex;align-items:center;gap:8px}
.badge-live{display:inline-block;background:#f0fdf4;border:1px solid #bbf7d0;color:#16a34a;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px}
.badge-daily{display:inline-block;background:#f5f3ff;border:1px solid #ddd6fe;color:#7c3aed;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px}
.main .stButton>button{background:#1a2035!important;color:#fff!important;border:none!important;border-radius:7px!important;font-weight:600!important;font-size:13px!important;padding:8px 18px!important}
.main .stButton>button:hover{background:#2d3a56!important}
section[data-testid="stSidebar"]{min-width:260px!important;max-width:260px!important;width:260px!important}
[data-testid="stSidebarResizer"]{display:none!important}
[data-testid="stSidebarCollapseButton"]{display:none!important}
[data-testid="stSidebarCollapsedControl"]{display:none!important}
section[data-testid="stSidebar"] .stButton button{text-align:left!important;padding:8px 14px 8px 38px!important;min-height:0!important;height:36px!important;line-height:1.2!important;font-size:13px!important;font-weight:500!important;border-radius:8px!important;position:relative!important}
section[data-testid="stSidebar"] .stButton button::before{content:""!important;position:absolute!important;left:12px!important;top:50%!important;transform:translateY(-50%)!important;width:16px!important;height:16px!important;background-repeat:no-repeat!important;background-size:16px 16px!important;background-position:center!important}
section[data-testid="stSidebar"] .stButton button[kind="primary"]{background:#004031!important}
section[data-testid="stSidebar"] .stButton button[kind="primary"]:hover{background:#005a45!important}
.nav-marker{display:none!important;height:0!important;margin:0!important;padding:0!important}
div:has(.nav-inicio) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0zIDkuNUwxMiAzbDkgNi41VjIwYTEgMSAwIDAgMS0xIDFINGExIDEgMCAwIDEtMS0xVjkuNXoiLz48cGF0aCBkPSJNOSAyMVYxMmg2djkiLz48L3N2Zz4=")!important}
div:has(.nav-inicio) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0zIDkuNUwxMiAzbDkgNi41VjIwYTEgMSAwIDAgMS0xIDFINGExIDEgMCAwIDEtMS0xVjkuNXoiLz48cGF0aCBkPSJNOSAyMVYxMmg2djkiLz48L3N2Zz4=")!important}
div:has(.nav-ipca) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSIxOSIgeTE9IjUiIHgyPSI1IiB5Mj0iMTkiLz48Y2lyY2xlIGN4PSI2LjUiIGN5PSI2LjUiIHI9IjIuNSIvPjxjaXJjbGUgY3g9IjE3LjUiIGN5PSIxNy41IiByPSIyLjUiLz48L3N2Zz4=")!important}
div:has(.nav-ipca) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSIxOSIgeTE9IjUiIHgyPSI1IiB5Mj0iMTkiLz48Y2lyY2xlIGN4PSI2LjUiIGN5PSI2LjUiIHI9IjIuNSIvPjxjaXJjbGUgY3g9IjE3LjUiIGN5PSIxNy41IiByPSIyLjUiLz48L3N2Zz4=")!important}
div:has(.nav-mercados) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIyIDcgMTMuNSAxNS41IDguNSAxMC41IDIgMTciLz48cG9seWxpbmUgcG9pbnRzPSIxNiA3IDIyIDcgMjIgMTMiLz48L3N2Zz4=")!important}
div:has(.nav-mercados) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIyIDcgMTMuNSAxNS41IDguNSAxMC41IDIgMTciLz48cG9seWxpbmUgcG9pbnRzPSIxNiA3IDIyIDcgMjIgMTMiLz48L3N2Zz4=")!important}
div:has(.nav-graficos) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjEyIiB3aWR0aD0iNCIgaGVpZ2h0PSI5Ii8+PHJlY3QgeD0iMTAiIHk9IjciIHdpZHRoPSI0IiBoZWlnaHQ9IjE0Ii8+PHJlY3QgeD0iMTciIHk9IjMiIHdpZHRoPSI0IiBoZWlnaHQ9IjE4Ii8+PC9zdmc+")!important}
div:has(.nav-graficos) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjEyIiB3aWR0aD0iNCIgaGVpZ2h0PSI5Ii8+PHJlY3QgeD0iMTAiIHk9IjciIHdpZHRoPSI0IiBoZWlnaHQ9IjE0Ii8+PHJlY3QgeD0iMTciIHk9IjMiIHdpZHRoPSI0IiBoZWlnaHQ9IjE4Ii8+PC9zdmc+")!important}
div:has(.nav-exportar) + div button[kind="secondary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMSAxNXY0YTIgMiAwIDAgMS0yIDJINWEyIDIgMCAwIDEtMi0ydi00Ii8+PHBvbHlsaW5lIHBvaW50cz0iNyAxMCAxMiAxNSAxNyAxMCIvPjxsaW5lIHgxPSIxMiIgeTE9IjE1IiB4Mj0iMTIiIHkyPSIzIi8+PC9zdmc+")!important}
div:has(.nav-exportar) + div button[kind="primary"]::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMS44IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMSAxNXY0YTIgMiAwIDAgMS0yIDJINWEyIDIgMCAwIDEtMi0ydi00Ii8+PHBvbHlsaW5lIHBvaW50cz0iNyAxMCAxMiAxNSAxNyAxMCIvPjxsaW5lIHgxPSIxMiIgeTE9IjE1IiB4Mj0iMTIiIHkyPSIzIi8+PC9zdmc+")!important}
</style>
"""


# ── Helpers de formatação ─────────────────────────────────────────────────────

def fmt(v, dec: int = 2) -> str:
    """Formata número no padrão brasileiro (ponto milhar, vírgula decimal)."""
    if v is None:
        return "—"
    s = f"{v:,.{dec}f}".split(".")
    return f"{s[0].replace(',','.')},{s[1]}" if len(s) > 1 else s[0].replace(",", ".")


# ── Widgets de UI ─────────────────────────────────────────────────────────────

def inject_css() -> None:
    """Injeta o CSS global no app. Chamar uma vez no app.py."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def page_header(title: str) -> None:
    """Cabeçalho padronizado de página (sem renderização visível por enquanto)."""
    _ = now_brt().strftime("%d/%m/%Y %H:%M")


def sec_title(txt: str, badge: str = "", cls: str = "badge-live") -> None:
    """Título de seção com badge opcional."""
    b = f'<span class="{cls}">{badge}</span>' if badge else ""
    st.markdown(f'<div class="sec-title">{txt} {b}</div>', unsafe_allow_html=True)
def kpi_card(label: str, value: str, chg_p=None, sub: str = "",
             invert: bool = False, d: dict = None, raw_delta=None) -> None:
    """Card de KPI padronizado com valor, variação e badge de referência."""
    d  = d or {}
    cd = d.get("close_date")
    if chg_p is not None:
        up    = chg_p >= 0
        arrow = "▲" if up else "▼"
        color = "#16a34a" if up else "#dc2626"
        display_val = fmt(raw_delta) if raw_delta is not None else f"{abs(chg_p):.2f}%"
        delta_html  = (f"<div style='color:{color};font-size:12px;font-weight:600;"
                       f"margin-top:4px'>{arrow} {display_val}</div>")
    else:
        delta_html = ""
    sub_html    = (f"<div style='font-size:10px;color:#9ca3af;margin-top:6px'>{sub}</div>"
                   if sub else "")
    banner_html = (
        f"<div style='background:#fef9c3;border:1px solid #fde047;border-radius:6px;"
        f"font-size:9px;font-weight:600;color:#854d0e;padding:3px 8px;margin-top:8px;"
        f"text-align:center'>⚠ Ref. {cd}</div>"
    ) if cd else ""
    st.markdown(
        "<div style='background:#ffffff;border:1px solid #e2e5e9;border-radius:12px;"
        "padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.05);text-align:center'>"
        f"<div style='font-size:10px;font-weight:700;color:#6b7280;"
        f"text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px'>{label}</div>"
        f"<div style='font-size:22px;font-weight:700;color:#111827'>{value}</div>"
        f"{delta_html}{sub_html}{banner_html}</div>",
        unsafe_allow_html=True,
    )
def stale_banner(df, label: str = "") -> None:
    """
    Exibe aviso amarelo se o DataFrame veio do cache stale (API indisponível).
    O atributo df.attrs['stale_since'] é setado por data._build_with_fallback.
    """
    from datetime import datetime
    stale_since = df.attrs.get("stale_since") if hasattr(df, "attrs") else None
    if stale_since is None:
        return
    delta = datetime.now() - stale_since
    horas = int(delta.total_seconds() // 3600)
    mins  = int((delta.total_seconds() % 3600) // 60)
    tempo = f"{horas}h {mins}min" if horas else f"{mins}min"
    nome  = f" — {label}" if label else ""
    st.warning(f"⚠️ **API BCB temporariamente indisponível{nome}.** Exibindo último dado disponível (obtido há {tempo}).")


def render_chart(fig, filename: str = "grafico", static: bool = False) -> None:
    """
    Renderiza uma figura Plotly com configuração padronizada.

    static=False (padrão) — gráfico dinâmico:
        rangeslider, botões 6M/1A/2A/5A/Tudo, zoom, pan, download PNG.
        Usado em: Monitor Inflação, Mercados, Gráficos, Exportar.

    static=True — gráfico estático:
        sem controles, sem barra de ferramentas. Leve e limpo.
        Usado em: Início (visão rápida) e snapshots de um único período.
    """
    from settings import CHART_CFG
    if static:
        cfg = {"displayModeBar": False, "staticPlot": False, "responsive": True}
    else:
        cfg = {**CHART_CFG, "toImageButtonOptions": {**CHART_CFG["toImageButtonOptions"], "filename": filename}}
    st.plotly_chart(fig, use_container_width=True, config=cfg)
