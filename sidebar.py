"""
sidebar.py — Menu lateral
Lida com estado de colapso, navegação entre páginas e layout da sidebar.
"""

import streamlit as st

NAV_ICONS = {
    "Início":           "⌂",
    "Mercados Globais": "◎",
    "Gráficos":         "⌇",
    "Exportar":         "↓",
}
NAV_KEYS = list(NAV_ICONS.keys())


def init_state():
    """Inicializa variáveis de session_state necessárias para a sidebar."""
    if "pagina"       not in st.session_state:
        st.session_state.pagina       = "Início"
    if "sb_collapsed" not in st.session_state:
        st.session_state.sb_collapsed = False


def _nav_button(key: str, label: str, use_container_width: bool = True):
    """Botão de navegação com highlight automático se for a página ativa."""
    is_active = st.session_state.pagina == key
    clicked   = st.button(
        label,
        key=f"nav_{'c' if st.session_state.sb_collapsed else 'e'}_{key}",
        type="primary" if is_active else "secondary",
        use_container_width=use_container_width,
        help=key if st.session_state.sb_collapsed else None,
    )
    if clicked:
        st.session_state.pagina = key
        st.rerun()


def render():
    """
    Renderiza a sidebar completa.
    Chame esta função dentro de `with st.sidebar:` no app principal,
    ou deixe que ela cuide do contexto internamente.
    """
    collapsed = st.session_state.sb_collapsed

    with st.sidebar:
        if collapsed:
            _render_collapsed()
        else:
            _render_expanded()


def _render_collapsed():
    """Sidebar no modo estreito (64px) — apenas ícones."""
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Botão para expandir
    st.markdown(
        "<div class='sb-toggle-btn' style='display:flex;justify-content:center;padding:4px 8px'>",
        unsafe_allow_html=True,
    )
    if st.button("›", key="sb_expand"):
        st.session_state.sb_collapsed = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='height:1px;background:#e8eaed;margin:8px 6px'></div>",
        unsafe_allow_html=True,
    )

    # Ícones de navegação centralizados
    for key in NAV_KEYS:
        st.markdown(
            "<div style='display:flex;justify-content:center;padding:0 4px'>",
            unsafe_allow_html=True,
        )
        _nav_button(key, NAV_ICONS[key])
        st.markdown("</div>", unsafe_allow_html=True)


def _render_expanded():
    """Sidebar no modo expandido (220px) — logo + labels de navegação."""
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # Logo + botão de colapso
    col_logo, col_btn = st.columns([5, 2])
    with col_logo:
        st.markdown(
            "<div style='padding:14px 0 8px 18px'>"
            "<div style='font-size:9px;font-weight:700;color:#d1d5db;"
            "letter-spacing:3px;text-transform:uppercase;margin-bottom:3px'>BR</div>"
            "<div style='font-size:15px;font-weight:700;color:#111827;"
            "letter-spacing:-0.3px'>Macro Brasil</div></div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sb-toggle-btn'>", unsafe_allow_html=True)
        if st.button("‹", key="sb_collapse"):
            st.session_state.sb_collapsed = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='height:1px;background:#e8eaed;margin:2px 0 6px 0'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:9px;font-weight:700;color:#9ca3af;"
        "text-transform:uppercase;letter-spacing:2px;"
        "padding:4px 18px 8px 18px'>Navegação</div>",
        unsafe_allow_html=True,
    )

    # Botões de navegação
    for key in NAV_KEYS:
        st.markdown("<div style='padding:0 6px'>", unsafe_allow_html=True)
        _nav_button(key, f"{NAV_ICONS[key]}   {key}")
        st.markdown("</div>", unsafe_allow_html=True)

    # Rodapé
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='height:1px;background:#e8eaed;margin:0 0 8px 0'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:9px;color:#d1d5db;line-height:1.9;padding:0 18px 16px 18px'>"
        "Fontes: BCB/SGS · Yahoo Finance<br>"
        "Mercados: ↻ 60s &nbsp;|&nbsp; BCB: ↻ 1h"
        "</div>",
        unsafe_allow_html=True,
    )
