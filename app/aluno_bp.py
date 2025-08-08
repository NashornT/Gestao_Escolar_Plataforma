from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app import anuncio_table, material_aula_table, alunos_turma_table, turma_table, disciplina_table
from sqlalchemy.sql import select, join

aluno_bp = Blueprint('aluno', __name__, url_prefix='/aluno', template_folder='../templates/aluno')


@aluno_bp.before_request
@login_required
def check_student_permission():
    if current_user.role != 'student':
        flash('Acesso negado. Esta área é restrita a alunos.', 'danger')
        return redirect(url_for('main_bp.get_files'))


@aluno_bp.route('/painel')
def painel():
    """Exibe o painel principal do aluno com anúncios e materiais."""

    anuncios_gerais = []
    materiais_turma = []
    academic_engine = db.get_engine(bind='academic')

    with academic_engine.connect() as connection:
        # 1. Busca todos os anúncios, ordenados pelo mais recente
        query_anuncios = select(anuncio_table).order_by(anuncio_table.c.data_postagem.desc())
        anuncios_gerais = connection.execute(query_anuncios).all()

        # 2. Busca a turma do aluno logado
        aluno_id_logado = current_user.aluno_id
        if aluno_id_logado:
            query_turma_aluno = select(alunos_turma_table.c.turma_id).where(
                alunos_turma_table.c.aluno_id == aluno_id_logado)
            resultado_turma = connection.execute(query_turma_aluno).first()

            if resultado_turma:
                turma_id_aluno = resultado_turma[0]

                # 3. Busca os materiais apenas da turma do aluno
                j = join(material_aula_table, turma_table, material_aula_table.c.turma_id == turma_table.c.turma_id)
                j = join(j, disciplina_table, material_aula_table.c.disciplina_id == disciplina_table.c.disciplina_id)

                query_materiais = select(
                    material_aula_table,
                    turma_table.c.turma,
                    disciplina_table.c.disciplina
                ).select_from(j).where(
                    material_aula_table.c.turma_id == turma_id_aluno
                ).order_by(material_aula_table.c.data_upload.desc())

                materiais_turma = connection.execute(query_materiais).all()

    return render_template(
        'painel.html',
        username=current_user.username,
        anuncios=anuncios_gerais,
        materiais=materiais_turma
    )