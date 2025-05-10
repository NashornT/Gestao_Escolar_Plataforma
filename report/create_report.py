import sys
import os

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from storage.db_keys import user, password, host, port, database

# Conexão com MySQL
engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")

# Carregamento com cache
@st.cache_data
def carregar_dados():
    alunos = pd.read_sql("SELECT * FROM alunos", con=engine)
    materias = pd.read_sql("SELECT * FROM materias", con=engine)
    notas = pd.read_sql("SELECT * FROM notas", con=engine)
    return alunos, materias, notas

# Título do app
st.set_page_config(page_title="Relatório de Notas", layout="wide")
st.title("📊 Relatório de Desempenho Escolar")

# Dados
alunos_df, materias_df, notas_df = carregar_dados()
notas_merged = notas_df \
    .merge(alunos_df, on="aluno_id") \
    .merge(materias_df, on="disciplina_id")

# FILTROS GLOBAIS
st.sidebar.header("🔎 Filtros")

aluno_filtro = st.sidebar.multiselect("Aluno:", alunos_df['aluno'].unique())
disciplina_filtro = st.sidebar.multiselect("Disciplina:", materias_df['disciplina'].unique())
turno_filtro = st.sidebar.multiselect("Turno:", alunos_df['turno'].dropna().unique())
serie_filtro = st.sidebar.multiselect("Série:", alunos_df['nivel_escolar'].dropna().unique())

dados_filtrados = notas_merged.copy()
if aluno_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['aluno'].isin(aluno_filtro)]
if disciplina_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['disciplina'].isin(disciplina_filtro)]
if turno_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['turno'].isin(turno_filtro)]
if serie_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['nivel_escolar'].isin(serie_filtro)]

# TABELA COMPLETA
st.subheader("📄 Dados Detalhados")
st.dataframe(dados_filtrados)

# MÉDIA POR DISCIPLINA
st.subheader("📚 Média Geral por Disciplina")
media_disciplina = dados_filtrados.groupby("disciplina")["media_notas"].mean().sort_values(ascending=False)
st.bar_chart(media_disciplina)

# TOP & BOTTOM ALUNOS
top_alunos = dados_filtrados.groupby("aluno")["media_notas"].mean().sort_values(ascending=False).head(5)
bottom_alunos = dados_filtrados.groupby("aluno")["media_notas"].mean().sort_values().head(5)

col1, col2 = st.columns(2)
with col1:
    st.subheader("🏆 Top 5 Alunos")
    st.bar_chart(top_alunos)
with col2:
    st.subheader("⚠️ Alunos com Menor Desempenho")
    st.bar_chart(bottom_alunos)

# EVOLUÇÃO DE NOTAS POR ALUNO
st.subheader("📈 Evolução de Notas por Aluno")

aluno_selecionado = st.selectbox("Selecionar aluno", dados_filtrados['aluno'].unique())
df_aluno = dados_filtrados[dados_filtrados['aluno'] == aluno_selecionado]

if not df_aluno.empty:
    evolucao = df_aluno[["primeiro_bimestre_nota", "segundo_bimestre_nota", "terceiro_bimestre_nota", "quarto_bimestre_nota"]].mean().reset_index()
    evolucao.columns = ['Bimestre', 'Média']
    fig = px.line(evolucao, x='Bimestre', y='Média', title=f"Evolução de {aluno_selecionado}")
    st.plotly_chart(fig)

# ALUNOS COM RISCO DE REPROVAÇÃO
st.subheader("🚨 Alunos com Média Abaixo de 6.0")
medias_gerais = dados_filtrados.groupby("aluno")["media_notas"].mean().reset_index()
alunos_em_risco = medias_gerais[medias_gerais["media_notas"] < 6.0]

if alunos_em_risco.empty:
    st.success("Nenhum aluno com risco de reprovação 🎉")
else:
    st.dataframe(alunos_em_risco)

# MÉDIA POR TURNO E SÉRIE
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏫 Média por Turno")
    media_turno = dados_filtrados.groupby("turno")["media_notas"].mean()
    st.bar_chart(media_turno)

with col2:
    st.subheader("📘 Média por Série")
    media_serie = dados_filtrados.groupby("nivel_escolar")["media_notas"].mean()
    st.bar_chart(media_serie)
