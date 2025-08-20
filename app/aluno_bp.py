from flask import Blueprint, render_template, flash, redirect, url_for, current_app, send_from_directory
from flask_login import login_required, current_user
from app import db, logger
from app import (anuncio_table, material_aula_table, alunos_turma_table, turma_table, disciplina_table, nota_table,
                 comentario_anuncio_table)
from sqlalchemy.sql import select, join
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

        # 1. Busca todos os anúncios e seus comentários de uma vez usando LEFT JOIN
        j = anuncio_table.outerjoin(
            comentario_anuncio_table,
            anuncio_table.c.anuncio_id == comentario_anuncio_table.c.anuncio_id
        )

        query = select(
            anuncio_table,
            comentario_anuncio_table
        ).select_from(j).order_by(
            anuncio_table.c.data_postagem.desc(),
            comentario_anuncio_table.c.data_comentario.asc()
        )

        resultados = connection.execute(query).mappings().all()

        # 2. Organiza os resultados em uma estrutura aninhada (anúncios com seus comentários)
        anuncios_dict = {}
        for row in resultados:
            anuncio_id = row['anuncio_id']
            if anuncio_id not in anuncios_dict:
                anuncios_dict[anuncio_id] = {
                    'anuncio': {
                        'anuncio_id': row['anuncio_id'],
                        'titulo': row['titulo'],
                        'conteudo': row['conteudo'],
                        'data_postagem': row['data_postagem']
                    },
                    'comentarios': []
                }

            # Adiciona o comentário se ele existir (devido ao LEFT JOIN, pode ser nulo)
            if row['comentario_id'] is not None:
                anuncios_dict[anuncio_id]['comentarios'].append({
                    'nome_usuario': row['nome_usuario'],
                    'conteudo': row['comentarios_anuncios_conteudo'],
                    'data_comentario': row['data_comentario']
                })

        anuncios_data = list(anuncios_dict.values())

        # A lógica para buscar materiais continua a mesma
        aluno_id_logado = current_user.aluno_id
        if aluno_id_logado:
            query_turma_aluno = select(alunos_turma_table.c.turma_id).where(
                alunos_turma_table.c.aluno_id == aluno_id_logado)
            resultado_turma = connection.execute(query_turma_aluno).first()

            if resultado_turma:
                turma_id_aluno = resultado_turma.turma_id

                query_info_turma = select(turma_table).where(turma_table.c.turma_id == turma_id_aluno)
                info_turma_aluno = connection.execute(query_info_turma).first()

                j_materiais = join(material_aula_table, disciplina_table,
                                   material_aula_table.c.disciplina_id == disciplina_table.c.disciplina_id)
                query_materiais = select(
                    material_aula_table,
                    disciplina_table.c.disciplina
                ).select_from(j_materiais).where(
                    material_aula_table.c.turma_id == turma_id_aluno
                ).order_by(material_aula_table.c.data_upload.desc())

                materiais_turma = connection.execute(query_materiais).all()

    return render_template(
        'painel.html',
        username=current_user.username,
        anuncios_data=anuncios_data,
        materiais=materiais_turma,
        turma_info=info_turma_aluno
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