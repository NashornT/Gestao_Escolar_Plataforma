import pandas as pd
from io import BytesIO

from sqlalchemy import create_engine
from storage.db_keys import user, password, host, port, database


def download_school_data():


    # Conexão com o banco de dados
    engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4')

    # Consulta os dados do aluno no banco
    query = f"""
        SELECT a.aluno, m.disciplina, a.turno, a.nivel_escolar, a.total_faltas, a.ano_escolar, 
               n.primeiro_bimestre_nota, n.primeiro_bimestre_nota_recuperacao,
               n.segundo_bimestre_nota, n.segundo_bimestre_nota_recuperacao,
               n.terceiro_bimestre_nota, n.terceiro_bimestre_nota_recuperacao,
               n.quarto_bimestre_nota, n.quarto_bimestre_nota_recuperacao,
               n.media_notas, n.total_notas
        FROM alunos a
        JOIN notas n ON a.aluno_id = n.aluno_id
        JOIN materias m ON n.disciplina_id = m.disciplina_id
        """
    df = pd.read_sql(query, con=engine)

    if df.empty:
        return None, "Nenhum dado encontrado para exportar."

    # Gera o arquivo Excel com o histórico
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Histórico')
    output.seek(0)

    return output, None