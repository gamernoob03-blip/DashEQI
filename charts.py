"""
charts.py — Todas as figuras Plotly e helpers de visualização.
Nenhuma chamada a st.* aqui — só retorna go.Figure prontos para renderizar.
"""
import pandas as pd
import plotly.graph_objects as go

from settings import IPCA_GRUPOS_IDS, IPCA_GRUPOS_CORES, BCB_TOLE, COR_IPCA_LINHA

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

_I = {
    **_B,
    "xaxis": {**_B["xaxis"], "fixedrange": False},
    "yaxis": {**_B["yaxis"], "fixedrange": False},
    "dragmode": "zoom",
}

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
    h = h.lstrip("#")
    return f"rgba({int(h[:2],16)},{int(h[2:4],16)},{int(h[4:],16)},{a})"


def _y_range_for_window(df: pd.DataFrame, x_min, x_max,
                         value_col: str = "valor", pad: float = 0.15,
                         extra_min=None, extra_max=None) -> list:
    """Range Y baseado apenas nos pontos visíveis em [x_min, x_max]."""
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
    """Range X e Y para gráficos estáticos."""
    if df.empty:
        return fig
    mn, mx = df["valor"].min(), df["valor"].max()
    yd = (mx - mn) * pad if mx != mn else abs(mx) * 0.1 or 1
    xd = (df["data"].max() - df["data"].min()) * 0.02
    fig.update_xaxes(range=[df["data"].min() - xd, df["data"].max() + xd])
    fig.update_yaxes(range=[mn - yd, mx + yd], tickformat=".2f", ticksuffix=sfx.strip())
    return fig


def _apply_window(fig: go.Figure, df: pd.DataFrame, x_ini, x_fim,
                  suffix: str = "", height: int = 260,
                  extra_top: int = 32, pad: float = 0.15,
                  extra_min=None, extra_max=None) -> go.Figure:
    """
    Aplica janela X+Y e adiciona rangeslider.
    Chamado por line_fig e bar_fig quando inter=True e x_ini/x_fim fornecidos.
    Esta é a única função que define update_xaxes, update_yaxes e _add_rangeslider
    para gráficos interativos — app.py não precisa chamar nenhum desses.
    """
    yr = _y_range_for_window(df, x_ini, x_fim, pad=pad,
                             extra_min=extra_min, extra_max=extra_max)
    fig.update_xaxes(
        range=[str(pd.Timestamp(x_ini).date()), str(pd.Timestamp(x_fim).date())],
        rangeslider=dict(visible=True, thickness=0.05, bgcolor="#f1f5f9"),
        rangeselector=_RS_STYLE,
    )
    fig.update_yaxes(range=yr, fixedrange=False, ticksuffix=suffix.strip())
    fig.update_layout(height=height + 40, margin=dict(t=40 + extra_top))
    return fig


def _add_rangeslider(fig: go.Figure, height: int, extra_top: int = 32) -> go.Figure:
    """
    Adiciona rangeslider sem janela definida — usado pelos gráficos
    específicos de inflação que gerenciam x_ini/x_fim internamente.
    """
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
             inter: bool = False, x_ini=None, x_fim=None) -> go.Figure:
    """
    Gráfico de linha.
    - inter=False: estático, sem controles.
    - inter=True + x_ini/x_fim: interativo com janela definida, rangeslider e Y ajustado.
    - inter=True sem x_ini/x_fim: interativo sem janela inicial (usa série completa).
    """
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
        if x_ini is not None and x_fim is not None:
            return _apply_window(fig, df, x_ini, x_fim, suffix=suffix, height=height)
        fig = _add_rangeslider(fig, height)
        fig.update_yaxes(fixedrange=False, ticksuffix=suffix.strip())
        return fig
    return _rng(fig, df, suffix) if not df.empty else fig


def bar_fig(df: pd.DataFrame, title: str, suffix: str = "",
            height: int = 260, inter: bool = False,
            x_ini=None, x_fim=None) -> go.Figure:
    """
    Gráfico de barras.
    - inter=False: estático.
    - inter=True + x_ini/x_fim: interativo com janela e Y ajustado à janela.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["data"], y=df["valor"],
        marker_color=["#16a34a" if v >= 0 else "#dc2626" for v in df["valor"]],
        marker_line_width=0,
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>%{{y:.4f}}{suffix}</b><extra></extra>",
    ))
    fig.update_layout(**(_I if inter else _B), title=title, height=height)
    if inter:
        if x_ini is not None and x_fim is not None:
            return _apply_window(fig, df, x_ini, x_fim, suffix=suffix,
                                 height=height, pad=0.15)
        fig.update_xaxes(
            rangeslider=dict(visible=True, thickness=0.05, bgcolor="#f1f5f9",
                             yaxis=dict(rangemode="match")),
            rangeselector=_RS_STYLE,
        )
        fig.update_yaxes(fixedrange=False, rangemode="normal",
                         ticksuffix=suffix.strip())
        fig.update_layout(height=height + 40, margin=dict(t=40 + 32))
        return fig
    return _rng(fig, df, suffix, 0.15) if not df.empty else fig


# ── Gráficos específicos de inflação ─────────────────────────────────────────

def cores_overlay_fig(df_ipca: pd.DataFrame, nucleo_data: dict,
                       height: int = 480, x_ini=None, x_fim=None) -> go.Figure:
    """IPCA headline + núcleos. x_ini/x_fim definem janela inicial."""
    fig = go.Figure()
    if not df_ipca.empty:
        fig.add_trace(go.Scatter(
            x=df_ipca["data"], y=df_ipca["valor"],
            mode="lines", name="IPCA (headline)",
            line=dict(color=COR_IPCA_LINHA, width=2.5),
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
    fig.update_layout(
        **{**_I, "margin": dict(l=52, r=16, t=44, b=90)},
        height=height, title="IPCA e Núcleos de Inflação (% ao mês)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0,
                    font=dict(size=10, color="#374151"), bgcolor="rgba(255,255,255,0)"),
    )
    if x_ini and x_fim and not df_ipca.empty:
        # Combina todos os dfs para calcular Y range
        all_dfs = [df_ipca] + [df_n for _, (df_n, _, _) in nucleo_data.items() if not df_n.empty]
        df_all  = pd.concat(all_dfs, ignore_index=True)
        return _apply_window(fig, df_all, x_ini, x_fim,
                             suffix="%", height=height, extra_top=40, pad=0.2)
    fig.update_yaxes(ticksuffix="%")
    return _add_rangeslider(fig, height, extra_top=40)


def acum12m_meta_fig(df_ipca_full: pd.DataFrame, meta_val: float = 3.0,
                      x_ini=None, x_fim=None) -> go.Figure:
    """Acumulado 12M vs meta BCB com banda de tolerância."""
    df = df_ipca_full.copy().sort_values("data").reset_index(drop=True)
    if len(df) < 12:
        return go.Figure()
    df["acum12m"] = df["valor"].rolling(12).sum()
    df = df.dropna(subset=["acum12m"]).rename(columns={"acum12m": "valor"})
    teto = meta_val + BCB_TOLE

    fig = go.Figure()
    fig.add_hrect(
        y0=meta_val - BCB_TOLE, y1=teto,
        fillcolor="rgba(22,163,74,0.08)", line_width=0,
        annotation_text=f"Banda ±{BCB_TOLE}pp", annotation_position="top right",
        annotation_font=dict(size=10, color="#16a34a"),
    )
    fig.add_hline(y=meta_val, line_dash="dot", line_color="#16a34a", line_width=1.5,
                  annotation_text=f"Meta {meta_val:.1f}%", annotation_position="right",
                  annotation_font=dict(size=10, color="#16a34a"))
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["valor"],
        mode="lines", name="IPCA acum. 12M",
        line=dict(color=COR_IPCA_LINHA, width=2),
        fill="tozeroy", fillcolor=hex_rgba(COR_IPCA_LINHA, 0.05),
        hovertemplate="%{x|%b/%Y}<br><b>Acum. 12M: %{y:.2f}%</b><extra></extra>",
    ))
    fig.update_layout(**_I, height=320,
                      title="IPCA Acumulado 12 Meses vs Meta BCB",
                      hovermode="x unified", showlegend=False)
    if x_ini and x_fim:
        return _apply_window(fig, df, x_ini, x_fim, suffix="%", height=320,
                             pad=0.15, extra_min=float(BCB_TOLE),
                             extra_max=float(teto + 0.5))
    fig.update_yaxes(ticksuffix="%")
    return _add_rangeslider(fig, 320)


def grupos_bar_fig(df_grupos: pd.DataFrame, ultimo_mes) -> go.Figure:
    """Barras horizontais — snapshot mensal por grupo. Sempre estático."""
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
    fig.update_layout(**{**_B, "margin": dict(l=185, r=70, t=44, b=36)},
                      height=340,
                      title=f"Variação Mensal por Grupo — {ultimo_mes.strftime('%b/%Y')}",
                      xaxis_title="% ao mês")
    fig.update_xaxes(ticksuffix="%", zeroline=True,
                     zerolinecolor="#e2e5e9", zerolinewidth=1)
    return fig


def grupos_linhas_fig(df_grupos: pd.DataFrame, d_ini=None, d_fim=None,
                       height: int = 420) -> go.Figure:
    """Linhas de evolução mensal por grupo. d_ini/d_fim = janela inicial."""
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
    fig.update_layout(
        **{**_I, "margin": dict(l=52, r=16, t=80, b=36)},
        height=height, title="Variação Mensal por Grupo (% ao mês)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=10, color="#374151"),
                    bgcolor="rgba(255,255,255,0.8)", bordercolor="#e2e5e9", borderwidth=1),
    )
    x_max = df_f["data"].max()
    x_ini = pd.Timestamp(d_ini) if d_ini else (x_max - pd.DateOffset(months=24))
    x_fim = pd.Timestamp(d_fim) if d_fim else x_max
    return _apply_window(fig, df_f, x_ini, x_fim,
                         suffix="%", height=height, extra_top=50, pad=0.2)


def nucleos_acum12m_fig(df_all: pd.DataFrame, nucleo_data: dict,
                         ipca_a12: pd.DataFrame, meta_bcb: float,
                         x_ini=None, x_fim=None) -> go.Figure:
    """
    Média dos núcleos acumulado 12M vs meta BCB.
    df_all: DataFrame com colunas {key}_a12 e media_a12.
    """
    from settings import COR_MEDIA_NUCL
    piso_meta = meta_bcb - BCB_TOLE
    teto_meta = meta_bcb + BCB_TOLE

    fig = go.Figure()
    # Banda de dispersão entre mín e máx dos núcleos
    _acols = [f"{k}_a12" for k in nucleo_data if f"{k}_a12" in df_all.columns]
    if _acols:
        df_all["min_a12"] = df_all[_acols].min(axis=1)
        df_all["max_a12"] = df_all[_acols].max(axis=1)
        fig.add_trace(go.Scatter(
            x=pd.concat([df_all["data"], df_all["data"].iloc[::-1]]),
            y=pd.concat([df_all["max_a12"], df_all["min_a12"].iloc[::-1]]),
            fill="toself", fillcolor="rgba(139,92,246,0.10)",
            line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", showlegend=False,
        ))
    # Linhas individuais dos núcleos (pontilhadas)
    for key, (_, label, color) in nucleo_data.items():
        col_a = f"{key}_a12"
        if col_a in df_all.columns:
            fig.add_trace(go.Scatter(
                x=df_all["data"], y=df_all[col_a],
                mode="lines", name=key,
                line=dict(color=color, width=1, dash="dot"), opacity=0.55,
                hovertemplate=f"%{{x|%b/%Y}}<br>{key} acum. 12M: %{{y:.2f}}%<extra></extra>",
            ))
    # IPCA headline acum. 12M
    if not ipca_a12.empty:
        fig.add_trace(go.Scatter(
            x=ipca_a12["data"], y=ipca_a12["acum12m"],
            mode="lines", name="IPCA acum. 12M",
            line=dict(color=COR_IPCA_LINHA, width=1.8, dash="dash"),
            hovertemplate="%{x|%b/%Y}<br>IPCA acum. 12M: %{y:.2f}%<extra></extra>",
        ))
    # Média dos núcleos (destaque)
    fig.add_trace(go.Scatter(
        x=df_all["data"], y=df_all["media_a12"],
        mode="lines+markers", name="Média Núcleos acum. 12M",
        line=dict(color=COR_MEDIA_NUCL, width=2.5),
        marker=dict(size=6, color=COR_MEDIA_NUCL),
        hovertemplate="%{x|%b/%Y}<br><b>Média acum. 12M: %{y:.2f}%</b><extra></extra>",
    ))
    # Banda e linha de meta
    fig.add_hrect(y0=piso_meta, y1=teto_meta, fillcolor="rgba(22,163,74,0.07)", line_width=0)
    fig.add_hline(y=meta_bcb, line_dash="dot", line_color="#16a34a", line_width=1.2,
                  annotation_text=f"Meta {meta_bcb:.1f}%", annotation_position="right",
                  annotation_font=dict(size=10, color="#16a34a"))
    fig.update_layout(
        **{**_I, "margin": dict(l=52, r=16, t=44, b=90)},
        height=360, title="Núcleos de Inflação — Acumulado 12 Meses (%) vs Meta BCB",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0,
                    font=dict(size=10, color="#374151"), bgcolor="rgba(255,255,255,0)"),
    )
    # Anotação com último valor
    last_val = df_all["media_a12"].iloc[-1]
    fig.add_annotation(
        x=df_all["data"].iloc[-1], y=last_val,
        text=f"  {last_val:.2f}%", showarrow=False,
        font=dict(size=11, color=COR_MEDIA_NUCL, family="Inter"), xanchor="left",
    )
    # Janela + rangeslider
    df_vis = df_all[["data", "media_a12"]].rename(columns={"media_a12": "valor"})
    if x_ini and x_fim:
        return _apply_window(fig, df_vis, x_ini, x_fim,
                             suffix="%", height=360, extra_top=40,
                             pad=0.2, extra_min=0.0, extra_max=float(teto_meta + 0.5))
    fig.update_yaxes(ticksuffix="%")
    return _add_rangeslider(fig, 360, extra_top=40)


def grupos_acum12m_fig(df_acum_u: pd.DataFrame, ult_acum,
                        meta_bcb: float) -> go.Figure:
    """Barras horizontais — acumulado 12M por grupo vs meta. Sempre estático."""
    teto_meta = meta_bcb + BCB_TOLE
    piso_meta = meta_bcb - BCB_TOLE
    colors = ["#dc2626" if v > teto_meta else "#16a34a" if v < piso_meta else "#0891b2"
              for v in df_acum_u["valor"]]
    fig = go.Figure()
    fig.add_shape(type="rect", x0=piso_meta, x1=teto_meta,
                  y0=-0.5, y1=len(df_acum_u) - 0.5,
                  fillcolor="rgba(22,163,74,0.07)", line_width=0)
    fig.add_vline(x=meta_bcb, line_dash="dot", line_color="#16a34a", line_width=1.5,
                  annotation_text=f"Meta {meta_bcb:.1f}%", annotation_position="top",
                  annotation_font=dict(size=10, color="#16a34a"))
    fig.add_trace(go.Bar(
        x=df_acum_u["valor"], y=df_acum_u["grupo"], orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[f"{v:.1f}%" for v in df_acum_u["valor"]], textposition="outside",
        hovertemplate="%{y}<br><b>Acum. 12M: %{x:.2f}%</b><extra></extra>",
    ))
    fig.update_layout(
        **{**_B, "margin": dict(l=190, r=70, t=44, b=36)}, height=340,
        title=f"IPCA Acumulado 12M por Grupo — {ult_acum.strftime('%b/%Y')} (meta {meta_bcb:.1f}%)",
        xaxis_title="% acumulado 12 meses",
    )
    fig.update_xaxes(ticksuffix="%")
    return fig


def comparacao_fig(series_comp: dict, selecionados: list,
                   x_ini=None, x_fim=None) -> go.Figure:
    """
    Gráfico de comparação de séries com suporte a eixo Y duplo.
    series_comp: {nome: (df, unidade)}
    """
    _unidades = list(dict.fromkeys(u for _, u in series_comp.values()))
    _usa_y2   = len(_unidades) >= 2

    from settings import CORES_COMP
    fig  = go.Figure()
    cors = list(CORES_COMP)

    for i, (_nome, (_df_c, _unit)) in enumerate(series_comp.items()):
        if _df_c.empty:
            continue
        _cor  = cors[i % len(cors)]
        _yref = "y2" if (_usa_y2 and _unit != _unidades[0]) else "y"
        fig.add_trace(go.Scatter(
            x=_df_c["data"], y=_df_c["valor"],
            mode="lines", name=f"{_nome} ({_unit})",
            line=dict(color=_cor, width=2),
            yaxis=_yref,
            hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>{_nome}: %{{y:.2f}} {_unit}</b><extra></extra>",
        ))

    _layout = {
        **_I,
        "margin": dict(l=60, r=60, t=44, b=36),
        "hovermode": "x unified",
        "legend": dict(orientation="h", yanchor="bottom", y=1.02,
                       xanchor="left", x=0, font=dict(size=11)),
    }
    if _usa_y2:
        _layout["yaxis"]  = {**_I["yaxis"], "title": _unidades[0],
                              "ticksuffix": f" {_unidades[0]}"}
        _layout["yaxis2"] = dict(title=_unidades[1], overlaying="y", side="right",
                                  showgrid=False,
                                  tickfont=dict(size=10, color="#9ca3af"),
                                  zeroline=False, ticksuffix=f" {_unidades[1]}")

    fig.update_layout(**_layout, height=460, title=" vs ".join(selecionados))

    # Combina todos os dfs para calcular Y range
    _all_dfs = [df for df, _ in series_comp.values() if not df.empty]
    if _all_dfs and x_ini and x_fim:
        _df_combined = pd.concat(_all_dfs, ignore_index=True)
        return _apply_window(fig, _df_combined, x_ini, x_fim, height=460)

    return _add_rangeslider(fig, 460)
