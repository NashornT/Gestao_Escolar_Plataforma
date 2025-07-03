import pandas as pd
from io import BytesIO

from sqlalchemy import create_engine
from storage.db_keys import user, password, host, port, database


def download_school_data():
    # Conexão com o banco de dados
    engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4')

    # Consulta os dados no banco
    query = f"""
        SELECT a.aluno, n.total_faltas, t.ano_escolar, t.turma, t.turno,
               m.disciplina,
               n.nota_1_bimestre, n.nota_1_bimestre_recuperacao, n.nota_1_bimestre_final,
               n.nota_2_bimestre, n.nota_2_bimestre_recuperacao, n.nota_2_bimestre_final,
               n.nota_3_bimestre, n.nota_3_bimestre_recuperacao, n.nota_3_bimestre_final,
               n.nota_4_bimestre, n.nota_4_bimestre_recuperacao, n.nota_4_bimestre_final,
               n.nota_total, n.media_final
        FROM alunos a
        JOIN notas n ON a.aluno_id = n.aluno_id
        JOIN alunos_turma at ON a.aluno_id = at.aluno_id
        JOIN turmas t ON at.turma_id = t.turma_id
        JOIN materias m ON n.disciplina_id = m.disciplina_id
    """
    df = pd.read_sql(query, con=engine)

    if df.empty:
        return None, "Nenhum dado encontrado para exportar."

    # Gera o arquivo Excel com os dados
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados Escolares')
    output.seek(0)

    return output, None