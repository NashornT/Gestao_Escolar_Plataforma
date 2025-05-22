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
        if table_name == "materias":
            insert_without_duplicates(df,engine,table_name)
        else:
            df.to_sql(table_name, con=engine, if_exists='append', index=index)
    else:
        print(f"Tabela '{table_name}' não encontrada. Criando a tabela com replace...")
        df.to_sql(table_name, con=engine, if_exists='replace', index=index)

    print(f"Dados enviados para a tabela '{table_name}' com sucesso!\n")


def insert_without_duplicates(df, engine, table_name):
    """
    Insere disciplinas sem duplicatas no banco de dados.
    :param df: DataFrame a ser inserido
    :param table_name: Nome da tabela no banco
    :param engine: Conexão SQLAlchemy
    """
    try:
        db_columns = pd.read_sql(f"SELECT disciplina FROM {table_name}", con=engine)
        db_columns['disciplina'] = db_columns['disciplina'].str.upper().str.strip().str.replace(' ', '_')
    except:
        db_columns = pd.DataFrame(columns=['disciplina'])

    # Remove duplicadas já existentes
    insert = df[~df['disciplina'].isin(db_columns['disciplina'])]

    if not insert.empty:
        print(f"Inserindo {len(insert)} disciplinas novas...")
        insert.to_sql(table_name, con=engine, if_exists='append', index=False)
    else:
        print("Nenhuma disciplina nova para inserir.")

