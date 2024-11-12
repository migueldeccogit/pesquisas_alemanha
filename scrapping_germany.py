import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import numpy as np

# Definir cores específicas para cada partido ou coalizão
CATEGORY_COLORS = {
    "SPD": "#de001d",
    "Union": "#151518",
    "Green": "#459b40",
    "FDP": "#fded2f",
    "AfD": "#28a2dc",
    "Linke": "#bb2c75",
    "FW": "#f3a724",
    "BSW": "#772151",
    "Others": "#9f9f9f",
    "CDU + SPD": "#94beff",
    "CDU + Green": "#006340",
    "CDU + SPD + FDP": "#eead2d",
    "CDU + SPD + Green": "#151518",
    "SPD + Green + FDP": "#f77315",
}

# Configuração da página
st.set_page_config(layout="wide")

# URL da página da Wikipédia
url = (
    "https://en.wikipedia.org/wiki/Opinion_polling_for_the_2025_German_federal_election"
)


def adicionar_coalisoes(df):
    df["CDU + SPD"] = df["Union"] + df["SPD"]
    df["CDU + Green"] = df["Union"] + df["Green"]
    df["CDU + SPD + FDP"] = df["Union"] + df["SPD"] + df["FDP"]
    df["CDU + SPD + Green"] = df["Union"] + df["SPD"] + df["Green"]
    df["SPD + Green + FDP"] = df["SPD"] + df["Green"] + df["FDP"]
    return df


def aplicar_barreira(row, colunas_valor, barreira):
    # Somar valores que não passam a barreira
    total_outros = sum(val for col, val in row[colunas_valor].items() if val < barreira)

    # Definir valores abaixo da barreira como 0 e reter os que passam
    valores_ponderados = {
        col: (val if val >= barreira else 0) for col, val in row[colunas_valor].items()
    }

    # Calcular a soma dos valores que passam na barreira
    total_passando = sum(valores_ponderados.values())

    # Reponderar os valores que passaram a barreira para manter a proporção
    if total_passando > 0:
        for col in colunas_valor:
            if valores_ponderados[col] > 0:
                valores_ponderados[col] = (valores_ponderados[col] / total_passando) * (
                    total_passando + total_outros
                )

    # Atualizar os valores no DataFrame
    for col in colunas_valor:
        row[col] = valores_ponderados[col]

    return row

# Função para adicionar linha horizontal se necessário
def add_threshold_line(fig, data, threshold=50):
    if data["Percentual"].max() > threshold:
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="grey",
        )
def add_vertical_line(fig):
    fig.add_vline(
        x=datetime.datetime(2024, 11, 7),
        line_width=2,
        line_dash="dash",
        line_color="grey",
    )

# Função para carregar e processar os dados da página, cacheada para evitar repetição
@st.cache_data(ttl=300)
def carregar_dados():
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", {"class": "wikitable"})
    headers = [
        header.text.strip() for header in table.find_all("th") if header.text.strip()
    ]
    rows = [
        [cell.text.strip() for cell in row.find_all(["td", "th"])]
        for row in table.find_all("tr")[1:]
    ]

    # Criação do DataFrame inicial
    df = pd.DataFrame(rows, columns=headers).drop(0)
    df["Fieldwork date"] = pd.to_datetime(
        df["Fieldwork date"].apply(lambda x: x.split("–")[-1].strip()), errors="coerce"
    )
    df = df[df["Fieldwork date"] >= "2023-12-31"].replace("–", np.nan)
    df = df.rename(columns={"Grüne": "Green"})

    # Criação do DataFrame de médias
    colunas_valor = [
        "SPD",
        "Union",
        "Green",
        "FDP",
        "AfD",
        "Linke",
        "FW",
        "BSW",
        "Others",
    ]
    df[colunas_valor] = df[colunas_valor].apply(pd.to_numeric, errors="coerce")
    df_ponderado = df.apply(
        lambda row: aplicar_barreira(row, colunas_valor=colunas_valor, barreira=5),
        axis=1,
    )
    df_ponderado[colunas_valor] = df_ponderado[colunas_valor].apply(
        lambda x: x.round(1)
    )
    # Adicionar colunas de coalizões
    df = adicionar_coalisoes(df=df)

    df_media = df.groupby("Fieldwork date")[colunas_valor].mean().reset_index()
    df_media = df_media.sort_values(
        "Fieldwork date"
    )  # Garantir que as datas estejam ordenadas
    df_media[colunas_valor] = (
        df_media[colunas_valor].rolling(window=4, min_periods=1).mean()
    )  # Média móvel de 4 períodos
    df_media = adicionar_coalisoes(df=df_media)
    df_ponderado_media = (
        df_ponderado.groupby("Fieldwork date")[colunas_valor].mean().reset_index()
    )
    df_ponderado_media = df_ponderado_media.sort_values("Fieldwork date")
    df_ponderado_media[colunas_valor] = (
        df_ponderado_media[colunas_valor].rolling(window=4, min_periods=1).mean()
    )  # Média móvel de 4 períodos para o ponderado
    df_ponderado = adicionar_coalisoes(df=df_ponderado)
    df_ponderado_media = adicionar_coalisoes(df=df_ponderado_media)

    return df, df_media, df_ponderado, df_ponderado_media


# Carregar os dados processados
df, df_media, df_ponderado, df_ponderado_media = carregar_dados()

# Configuração do título do dashboard
st.title("Pesquisa Eleitoral Alemã")

# Filtros globais
polling_firms = df["Polling firm"].unique()
partidos = list(CATEGORY_COLORS.keys())
min_date, max_date = (
    df["Fieldwork date"].min().date(),
    df["Fieldwork date"].max().date(),
)

# Controle deslizante para seleção de intervalo de datas
selected_date_range = st.slider(
    "Selecione o intervalo de datas",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
)

# Selectbox para seleção de firma de pesquisa
selected_firm = st.selectbox("Selecione a Pesquisa", options=polling_firms)

# Multiselect para seleção de partidos
selected_parties = st.pills(
    "Selecione os Partidos/Coalizões",
    options=partidos,
    default=None,
    selection_mode="multi",
)

# Filtragem de dados
df_filtered = df[
    (df["Fieldwork date"] >= pd.to_datetime(selected_date_range[0]))
    & (df["Fieldwork date"] <= pd.to_datetime(selected_date_range[1]))
]
df_media_filtered = df_media[
    (df_media["Fieldwork date"] >= pd.to_datetime(selected_date_range[0]))
    & (df_media["Fieldwork date"] <= pd.to_datetime(selected_date_range[1]))
]
df_ponderado_filtered = df_ponderado[
    (df_ponderado["Fieldwork date"] >= pd.to_datetime(selected_date_range[0]))
    & (df_ponderado["Fieldwork date"] <= pd.to_datetime(selected_date_range[1]))
]
df_ponderado_media_filtered = df_ponderado_media[
    (df_ponderado_media["Fieldwork date"] >= pd.to_datetime(selected_date_range[0]))
    & (df_ponderado_media["Fieldwork date"] <= pd.to_datetime(selected_date_range[1]))
]

# Colunas para os gráficos
col1, col2 = st.columns(2)

# Gráfico 1: Pesquisa específica por firma
with col1:
    st.subheader(f"Evolução dos Partidos - {selected_firm}")
    df_firm_filtered = df_filtered[df_filtered["Polling firm"] == selected_firm]
    df_firm_filtered = df_firm_filtered.melt(
        id_vars=["Fieldwork date"],
        value_vars=selected_parties,
        var_name="Partido",
        value_name="Percentual",
    )
    fig1 = go.Figure()
    for partido in selected_parties:
        data_partido = df_firm_filtered[df_firm_filtered["Partido"] == partido]
        fig1.add_trace(
            go.Scatter(
                x=data_partido["Fieldwork date"],
                y=data_partido["Percentual"],
                mode="lines+markers",
                name=partido,
                line=dict(color=CATEGORY_COLORS.get(partido, "#000000")),
            )
        )
    add_threshold_line(fig1, df_firm_filtered)
    add_vertical_line(fig1)
    fig1.update_layout(xaxis_title="Data", yaxis_title="Percentual (%)")
    st.plotly_chart(
        fig1, use_container_width=True, key="plotly_chart1"
    )  # Adiciona uma chave única

# Gráfico 2: Média das pesquisas
with col2:
    st.subheader("Evolução dos Partidos - Todas as Pesquisas")
    df_media_filtered = df_media_filtered.melt(
        id_vars="Fieldwork date",
        value_vars=selected_parties,
        var_name="Partido",
        value_name="Percentual",
    )
    fig2 = go.Figure()

    # Adicionar a "nuvem" de pontos de cada partido com transparência
    for partido in selected_parties:
        data_partido = df_filtered.melt(
            id_vars=["Fieldwork date"],
            value_vars=[partido],
            var_name="Partido",
            value_name="Percentual",
        )
        data_partido = data_partido[data_partido["Partido"] == partido]
        fig2.add_trace(
            go.Scatter(
                x=data_partido["Fieldwork date"],
                y=data_partido["Percentual"],
                mode="markers",
                name=f"{partido} (pontos)",
                marker=dict(
                    color=CATEGORY_COLORS.get(partido, "#000000"),
                    opacity=0.6,  # Transparência dos pontos
                    size=6,
                ),
                showlegend=False,  # Ocultar a legenda dos pontos
            )
        )

    # Adicionar as linhas de média
    for partido in selected_parties:
        data_partido = df_media_filtered[df_media_filtered["Partido"] == partido]
        fig2.add_trace(
            go.Scatter(
                x=data_partido["Fieldwork date"],
                y=data_partido["Percentual"],
                mode="lines",
                name=partido,
                line_shape="spline",
                line=dict(color=CATEGORY_COLORS.get(partido, "#000000")),
            )
        )
    add_threshold_line(fig2, df_media_filtered)
    add_vertical_line(fig2)
    fig2.update_layout(xaxis_title="Data", yaxis_title="Percentual (%)")
    st.plotly_chart(fig2, use_container_width=True, key="plotly_chart2")

# Segunda linha de gráficos
col3, col4 = st.columns(2)
with col3:
    st.subheader(f"Evolução dos Partidos (Reponderado) - {selected_firm}")
    df_firm_filtered = df_ponderado_filtered[
        df_ponderado_filtered["Polling firm"] == selected_firm
    ]
    df_firm_filtered = df_firm_filtered.melt(
        id_vars=["Fieldwork date"],
        value_vars=selected_parties,
        var_name="Partido",
        value_name="Percentual",
    )
    fig3 = go.Figure()
    for partido in selected_parties:
        data_partido = df_firm_filtered[df_firm_filtered["Partido"] == partido]
        fig3.add_trace(
            go.Scatter(
                x=data_partido["Fieldwork date"],
                y=data_partido["Percentual"],
                mode="lines+markers",
                name=partido,
                line=dict(color=CATEGORY_COLORS.get(partido, "#000000")),
            )
        )
    add_threshold_line(fig3, df_firm_filtered)
    add_vertical_line(fig3)
    fig3.update_layout(xaxis_title="Data", yaxis_title="Percentual (%)")
    st.plotly_chart(
        fig3, use_container_width=True, key="plotly_chart3"
    )  # Adiciona uma chave única

# Gráfico 2: Média das pesquisas
with col4:
    st.subheader("Evolução dos Partidos (Reponderado) - Todas as Pesquisas")
    df_ponderado_media_filtered = df_ponderado_media_filtered.melt(
        id_vars="Fieldwork date",
        value_vars=selected_parties,
        var_name="Partido",
        value_name="Percentual",
    )
    fig4 = go.Figure()

    # Adicionar a "nuvem" de pontos de cada partido com transparência
    for partido in selected_parties:
        data_partido = df_ponderado_filtered.melt(
            id_vars=["Fieldwork date"],
            value_vars=[partido],
            var_name="Partido",
            value_name="Percentual",
        )
        data_partido = data_partido[data_partido["Partido"] == partido]
        fig4.add_trace(
            go.Scatter(
                x=data_partido["Fieldwork date"],
                y=data_partido["Percentual"],
                mode="markers",
                name=f"{partido} (pontos)",
                marker=dict(
                    color=CATEGORY_COLORS.get(partido, "#000000"),
                    opacity=0.6,  # Transparência dos pontos
                    size=6,
                ),
                showlegend=False,  # Ocultar a legenda dos pontos
            )
        )

    # Adicionar as linhas de média
    for partido in selected_parties:
        data_partido = df_ponderado_media_filtered[
            df_ponderado_media_filtered["Partido"] == partido
        ]
        fig4.add_trace(
            go.Scatter(
                x=data_partido["Fieldwork date"],
                y=data_partido["Percentual"],
                mode="lines",
                name=partido,
                line_shape="spline",
                line=dict(color=CATEGORY_COLORS.get(partido, "#000000")),
            )
        )
    add_threshold_line(fig4, df_ponderado_media_filtered)
    add_vertical_line(fig4)
    fig4.update_layout(xaxis_title="Data", yaxis_title="Percentual (%)")
    st.plotly_chart(fig4, use_container_width=True, key="plotly_chart4")
