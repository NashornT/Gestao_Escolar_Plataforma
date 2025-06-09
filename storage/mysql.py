import pandas as pd
from sqlalchemy import create_engine, inspect
from storage.db_keys import user, password, host, port, database

def send_to_mysql(**kwargs):

    # Crie a conexão
    engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4')

    tables = {'df_students': 'alunos',
            'df_disciplines': 'materias',
            'df_grades': 'notas',
            'df_address': 'endereco',
            'df_professors': 'professores',
            'df_students_guardian': 'responsaveis',
            'df_classes': 'turmas',
            'df_students_classes': 'alunos_turma',
            'df_disciplines_classes': 'disciplina_turma',
            'df_professors_disciplines': 'professores_disciplinas'}

    for table in tables.keys():
        if kwargs.get(table) is not None:
            safe_to_sql(kwargs.get(table), tables[table], engine, index=False)
        else:
            print(f"DataFrame '{table}' não encontrado. Pulando a inserção.")


def safe_to_sql(df, table_name, engine, index=False):
    """
    Insere o DataFrame em uma tabela no banco de dados de forma segura.
    Se a tabela existir, faz append. Se não existir, cria a tabela (replace).

    :param df: DataFrame a ser inserido
    :param table_name: Nome da tabela no banco
    :param engine: Conexão SQLAlchemy
    :param index: Se deve ou não inserir o índice do DataFrame (default: False)
    """
    inspector = inspect(engine)
    tabelas_existentes = inspector.get_table_names()

    if table_name in tabelas_existentes:
        print(f"Tabela '{table_name}' encontrada. Inserindo dados com append...")
        if table_name == "materias" or table_name == "turmas":
            insert_without_duplicates(df,engine,table_name)
        else:
            df.to_sql(table_name, con=engine, if_exists='append', index=index)
    else:
        print(f"Tabela '{table_name}' não encontrada. Criando a tabela com replace...")
        df.to_sql(table_name, con=engine, if_exists='replace', index=index)

    print(f"Dados enviados para a tabela '{table_name}' com sucesso!\n")


def insert_without_duplicates(df, engine, table_name):
    """
    Insere registros sem duplicatas no banco de dados.
    :param df: DataFrame a ser inserido
    :param table_name: Nome da tabela no banco
    :param engine: Conexão SQLAlchemy
    """
    if table_name == "materias":
        column = "disciplina"
    elif table_name == "turmas":
        column = "turma_id"
    else:
        raise ValueError("Tabela não suportada para remoção de duplicatas.")

    try:
        # Carrega os valores existentes no banco para a coluna relevante
        db_columns = pd.read_sql(f"SELECT {column} FROM {table_name}", con=engine)
        db_columns[column] = db_columns[column].str.strip().str.upper()
    except Exception as e:
        print(f"Erro ao carregar dados existentes: {e}")
        db_columns = pd.DataFrame(columns=[column])

    # Padroniza os valores do DataFrame de entrada
    df[column] = df[column].str.strip().str.upper()

    # Remove duplicatas já existentes no banco
    insert = df[~df[column].isin(db_columns[column])]

    if not insert.empty:
        print(f"Inserindo {len(insert)} novos registros na tabela '{table_name}'...")
        insert.to_sql(table_name, con=engine, if_exists='append', index=False)
    else:
        print(f"Nenhum registro novo para inserir na tabela '{table_name}'.")
