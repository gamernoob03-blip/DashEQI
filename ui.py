"""
ui.py — Componentes de interface reutilizáveis
KPI cards (via st.metric nativo), gráficos Plotly e helpers de formatação.
"""

from datetime import datetime
import plotly.graph_objects as go
import streamlit as st

# ─── FORMATAÇÃO ──────────────────────────────────────────────────────────────
def fmt(v, dec: int = 2) -> str:
    """Formata número para padrão pt-BR (ponto em milhar, vírgula decimal)."""
    if v is None:
        return "—"
    s       = f"{v:,.{dec}f}"
    parts   = s.split(".")
    integer = parts[0].replace(",", ".")
    decimal = parts[1] if len(parts) > 1 else ""
    return f"{integer},{decimal}" if decimal else integer


def hex_rgba(h: str, a: float = 0.08) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


# ─── KPI CARD ─────────────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, chg_p=None, sub: str = "",
             invert: bool = False, d: dict = None):
    """
    Renderiza KPI usando st.metric nativo (funciona em todas as versões/ambientes).
    O CSS global em app.py customiza a aparência do metric.
    """
    d = d or {}
    is_closed   = d.get("is_closed",   False)
    is_extended = d.get("is_extended", False)
    close_date  = d.get("close_date",  None)
    market      = d.get("market",      "")

    # ── Ribbon de status (acima do metric) ───────────────────────────────
    if is_closed and close_date:
        st.caption(f"🕐 Fechamento {close_date}")
    elif is_closed:
        st.caption("🕐 Último fechamento")
    elif is_extended:
        label_ext = "Pré-mercado" if "PRE" in market else "Pós-mercado"
        st.caption(f"⏳ {label_ext}")

    # ── Delta formatado ───────────────────────────────────────────────────
    delta_str = None
    if chg_p is not None:
        arrow     = "▲" if chg_p >= 0 else "▼"
        delta_str = f"{arrow} {abs(chg_p):.2f}%"

    # st.metric lida com delta internamente;
    # usamos delta_color="off" e controlamos a cor via CSS
    st.metric(
        label=label,
        value=value,
        delta=delta_str,
        delta_color="off",          # desliga cor automática; CSS cuida disso
        help=sub if sub else None,
    )

    # Sub-texto abaixo do metric
    if sub:
        st.caption(sub)


# ─── PLOTLY — configurações base ─────────────────────────────────────────────
_PLOT_BASE = dict(
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    font_color="#6b7280",
    font_family="Inter",
    margin=dict(l=0, r=4, t=36, b=0),
    xaxis=dict(
        gridcolor="#f1f5f9", showline=False,
        tickfont=dict(size=10, color="#9ca3af"),
        zeroline=False, fixedrange=True,
    ),
    yaxis=dict(
        gridcolor="#f1f5f9", showline=False,
        tickfont=dict(size=10, color="#9ca3af"),
        zeroline=False, fixedrange=True,
    ),
    title_font=dict(color="#374151", size=12, family="Inter"),
    hoverlabel=dict(
        bgcolor="#1a2035", font_size=12,
        font_color="#e2e8f0", bordercolor="#1a2035",
    ),
    dragmode=False,
)

_PLOT_INTER = {
    **_PLOT_BASE,
    "xaxis":    {**_PLOT_BASE["xaxis"],  "fixedrange": False},
    "yaxis":    {**_PLOT_BASE["yaxis"],  "fixedrange": False},
    "dragmode": "pan",
}

CHART_CFG = {"displayModeBar": False, "staticPlot": False, "scrollZoom": False}


def _apply_range(fig, df, suffix: str = "", pad_pct: float = 0.08):
    if df.empty:
        return fig
    y_min, y_max = df["valor"].min(), df["valor"].max()
    y_pad = (y_max - y_min) * pad_pct if (y_max - y_min) > 0 else abs(y_max) * 0.1 or 1
    x_min, x_max = df["data"].min(), df["data"].max()
    x_pad = (x_max - x_min) * 0.02
    fig.update_xaxes(range=[x_min - x_pad, x_max + x_pad])
    fig.update_yaxes(
        range=[y_min - y_pad, y_max + y_pad],
        tickformat=".2f",
        ticksuffix=suffix.strip() if suffix.strip() else "",
    )
    return fig


def line_fig(df, title, color="#1a2035", fill=True, suffix="",
             height=260, interactive=False):
    base = _PLOT_INTER if interactive else _PLOT_BASE
    fig  = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"], mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_rgba(color, 0.07),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**base, title=title, height=height)
    if not interactive:
        fig = _apply_range(fig, df, suffix)
    return fig


def bar_fig(df, title, suffix="", height=260, interactive=False):
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in df["valor"]]
    base   = _PLOT_INTER if interactive else _PLOT_BASE
    fig    = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=colors, marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**base, title=title, height=height)
    if not interactive:
        fig = _apply_range(fig, df, suffix, pad_pct=0.15)
    return fig


def section_title(text: str, badge: str = "", badge_cls: str = "badge-live"):
    badge_html = f'<span class="{badge_cls}">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="sec-title">{text} {badge_html}</div>',
        unsafe_allow_html=True,
    )
