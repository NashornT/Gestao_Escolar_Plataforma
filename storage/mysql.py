import pandas as pd
from sqlalchemy import create_engine, inspect
from storage.db_keys import user, password, host, port, database

def send_to_mysql(**kwargs):

    # Crie a conexão
    engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4')

    safe_to_sql(kwargs.get('df_students'), 'alunos', engine, index=False)
    safe_to_sql(kwargs.get('df_disciplines'), 'materias', engine, index=False)
    safe_to_sql(kwargs.get('df_grades'), 'notas', engine, index=False)



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
        db_columns = pd.read_sql(f"SELECT nome FROM {table_name}", con=engine)
        db_columns['nome'] = db_columns['nome'].str.upper().str.strip().str.replace(' ', '_')
    except:
        db_columns = pd.DataFrame(columns=['nome'])

    # Remove duplicadas já existentes
    insert = df[~df['nome'].isin(db_columns['nome'])]

    if not insert.empty:
        print(f"Inserindo {len(insert)} disciplinas novas...")
        insert.to_sql(table_name, con=engine, if_exists='append', index=False)
    else:
        print("Nenhuma disciplina nova para inserir.")

