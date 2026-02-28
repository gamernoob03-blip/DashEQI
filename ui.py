from datetime import datetime
"""
ui.py — Componentes de interface reutilizáveis
KPI cards, fábricas de gráficos Plotly e helpers de formatação.
"""

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
    """Converte hex #RRGGBB para rgba(r,g,b,a)."""
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


# ─── KPI CARD ─────────────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, chg_p=None, sub: str = "", invert: bool = False, d: dict = None):
    """
    Renderiza um card KPI via st.metric nativo do Streamlit.

    Parâmetros:
        label   — título do indicador
        value   — valor principal formatado (string)
        chg_p   — variação percentual (float ou None)
        sub     — texto de rodapé (ex: "Ref: Jan/25")
        invert  — inverte a cor do delta (útil para câmbio: queda = bom)
        d       — dict retornado por get_quote() para exibir ribbon de mercado
    """
    is_closed   = d.get("is_closed",   False) if d else False
    is_extended = d.get("is_extended", False) if d else False
    close_date  = d.get("close_date",  None)  if d else None

    # ── Ribbon de status ──────────────────────────────────────────────────
    if is_closed and close_date:
        ribbon_txt   = f"Fechamento {close_date}"
        ribbon_color = "#92400e"
        ribbon_bg    = "#fef3c7"
    elif is_closed:
        ribbon_txt   = "Último fechamento"
        ribbon_color = "#92400e"
        ribbon_bg    = "#fef3c7"
    elif is_extended:
        mstate       = d.get("market", "") if d else ""
        ribbon_txt   = "Pré-mercado" if "PRE" in mstate else "Pós-mercado"
        ribbon_color = "#1d4ed8"
        ribbon_bg    = "#eff6ff"
    else:
        ribbon_txt = ribbon_color = ribbon_bg = None

    ribbon_html = ""
    if ribbon_txt:
        ribbon_html = (
            f'<div style="position:absolute;top:0;right:0;background:{ribbon_bg};'
            f'border-bottom-left-radius:8px;color:{ribbon_color};font-size:9px;'
            f'font-weight:600;padding:3px 9px;white-space:nowrap;'
            f'font-family:Inter,sans-serif">{ribbon_txt}</div>'
        )

    # ── Delta ─────────────────────────────────────────────────────────────
    if chg_p is not None:
        up          = (chg_p >= 0) if not invert else (chg_p < 0)
        delta_color = "#16a34a" if up else "#dc2626"
        arrow       = "▲" if chg_p >= 0 else "▼"
        delta_html  = (
            f'<p style="font-size:12px;font-weight:600;color:{delta_color};'
            f'margin:2px 0 0 0;font-family:Inter,sans-serif">'
            f'{arrow} {abs(chg_p):.2f}%</p>'
        )
    else:
        delta_html = '<p style="font-size:12px;color:#9ca3af;margin:2px 0 0 0">—</p>'

    # ── Sub ───────────────────────────────────────────────────────────────
    sub_html = (
        f'<p style="font-size:10px;color:#9ca3af;margin:1px 0 0 0;'
        f'font-family:Inter,sans-serif">{sub}</p>'
        if sub else ""
    )

    # ── Card completo ─────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="
            background:#ffffff;
            border:1px solid #e2e5e9;
            border-radius:12px;
            padding:18px 16px 16px;
            text-align:center;
            min-height:116px;
            display:flex;
            flex-direction:column;
            justify-content:center;
            align-items:center;
            gap:2px;
            box-shadow:0 1px 3px rgba(0,0,0,0.05);
            position:relative;
            overflow:hidden;
            font-family:Inter,sans-serif;
        ">
            {ribbon_html}
            <p style="font-size:9px;font-weight:700;color:#6b7280;
                text-transform:uppercase;letter-spacing:1.5px;margin:4px 0 0 0">
                {label}
            </p>
            <p style="font-size:20px;font-weight:700;color:#111827;
                line-height:1.2;margin:4px 0 0 0">
                {value}
            </p>
            {delta_html}
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    hoverlabel=dict(bgcolor="#1a2035", font_size=12, font_color="#e2e8f0", bordercolor="#1a2035"),
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
    """Ajusta eixos para eliminar espaço desnecessário."""
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


# ─── GRÁFICO DE LINHA ─────────────────────────────────────────────────────────
def line_fig(
    df,
    title:       str,
    color:       str   = "#1a2035",
    fill:        bool  = True,
    suffix:      str   = "",
    height:      int   = 260,
    interactive: bool  = False,
) -> go.Figure:
    """Cria gráfico de linha Plotly com área preenchida opcional."""
    base = _PLOT_INTER if interactive else _PLOT_BASE
    fig  = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_rgba(color, 0.07),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**base, title=title, height=height)
    if not interactive:
        fig = _apply_range(fig, df, suffix)
    return fig


# ─── GRÁFICO DE BARRAS ────────────────────────────────────────────────────────
def bar_fig(
    df,
    title:       str,
    suffix:      str  = "",
    height:      int  = 260,
    interactive: bool = False,
) -> go.Figure:
    """Cria gráfico de barras colorido (verde = positivo, vermelho = negativo)."""
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


# ─── TÍTULOS DE SEÇÃO ─────────────────────────────────────────────────────────
def section_title(text: str, badge: str = "", badge_cls: str = "badge-live"):
    """Renderiza cabeçalho de seção com badge opcional."""
    badge_html = (
        f'<span class="{badge_cls}">{badge}</span>' if badge else ""
    )
    st.markdown(
        f'<div class="sec-title">{text} {badge_html}</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = ""):
    """Renderiza cabeçalho fixo de página."""
    sub_html = subtitle if subtitle else datetime.now().strftime("%d/%m/%Y %H:%M")  # noqa: F821
    st.markdown(
        f"<div class='page-top'>"
        f"<h1>{title}</h1>"
        f"<div class='ts'>{sub_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
