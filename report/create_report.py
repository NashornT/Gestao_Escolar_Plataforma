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
    alunos_turma = pd.read_sql("SELECT * FROM alunos_turma", con=engine)
    turmas = pd.read_sql("SELECT * FROM turmas", con=engine)
    return alunos, materias, notas, alunos_turma, turmas

# Título do app
st.set_page_config(page_title="Relatório de Notas", layout="wide")
st.title("\U0001F4CA Relatório de Desempenho Escolar")

# Dados
alunos_df, materias_df, notas_df, alunos_turma_df, turmas_df = carregar_dados()

# Juntando dados para análise
alunos_com_turma = alunos_df \
    .merge(alunos_turma_df, on="aluno_id") \
    .merge(turmas_df, on="turma_id")

notas_merged = notas_df \
    .merge(alunos_com_turma, on="aluno_id") \
    .merge(materias_df, on="disciplina_id")

# Ver valores únicos para debug de pré-filtros
valores_turno = notas_merged['turno'].dropna().unique()
valores_turma = notas_merged['turma'].dropna().unique()
st.sidebar.markdown("**Turnos disponíveis:**")
st.sidebar.write(valores_turno)
st.sidebar.markdown("**Turmas disponíveis:**")
st.sidebar.write(valores_turma)

# PRÉ-FILTROS
st.sidebar.markdown("### 🎯 Pré-Filtros")
if st.sidebar.button("🔹 Ensino Fundamental - Manhã"):
    turno_filtro = ['Manhã']
    serie_filtro = [turma for turma in valores_turma if '6' in turma or '7' in turma or '8' in turma or '9' in turma]
    dados_filtrados = notas_merged[notas_merged['turno'].isin(turno_filtro) & notas_merged['turma'].isin(serie_filtro)]
elif st.sidebar.button("🔹 Ensino Médio - Tarde"):
    turno_filtro = ['Tarde']
    serie_filtro = [turma for turma in valores_turma if '1' in turma or '2' in turma or '3' in turma]
    dados_filtrados = notas_merged[notas_merged['turno'].isin(turno_filtro) & notas_merged['turma'].isin(serie_filtro)]
else:
    dados_filtrados = notas_merged.copy()

# FILTROS GLOBAIS
with st.sidebar.expander("\U0001F50E Filtros", expanded=True):
    if st.button("❌ Limpar Filtros"):
        st.session_state.clear()
        st.experimental_set_query_params()
        st.stop()

    aluno_filtro = st.multiselect("Aluno:", alunos_df['aluno'].unique())
    disciplina_filtro = st.multiselect("Disciplina:", materias_df['disciplina'].unique())
    turno_user_filtro = st.multiselect("Turno:", turmas_df['turno'].dropna().unique())
    serie_user_filtro = st.multiselect("Turma:", turmas_df['turma'].dropna().unique())

if aluno_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['aluno'].isin(aluno_filtro)]
if disciplina_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['disciplina'].isin(disciplina_filtro)]
if turno_user_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['turno'].isin(turno_user_filtro)]
if serie_user_filtro:
    dados_filtrados = dados_filtrados[dados_filtrados['turma'].isin(serie_user_filtro)]

# Botão para download
csv = dados_filtrados.to_csv(index=False).encode('utf-8')
st.download_button("📥 Baixar dados como CSV", data=csv, file_name="relatorio_notas.csv", mime="text/csv")

# TABELA COMPLETA
st.subheader("\U0001F4C4 Dados Detalhados")
st.dataframe(dados_filtrados)

# MÉDIA POR DISCIPLINA
st.subheader("\U0001F4DA Média Geral por Disciplina")
media_disciplina = dados_filtrados.groupby("disciplina")["media_final"].mean().sort_values(ascending=False)
st.bar_chart(media_disciplina)

# TOP & BOTTOM ALUNOS
top_alunos = dados_filtrados.groupby("aluno")["media_final"].mean().sort_values(ascending=False).head(5)
bottom_alunos = dados_filtrados.groupby("aluno")["media_final"].mean().sort_values().head(5)

col1, col2 = st.columns(2)
with col1:
    st.subheader("\U0001F3C6 Top 5 Alunos")
    st.bar_chart(top_alunos)
with col2:
    st.subheader("\u26A0\uFE0F Alunos com Menor Desempenho")
    st.bar_chart(bottom_alunos)

# EVOLUÇÃO DE NOTAS POR ALUNO
st.subheader("\U0001F4C8 Evolução de Notas por Aluno")

aluno_selecionado = st.selectbox("Selecionar aluno", dados_filtrados['aluno'].unique())
df_aluno = dados_filtrados[dados_filtrados['aluno'] == aluno_selecionado]

if not df_aluno.empty:
    df_aluno_long = df_aluno.melt(
        id_vars=["aluno"],
        value_vars=["nota_1_bimestre", "nota_2_bimestre", "nota_3_bimestre", "nota_4_bimestre"],
        var_name="Bimestre", value_name="Nota"
    )
    df_aluno_long["Bimestre"] = df_aluno_long["Bimestre"].str.extract(r"nota_(\d)_bimestre")[0] + "º Bimestre"
    fig = px.line(df_aluno_long, x='Bimestre', y='Nota', title=f"Evolução de {aluno_selecionado}")
    st.plotly_chart(fig)

# ALUNOS COM RISCO DE REPROVAÇÃO
st.subheader("\U0001F6A8 Alunos com Média Abaixo de 6.0")
medias_gerais = dados_filtrados.groupby("aluno")["media_final"].mean().reset_index()
alunos_em_risco = medias_gerais[medias_gerais["media_final"] < 6.0]

if alunos_em_risco.empty:
    st.success("Nenhum aluno com risco de reprovação \U0001F389")
else:
    st.dataframe(alunos_em_risco)

# MÉDIA POR TURNO E SÉRIE
col1, col2 = st.columns(2)

with col1:
    st.subheader("\U0001F3EB Média por Turno")
    media_turno = dados_filtrados.groupby("turno")["media_final"].mean()
    st.bar_chart(media_turno)

with col2:
    st.subheader("\U0001F4D8 Média por Série")
    media_serie = dados_filtrados.groupby("turma")["media_final"].mean()
    st.bar_chart(media_serie)
