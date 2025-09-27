from flask import Blueprint, render_template, flash, redirect, url_for, current_app, send_from_directory, send_file, \
    jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc

from app import db, logger, aluno_table, professor_table
from app import (anuncio_table, material_aula_table, alunos_turma_table, turma_table, disciplina_table, nota_table,
                 comentario_anuncio_table, professores_turmas_disciplinas_table)
from sqlalchemy.sql import select, join
from io import BytesIO
from fpdf import FPDF
import os


aluno_bp = Blueprint('aluno', __name__, url_prefix='/aluno', template_folder='../templates/aluno')


@aluno_bp.before_request
@login_required
def check_student_permission():
    if current_user.role != 'student':
        flash('Acesso negado. Esta área é restrita a alunos.', 'danger')
        return redirect(url_for('main_bp.get_files'))


@aluno_bp.route('/painel')
def painel():
    anuncios_data = []
    materiais_turma = []
    info_turma_aluno = None
    academic_engine = db.get_engine(bind='academic')

    with academic_engine.connect() as connection:
        aluno_id_logado = current_user.aluno_id
        if aluno_id_logado:
            j_turma = join(aluno_table, alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
            j_turma = join(j_turma, turma_table, alunos_turma_table.c.turma_id == turma_table.c.turma_id)
            query_info = select(
                aluno_table.c.aluno,
                turma_table.c.turma,
                turma_table.c.turno,
                alunos_turma_table.c.turma_id
            ).select_from(j_turma).where(aluno_table.c.aluno_id == aluno_id_logado)
            info_aluno = connection.execute(query_info).first()

            # ===== INÍCIO DA CORREÇÃO =====
            # 2. Se o aluno pertence a uma turma, busca os materiais correspondentes
            if info_aluno and info_aluno.turma_id:
                j_materiais = join(material_aula_table, disciplina_table,
                                   material_aula_table.c.disciplina_id == disciplina_table.c.disciplina_id)
                j_materiais = join(j_materiais, professor_table,
                                   material_aula_table.c.professor_id == professor_table.c.professor_id)

                query_materiais = select(
                    material_aula_table,
                    disciplina_table.c.disciplina,
                    professor_table.c.nome.label('nome_professor')
                ).select_from(j_materiais).where(
                    material_aula_table.c.turma_id == info_aluno.turma_id
                ).order_by(desc(material_aula_table.c.data_upload))

                materiais_turma = connection.execute(query_materiais).all()
            # ===== FIM DA CORREÇÃO =====

            # 3. Busca os anúncios (lógica existente)
            j_anuncios = join(anuncio_table, professor_table,
                              anuncio_table.c.professor_id == professor_table.c.professor_id)
            query_anuncios = select(
                anuncio_table,
                professor_table.c.nome.label('nome_professor')
            ).select_from(j_anuncios).order_by(desc(anuncio_table.c.data_postagem))
            anuncios_publicados = connection.execute(query_anuncios).all()

            for anuncio in anuncios_publicados:
                query_comentarios = select(comentario_anuncio_table).where(
                    comentario_anuncio_table.c.anuncio_id == anuncio.anuncio_id
                ).order_by(comentario_anuncio_table.c.data_comentario.asc())
                comentarios = connection.execute(query_comentarios).all()
                anuncios_data.append({'anuncio': anuncio, 'comentarios': comentarios})

        return render_template(
            'aluno/painel.html',
            username=current_user.username,
            user_role=current_user.role,
            anuncios_data=anuncios_data,
            materiais=materiais_turma,
            dados_aluno=info_aluno
        )


@aluno_bp.route('/materiais/<path:filename>')
@login_required
def download_material(filename):
    materiais_directory = os.path.join(current_app.root_path, '..', 'uploads', 'materiais')
    return send_from_directory(directory=materiais_directory, path=filename)


@aluno_bp.route('/minhas-notas')
@login_required
def minhas_notas():
    """
    Busca e exibe o boletim completo do aluno logado.
    """
    boletim_aluno = []
    academic_engine = db.get_engine(bind='academic')
    aluno_id_logado = current_user.aluno_id

    if aluno_id_logado:
        with academic_engine.connect() as connection:
            # Query que junta as tabelas de notas e matérias para obter os nomes
            j = join(nota_table, disciplina_table, nota_table.c.disciplina_id == disciplina_table.c.disciplina_id)

            query_boletim = select(
                nota_table,
                disciplina_table.c.disciplina
            ).select_from(j).where(
                nota_table.c.aluno_id == aluno_id_logado
            ).order_by(disciplina_table.c.disciplina)

            boletim_aluno = connection.execute(query_boletim).all()

    return render_template(
        'minhas_notas.html',
        username=current_user.username,
        boletim=boletim_aluno
    )

class PDF(FPDF):
    def header(self):
        # Define o logo ou título do cabeçalho
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Boletim de Desempenho Escolar', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        # Define o rodapé
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def print_student_info(self, student_name, turma_info):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, f'Aluno: {student_name}', 0, 1, 'L')
        if turma_info:
            self.cell(0, 10, f"Turma: {turma_info.turma} - {turma_info.turno}", 0, 1, 'L')
        self.ln(5)

    def create_grades_table(self, data):
        self.set_font('Arial', 'B', 10)
        col_widths = {'disciplina': 70, 'b1': 20, 'b2': 20, 'b3': 20, 'b4': 20, 'media': 20, 'faltas': 20}

        # Cabeçalho da Tabela
        self.cell(col_widths['disciplina'], 7, 'Disciplina', 1, 0, 'C')
        self.cell(col_widths['b1'], 7, '1º Bim', 1, 0, 'C')
        self.cell(col_widths['b2'], 7, '2º Bim', 1, 0, 'C')
        self.cell(col_widths['b3'], 7, '3º Bim', 1, 0, 'C')
        self.cell(col_widths['b4'], 7, '4º Bim', 1, 0, 'C')
        self.cell(col_widths['media'], 7, 'Média', 1, 0, 'C')
        self.cell(col_widths['faltas'], 7, 'Faltas', 1, 1, 'C')

        # Corpo da Tabela
        self.set_font('Arial', '', 10)
        for row in data:
            self.cell(col_widths['disciplina'], 6, str(row['disciplina']), 1)
            self.cell(col_widths['b1'], 6, str(row['nota_1']), 1, 0, 'C')
            self.cell(col_widths['b2'], 6, str(row['nota_2']), 1, 0, 'C')
            self.cell(col_widths['b3'], 6, str(row['nota_3']), 1, 0, 'C')
            self.cell(col_widths['b4'], 6, str(row['nota_4']), 1, 0, 'C')
            self.cell(col_widths['media'], 6, str(row['media_final']), 1, 0, 'C')
            self.cell(col_widths['faltas'], 6, str(row['total_faltas']), 1, 1, 'C')


@aluno_bp.route('/exportar-boletim-pdf')
@login_required
def exportar_boletim_pdf():
    academic_engine = db.get_engine(bind='academic')
    aluno_id_logado = current_user.aluno_id

    with academic_engine.connect() as connection:
        # Busca as notas e nome da disciplina
        j_notas = join(nota_table, disciplina_table, nota_table.c.disciplina_id == disciplina_table.c.disciplina_id)
        query_boletim = select(
            nota_table, disciplina_table.c.disciplina
        ).select_from(j_notas).where(
            nota_table.c.aluno_id == aluno_id_logado
        ).order_by(disciplina_table.c.disciplina)
        boletim_aluno = connection.execute(query_boletim).mappings().all()

        # Busca informações da turma do aluno
        j_turma = join(alunos_turma_table, turma_table, alunos_turma_table.c.turma_id == turma_table.c.turma_id)
        query_turma = select(turma_table).select_from(j_turma).where(alunos_turma_table.c.aluno_id == aluno_id_logado)
        turma_info = connection.execute(query_turma).first()

    if not boletim_aluno:
        flash('Não há notas para gerar o boletim.', 'warning')
        return redirect(url_for('aluno.minhas_notas'))

    pdf = PDF()
    pdf.add_page()
    pdf.print_student_info(current_user.username, turma_info)

    dados_tabela = []
    for nota in boletim_aluno:
        dados_tabela.append({
            'disciplina': nota.disciplina,
            'nota_1': round(nota.nota_1_bimestre_final, 1) if nota.nota_1_bimestre_final is not None else '-',
            'nota_2': round(nota.nota_2_bimestre_final, 1) if nota.nota_2_bimestre_final is not None else '-',
            'nota_3': round(nota.nota_3_bimestre_final, 1) if nota.nota_3_bimestre_final is not None else '-',
            'nota_4': round(nota.nota_4_bimestre_final, 1) if nota.nota_4_bimestre_final is not None else '-',
            'media_final': round(nota.media_final, 1) if nota.media_final is not None else '-',
            'total_faltas': int(nota.total_faltas) if nota.total_faltas is not None else '-'
        })

    pdf.create_grades_table(dados_tabela)

    pdf_output = pdf.output(dest='S')
    buffer = BytesIO(pdf_output)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'boletim_{current_user.username}.pdf',
        mimetype='application/pdf'
    )


@aluno_bp.route('/api/desempenho_pessoal')
@login_required
def api_desempenho_pessoal():
    """
    Retorna os dados de desempenho do aluno logado para o gráfico.
    """
    aluno_id_logado = current_user.aluno_id
    if not aluno_id_logado:
        return jsonify({'error': 'ID do aluno não encontrado.'}), 404

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        j = join(nota_table, disciplina_table, nota_table.c.disciplina_id == disciplina_table.c.disciplina_id)
        query_desempenho = select(
            disciplina_table.c.disciplina,
            nota_table.c.media_final
        ).select_from(j).where(
            nota_table.c.aluno_id == aluno_id_logado,
            nota_table.c.media_final.isnot(None)
        ).order_by(disciplina_table.c.disciplina)

        resultados = connection.execute(query_desempenho).mappings().all()

        # Prepara os dados para o gráfico
        labels = [row['disciplina'] for row in resultados]
        data = [round(row['media_final'], 1) for row in resultados]

    return jsonify({'labels': labels, 'data': data})