import pandas as pd
from sqlalchemy import create_engine, inspect, text
from storage.db_keys import user, password, host, port, database
from methods.logging_config import setup_logging

logger = setup_logging()


def limpar_dados_turma(turma_id, engine):
    """Apaga todos os dados associados a uma turma específica antes de uma nova inserção."""
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            logger.info(f"Iniciando limpeza de dados para a turma_id: {turma_id}...")

            # Pega todos os alunos associados a esta turma
            alunos_na_turma_query = text("SELECT aluno_id FROM alunos_turma WHERE turma_id = :turma_id")
            alunos_ids = [row[0] for row in connection.execute(alunos_na_turma_query, {'turma_id': turma_id})]

            if alunos_ids:
                # Deleta as notas desses alunos
                connection.execute(text("DELETE FROM notas WHERE aluno_id IN :alunos_ids"),
                                   {'alunos_ids': tuple(alunos_ids)})
                logger.info(f"Notas antigas de {len(alunos_ids)} alunos foram removidas.")

                # Deleta as matrículas na tabela alunos_turma
                connection.execute(text("DELETE FROM alunos_turma WHERE turma_id = :turma_id"), {'turma_id': turma_id})
                logger.info("Matrículas antigas da turma foram removidas.")

                # Deleta os próprios alunos
                connection.execute(text("DELETE FROM alunos WHERE aluno_id IN :alunos_ids"),
                                   {'alunos_ids': tuple(alunos_ids)})
                logger.info(f"{len(alunos_ids)} registros de alunos antigos foram removidos.")

            trans.commit()
            logger.info("Limpeza de dados da turma concluída com sucesso.")
        except Exception as e:
            trans.rollback()
            logger.error(f"Erro durante a limpeza de dados da turma: {e}")
            raise



def send_to_mysql(**kwargs):
    engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4')

    df_students = kwargs.get('df_students')
    if df_students is not None and not df_students.empty:
        # Pega a lista de IDs de alunos que estão sendo processados NESTE ARQUIVO
        ids_para_processar = tuple(df_students['aluno_id'].unique())

        with engine.connect() as connection:
            trans = connection.begin()
            try:
                logger.info(f"Limpando dados antigos para {len(ids_para_processar)} alunos...")
                # Apaga os registros dependentes PRIMEIRO
                connection.execute(text("DELETE FROM notas WHERE aluno_id IN :ids"), {'ids': ids_para_processar})
                connection.execute(text("DELETE FROM alunos_turma WHERE aluno_id IN :ids"), {'ids': ids_para_processar})
                # Depois apaga os próprios alunos
                connection.execute(text("DELETE FROM alunos WHERE aluno_id IN :ids"), {'ids': ids_para_processar})
                trans.commit()
            except Exception as e:
                trans.rollback()
                logger.error(f"Erro ao limpar dados antigos: {e}")
                raise

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

    for table_key, table_name in tables.items():
        df = kwargs.get(table_key)
        if df is not None:
            safe_to_sql(df, table_name, engine, index=False)
        else:
            logger.info(f"DataFrame '{table_key}' não encontrado. Pulando a inserção.")


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

    # Lógica de prevenção de duplicatas para a tabela de alunos
    if table_name == 'alunos':
        if not df.empty:
            df.drop_duplicates(subset=['aluno_id'], keep='first', inplace=True)
            if table_name in tabelas_existentes:
                try:
                    db_alunos_ids = pd.read_sql(f"SELECT aluno_id FROM {table_name}", con=engine)
                    df = df[~df['aluno_id'].isin(db_alunos_ids['aluno_id'])]
                except Exception as e:
                    logger.info(f"Não foi possível verificar alunos existentes: {e}")

    if table_name in tabelas_existentes:
        logger.info(f"Tabela '{table_name}' encontrada. Inserindo dados com append...")
        # Adiciona 'professores' à verificação de duplicatas
        if table_name in ["materias", "turmas", "professores"]:
            insert_without_duplicates(df, engine, table_name)
        else:
            if not df.empty:
                df.to_sql(table_name, con=engine, if_exists='append', index=index)
                logger.info(f"{len(df)} registros inseridos em '{table_name}'.")
            else:
                logger.info(f"Nenhum registro novo para inserir na tabela '{table_name}'.")
    else:
        logger.info(f"Tabela '{table_name}' não encontrada. Criando a tabela com replace...")
        df.to_sql(table_name, con=engine, if_exists='replace', index=index)

    logger.info(f"Dados enviados para a tabela '{table_name}' com sucesso!\n")


def insert_without_duplicates(df, engine, table_name):
    """
    Insere registros sem duplicatas no banco de dados.
    :param df: DataFrame a ser inserido
    :param table_name: Nome da tabela no banco
    :param engine: Conexão SQLAlchemy
    """
    # Mapeamento correto das colunas a serem verificadas
    if table_name == "materias":
        column = "disciplina"  # Compara pelo nome da disciplina
    elif table_name == "turmas":
        column = "turma_id"
    elif table_name == "professores":
        column = "professor_id"
    else:
        raise ValueError("Tabela não suportada para remoção de duplicatas.")

    if df.empty:
        logger.info(f"Nenhum registro novo para inserir na tabela '{table_name}'.")
        return

    try:
        db_columns = pd.read_sql(f"SELECT {column} FROM {table_name}", con=engine)
        # Converte a coluna do banco para string para uma comparação segura
        db_columns[column] = db_columns[column].astype(str)
    except Exception as e:
        logger.info(f"Erro ao carregar dados existentes de '{table_name}': {e}")
        db_columns = pd.DataFrame(columns=[column])

    df[column] = df[column].astype(str)
    insert_df = df[~df[column].isin(db_columns[column])]

    if not insert_df.empty:
        logger.info(f"Inserindo {len(insert_df)} novos registros na tabela '{table_name}'...")
        insert_df.to_sql(table_name, con=engine, if_exists='append', index=False)
    else:
        logger.info(f"Nenhum registro novo para inserir na tabela '{table_name}'.")