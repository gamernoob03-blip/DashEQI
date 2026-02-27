# 🇧🇷 Dashboard Macro Brasil

Dashboard com os principais indicadores macroeconômicos do Brasil, atualizado automaticamente.

## Indicadores

| Indicador | Fonte | Atualização |
|-----------|-------|-------------|
| Ibovespa | Brapi.dev | A cada 30s |
| Dólar (USD/BRL) | Brapi.dev | A cada 30s |
| Euro (EUR/BRL) | Brapi.dev | A cada 30s |
| Selic | BCB/SGS (cód. 432) | Diária |
| IPCA | BCB/SGS (cód. 433) | Diária |
| IBC-Br | BCB/SGS (cód. 24363) | Diária |
| Dólar PTAX | BCB/SGS (cód. 1) | Diária |
| PIB | BCB/SGS (cód. 4380) | Diária |
| Desemprego PNAD | BCB/SGS (cód. 24369) | Diária |

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Como fazer o deploy no Streamlit Cloud (gratuito)

1. Faça fork ou suba este repositório no seu GitHub
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Clique em **"New app"**
4. Selecione o repositório e o arquivo `app.py`
5. Clique em **"Deploy!"**

Pronto — o dashboard ficará disponível em uma URL pública do tipo:
`https://seu-usuario-macro-brasil.streamlit.app`

## Estrutura do projeto

```
macro_brasil/
├── app.py                  # App principal
├── requirements.txt        # Dependências Python
├── .streamlit/
│   └── config.toml         # Tema escuro
└── README.md
```
