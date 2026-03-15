"""
charts.py — Todas as figuras Plotly e helpers de visualização.
Nenhuma chamada a st.* aqui — só retorna go.Figure prontos para renderizar.
"""
import pandas as pd
import plotly.graph_objects as go

from config import IPCA_GRUPOS_IDS, IPCA_GRUPOS_CORES, BCB_TOLE

# ── IDs dos grupos para filtro ────────────────────────────────────────────────
_GRUPO_IDS = [g.strip() for g in IPCA_GRUPOS_IDS.split(",")]

# ── Layout base ───────────────────────────────────────────────────────────────
_B = dict(
    paper_bgcolor="#fff", plot_bgcolor="#fff",
    font_color="#6b7280", font_family="Inter",
    margin=dict(l=52, r=16, t=40, b=36),
    xaxis=dict(gridcolor="#f1f5f9", showline=False,
               tickfont=dict(size=10, color="#9ca3af"),
               zeroline=False, fixedrange=True),
    yaxis=dict(gridcolor="#f1f5f9", showline=False,
               tickfont=dict(size=10, color="#9ca3af"),
               zeroline=False, fixedrange=True),
    title_font=dict(color="#374151", size=12, family="Inter"),
    hoverlabel=dict(bgcolor="#1a2035", font_size=12, font_color="#e2e8f0"),
    dragmode=False,
)

# _I: layout interativo — Y e X livres para zoom/pan
_I = {
    **_B,
    "xaxis": {**_B["xaxis"], "fixedrange": False},
    "yaxis": {**_B["yaxis"], "fixedrange": False},
    "dragmode": "zoom",
}

# ── Range selector ────────────────────────────────────────────────────────────
_RS_BUTTONS = [
    dict(count=6,  label="6M",  step="month", stepmode="backward"),
    dict(count=1,  label="1A",  step="year",  stepmode="backward"),
    dict(count=2,  label="2A",  step="year",  stepmode="backward"),
    dict(count=5,  label="5A",  step="year",  stepmode="backward"),
    dict(step="all", label="Tudo"),
]
_RS_STYLE = dict(
    bgcolor="#f8fafc", bordercolor="#e2e5e9", borderwidth=1,
    font=dict(size=11, color="#374151"), activecolor="#e6f0ed",
    x=1.0, xanchor="right", y=1.0, yanchor="bottom",
    buttons=_RS_BUTTONS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def hex_rgba(h: str, a: float = 0.08) -> str:
    """Converte cor hex para rgba com transparência."""
    h = h.lstrip("#")
    return f"rgba({int(h[:2],16)},{int(h[2:4],16)},{int(h[4:],16)},{a})"


def _y_range_for_window(df: pd.DataFrame, x_min, x_max,
                         value_col: str = "valor", pad: float = 0.15,
                         extra_min=None, extra_max=None) -> list:
    """
    Calcula range Y baseado apenas nos pontos visíveis na janela [x_min, x_max].
    Garante que valores extras (ex: linhas de meta) fiquem dentro do range.
    """
    mask    = (df["data"] >= pd.Timestamp(x_min)) & (df["data"] <= pd.Timestamp(x_max))
    visible = df[mask][value_col].dropna()
    if visible.empty:
        visible = df[value_col].dropna()
    mn, mx = float(visible.min()), float(visible.max())
    if extra_min is not None: mn = min(mn, float(extra_min))
    if extra_max is not None: mx = max(mx, float(extra_max))
    gap = (mx - mn) * pad if mx != mn else abs(mx) * 0.2 or 1
    return [mn - gap, mx + gap]


def _rng(fig: go.Figure, df: pd.DataFrame, sfx: str = "", pad: float = 0.08) -> go.Figure:
    """Aplica range X e Y iniciais para gráficos estáticos (não interativos)."""
    if df.empty:
        return fig
    mn, mx = df["valor"].min(), df["valor"].max()
    yd = (mx - mn) * pad if mx != mn else abs(mx) * 0.1 or 1
    xd = (df["data"].max() - df["data"].min()) * 0.02
    fig.update_xaxes(range=[df["data"].min() - xd, df["data"].max() + xd])
    fig.update_yaxes(range=[mn - yd, mx + yd], tickformat=".2f", ticksuffix=sfx.strip())
    return fig


def _add_rangeslider(fig: go.Figure, height: int, extra_top: int = 32) -> go.Figure:
    """Adiciona rangeslider + rangeselector e libera o eixo Y para zoom."""
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.05, bgcolor="#f1f5f9"),
        rangeselector=_RS_STYLE,
    )
    fig.update_yaxes(fixedrange=False)
    fig.update_layout(height=height + 40, margin=dict(t=40 + extra_top))
    return fig


# ── Gráficos genéricos ────────────────────────────────────────────────────────

def line_fig(df: pd.DataFrame, title: str, color: str = "#1a2035",
             fill: bool = True, suffix: str = "", height: int = 260,
             inter: bool = False) -> go.Figure:
    """Gráfico de linha simples. inter=True adiciona rangeslider."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy" if fill else "none",
        fillcolor=hex_rgba(color, 0.07),
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.2f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**(_I if inter else _B), title=title, height=height)
    if inter:
        fig = _add_rangeslider(fig, height)
    return _rng(fig, df, suffix) if not df.empty else fig


def bar_fig(df: pd.DataFrame, title: str, suffix: str = "",
            height: int = 260, inter: bool = False) -> go.Figure:
    """Gráfico de barras com cor verde/vermelho por sinal. inter=True adiciona rangeslider."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=["#16a34a" if v >= 0 else "#dc2626" for v in df["valor"]],
        marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**(_I if inter else _B), title=title, height=height)
    if inter:
        fig = _add_rangeslider(fig, height)
    return _rng(fig, df, suffix, 0.15) if not df.empty else fig


# ── Gráficos específicos de inflação ─────────────────────────────────────────

def cores_overlay_fig(df_ipca: pd.DataFrame, nucleo_data: dict,
                       height: int = 480) -> go.Figure:
    """
    Overlay do IPCA headline com todos os núcleos de inflação.
    nucleo_data: {sigla: (df, label, cor)}
    """
    fig = go.Figure()
    if not df_ipca.empty:
        fig.add_trace(go.Scatter(
            x=df_ipca["data"], y=df_ipca["valor"],
            mode="lines", name="IPCA (headline)",
            line=dict(color="#1a2035", width=2.5),
            hovertemplate="%{x|%b/%Y}<br><b>IPCA: %{y:.2f}%</b><extra></extra>",
        ))
    for key, (df_n, label, color) in nucleo_data.items():
        if not df_n.empty:
            fig.add_trace(go.Scatter(
                x=df_n["data"], y=df_n["valor"],
                mode="lines", name=f"{key} — {label}",
                line=dict(color=color, width=1.6),
                hovertemplate=f"%{{x|%b/%Y}}<br><b>{key}: %{{y:.2f}}%</b><extra></extra>",
            ))
    _layout = {**_I, "margin": dict(l=52, r=16, t=44, b=90)}
    fig.update_layout(
        **_layout, height=height,
        title="IPCA e Núcleos de Inflação (% ao mês)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0,
                    font=dict(size=10, color="#374151"), bgcolor="rgba(255,255,255,0)"),
    )
    fig.update_yaxes(ticksuffix="%")
    return _add_rangeslider(fig, height, extra_top=40)


def acum12m_meta_fig(df_ipca_full: pd.DataFrame, meta_val: float = 3.0) -> go.Figure:
    """
    Acumulado 12 meses do IPCA vs meta BCB com banda de tolerância.
    """
    df = df_ipca_full.copy().sort_values("data").reset_index(drop=True)
    if len(df) < 12:
        return go.Figure()
    df["acum12m"] = df["valor"].rolling(12).sum()
    df = df.dropna(subset=["acum12m"])

    fig = go.Figure()
    fig.add_hrect(
        y0=meta_val - BCB_TOLE, y1=meta_val + BCB_TOLE,
        fillcolor="rgba(22,163,74,0.08)", line_width=0,
        annotation_text=f"Banda ±{BCB_TOLE}pp", annotation_position="top right",
        annotation_font=dict(size=10, color="#16a34a"),
    )
    fig.add_hline(
        y=meta_val, line_dash="dot", line_color="#16a34a", line_width=1.5,
        annotation_text=f"Meta {meta_val:.1f}%", annotation_position="right",
        annotation_font=dict(size=10, color="#16a34a"),
    )
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["acum12m"],
        mode="lines", name="IPCA acum. 12M",
        line=dict(color="#1a2035", width=2),
        fill="tozeroy", fillcolor="rgba(26,32,53,0.05)",
        hovertemplate="%{x|%b/%Y}<br><b>Acum. 12M: %{y:.2f}%</b><extra></extra>",
    ))
    fig.update_layout(**_I, height=320, title="IPCA Acumulado 12 Meses vs Meta BCB",
                      hovermode="x unified", showlegend=False)
    fig.update_yaxes(ticksuffix="%")
    return _add_rangeslider(fig, 320)


def grupos_bar_fig(df_grupos: pd.DataFrame, ultimo_mes) -> go.Figure:
    """Barras horizontais com variação mensal por grupo no mês selecionado."""
    df_m = df_grupos[
        (df_grupos["data"] == ultimo_mes) &
        df_grupos["grupo_id"].isin(_GRUPO_IDS)
    ].copy().sort_values("valor", ascending=True)
    if df_m.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_m["valor"], y=df_m["grupo"], orientation="h",
        marker_color=["#dc2626" if v >= 0 else "#16a34a" for v in df_m["valor"]],
        marker_line_width=0,
        text=[f"{v:+.2f}%" for v in df_m["valor"]], textposition="outside",
        hovertemplate="%{y}<br><b>%{x:.2f}%</b><extra></extra>",
    ))
    _layout_g = {**_B, "margin": dict(l=185, r=70, t=44, b=36)}
    fig.update_layout(**_layout_g, height=340,
                      title=f"Variação Mensal por Grupo — {ultimo_mes.strftime('%b/%Y')}",
                      xaxis_title="% ao mês")
    fig.update_xaxes(ticksuffix="%", zeroline=True, zerolinecolor="#e2e5e9", zerolinewidth=1)
    return fig


def grupos_linhas_fig(df_grupos: pd.DataFrame, d_ini=None, d_fim=None,
                       height: int = 420) -> go.Figure:
    """
    Linhas de evolução mensal por grupo.
    Carrega série completa; d_ini/d_fim controlam apenas a janela inicial.
    """
    df_f = df_grupos[df_grupos["grupo_id"].isin(_GRUPO_IDS)].copy()
    if df_f.empty:
        return go.Figure()
    fig = go.Figure()
    for grupo in sorted(df_f["grupo"].unique()):
        df_g = df_f[df_f["grupo"] == grupo].sort_values("data")
        color = IPCA_GRUPOS_CORES.get(grupo, "#94a3b8")
        fig.add_trace(go.Scatter(
            x=df_g["data"], y=df_g["valor"], mode="lines+markers", name=grupo,
            line=dict(color=color, width=1.8), marker=dict(size=5, color=color),
            hovertemplate=f"%{{x|%b/%Y}}<br><b>{grupo}: %{{y:.2f}}%</b><extra></extra>",
        ))
    _layout_l = {**_I, "margin": dict(l=52, r=16, t=80, b=36)}
    fig.update_layout(
        **_layout_l, height=height,
        title="Variação Mensal por Grupo (% ao mês)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=10, color="#374151"),
                    bgcolor="rgba(255,255,255,0.8)", bordercolor="#e2e5e9", borderwidth=1),
    )
    x_max = df_f["data"].max()
    x_min = pd.Timestamp(d_ini) if d_ini else (x_max - pd.DateOffset(months=24))
    x_fim = pd.Timestamp(d_fim) if d_fim else x_max
    yr = _y_range_for_window(df_f, x_min, x_fim, pad=0.2)
    fig.update_yaxes(ticksuffix="%", range=yr)
    fig = _add_rangeslider(fig, height, extra_top=50)
    fig.update_xaxes(range=[str(x_min.date()), str(x_fim.date())])
    return fig
