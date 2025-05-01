import pandas as pd
from sqlalchemy import create_engine
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
from storage.db_keys import user, password, host, port, database

# Função para buscar dados do banco
def carregar_dados():

    # Crie a engine SQLAlchemy (ajuste user, password, host e database)
    engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}/{database}")

    # Use essa engine no lugar do mysql.connector
    alunos = pd.read_sql("SELECT * FROM alunos", engine)
    materias = pd.read_sql("SELECT * FROM materias", engine)
    notas = pd.read_sql("SELECT * FROM notas", engine)

    df = notas.merge(alunos, on='aluno_id').merge(materias, on='disciplina_id')
    return df

# Inicializa app
app = Dash(__name__)

# Layout
app.layout = html.Div([
    html.H2("Dashboard Escolar"),

    dcc.Dropdown(id='aluno-dropdown', placeholder="Selecione um aluno"),
    dcc.Graph(id='grafico-notas'),
    dcc.Graph(id='grafico-materias'),
    dcc.Graph(id='grafico-ranking')
])

# Callback para preencher dropdown assim que abrir
@app.callback(
    Output('aluno-dropdown', 'options'),
    Input('aluno-dropdown', 'id')  # só para disparar a primeira vez
)
def preencher_dropdown(_):
    df = carregar_dados()
    opcoes = df[['aluno_id', 'nome']].drop_duplicates()
    return [{'label': nome, 'value': aluno_id} for aluno_id, nome in zip(opcoes['aluno_id'], opcoes['nome'])]

# Callback para os gráficos
@app.callback(
    Output('grafico-notas', 'figure'),
    Output('grafico-materias', 'figure'),
    Output('grafico-ranking', 'figure'),
    Input('aluno-dropdown', 'value')
)
def atualizar_graficos(aluno_id):
    df = carregar_dados()

    # Gráfico 1: Notas do aluno por disciplina
    df_aluno = df[df['aluno_id'] == aluno_id]
    fig1 = px.bar(df_aluno, x='nome_y', y='media_notas',
                  title='Notas por Matéria', labels={'nome_y': 'Disciplina'})

    # Gráfico 2: Média geral por matéria
    df_materia = df.groupby('nome_y')['media_notas'].mean().reset_index()
    fig2 = px.bar(df_materia, x='nome_y', y='media_notas',
                  title='Média Geral por Matéria', labels={'nome_y': 'Disciplina'})

    # Gráfico 3: Ranking de alunos
    df_ranking = df.groupby(['aluno_id', 'nome'])['media_notas'].mean().reset_index()
    fig3 = px.bar(df_ranking, x='nome', y='media_notas',
                  title='Ranking de Alunos', labels={'nome': 'Aluno'}, sort='y')

    return fig1, fig2, fig3

# Run
if __name__ == '__main__':
    app.run(debug=True)

