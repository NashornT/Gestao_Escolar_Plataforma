from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy.sql import select, update, insert, join, distinct
from app import db, logger
from app import turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table, \
    professores_turmas_disciplinas_table, anuncio_table, material_aula_table
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
import os

professor_bp = Blueprint('professor_bp', __name__, url_prefix='/professor')


@professor_bp.before_request
@login_required
def check_professor_permission():
    if not (current_user.is_professor or current_user.is_admin):
        flash('Acesso negado. Esta área é restrita a professores e administradores.', 'danger')
        return redirect(url_for('main_bp.get_files'))


@professor_bp.route('/notas')
def gerenciar_notas():
    professor_id_logado = current_user.professor_id
    turmas_atribuidas = []
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        if professor_id_logado:
            join_turmas = join(turma_table, professores_turmas_disciplinas_table,
                               turma_table.c.turma_id == professores_turmas_disciplinas_table.c.turma_id)
            query_turmas = select(
                distinct(turma_table.c.turma_id),
                turma_table.c.turma,
                turma_table.c.turno
            ).select_from(join_turmas).where(
                professores_turmas_disciplinas_table.c.professor_id == professor_id_logado
            ).order_by(turma_table.c.turma, turma_table.c.turno)
            turmas_atribuidas = connection.execute(query_turmas).all()
    return render_template(
        'professor/notas.html',
        turmas=turmas_atribuidas,
        username=current_user.username,
        user_role=current_user.role
    )


@professor_bp.route('/api/disciplinas_por_turma')
@login_required
def api_disciplinas_por_turma():
    turma_id = request.args.get('turma_id')
    professor_id_logado = current_user.professor_id
    if not turma_id or not professor_id_logado:
        return jsonify({'error': 'IDs de Turma e Professor são obrigatórios'}), 400
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        join_disciplinas = join(disciplina_table, professores_turmas_disciplinas_table,
                                disciplina_table.c.disciplina_id == professores_turmas_disciplinas_table.c.disciplina_id)
        query_disciplinas = select(
            disciplina_table.c.disciplina_id,
            disciplina_table.c.disciplina
        ).select_from(join_disciplinas).where(
            professores_turmas_disciplinas_table.c.professor_id == professor_id_logado,
            professores_turmas_disciplinas_table.c.turma_id == turma_id
        ).order_by(disciplina_table.c.disciplina)
        resultados = connection.execute(query_disciplinas).mappings().all()
        disciplinas_serializaveis = [dict(row) for row in resultados]
        return jsonify(disciplinas_serializaveis)


@professor_bp.route('/api/dados_turma')
@login_required
def api_dados_turma():
    turma_id = request.args.get('turma_id')
    disciplina_id = request.args.get('disciplina_id', type=int)
    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    dados_formatados = []
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            query_ano_letivo = select(turma_table.c.ano_escolar).where(turma_table.c.turma_id == turma_id)
            ano_letivo = connection.execute(query_ano_letivo).scalar_one_or_none() or str(datetime.now().year)

            j = join(aluno_table, alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
            query_alunos = select(aluno_table.c.aluno_id, aluno_table.c.aluno).select_from(j).where(
                alunos_turma_table.c.turma_id == turma_id).order_by(aluno_table.c.aluno)
            alunos = connection.execute(query_alunos).all()

            novas_notas_para_inserir = []
            for aluno in alunos:
                query_nota = select(nota_table).where(
                    nota_table.c.aluno_id == aluno.aluno_id,
                    nota_table.c.disciplina_id == disciplina_id
                )
                registro_nota = connection.execute(query_nota).first()
                if registro_nota:
                    notas_aluno = {
                        'nota_id': registro_nota.nota_id,
                        'bimestres': {'b1': {'valor': registro_nota.nota_1_bimestre},
                                      'b2': {'valor': registro_nota.nota_2_bimestre},
                                      'b3': {'valor': registro_nota.nota_3_bimestre},
                                      'b4': {'valor': registro_nota.nota_4_bimestre}},
                        'total_faltas': registro_nota.total_faltas
                    }
                else:
                    novo_nota_id = str(uuid.uuid4())
                    novas_notas_para_inserir.append({
                        'nota_id': novo_nota_id, 'aluno_id': aluno.aluno_id, 'disciplina_id': disciplina_id,
                        'ano_letivo': ano_letivo
                    })
                    notas_aluno = {
                        'nota_id': novo_nota_id,
                        'bimestres': {'b1': {'valor': ''}, 'b2': {'valor': ''}, 'b3': {'valor': ''},
                                      'b4': {'valor': ''}},
                        'total_faltas': ''
                    }
                dados_formatados.append({'id': aluno.aluno_id, 'nome': aluno.aluno, 'dados_nota': notas_aluno})

            if novas_notas_para_inserir:
                connection.execute(insert(nota_table), novas_notas_para_inserir)

            trans.commit()
        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao buscar dados da turma: {e}", exc_info=True)
            return jsonify({'error': 'Ocorreu um erro interno no servidor ao buscar dados dos alunos.'}), 500
    return jsonify(dados_formatados)


@professor_bp.route('/api/atualizar_dados', methods=['POST'])
@login_required
def api_atualizar_dados():
    data = request.get_json()
    if not data or 'dados' not in data:
        return jsonify({'success': False, 'message': 'Requisição inválida.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            for item in data['dados']:
                nota_id = item.get('nota_id')
                campo = item.get('campo')
                valor_str = item.get('valor')
                valor = None
                if valor_str not in [None, '']:
                    numeric_value = float(valor_str)
                    if 'nota' in campo:
                        if not (0 <= numeric_value <= 10):
                            raise ValueError("A nota deve estar entre 0 e 10.")
                        valor = numeric_value
                    else:
                        if numeric_value < 0:
                            raise ValueError("O número de faltas não pode ser negativo.")
                        valor = int(numeric_value)
                stmt = update(nota_table).where(nota_table.c.nota_id == nota_id).values({campo: valor})
                connection.execute(stmt)
            trans.commit()
            return jsonify({'success': True, 'message': 'Dados atualizados com sucesso!'})
        except Exception as e:
            trans.rollback()
            logger.error(f"Erro de banco de dados ao atualizar: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Ocorreu um erro: {str(e)}'}), 500


@professor_bp.route('/anuncios', methods=['GET', 'POST'])
@login_required
def gerenciar_anuncios():
    academic_engine = db.get_engine(bind='academic')

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        conteudo = request.form.get('conteudo')
        professor_id = current_user.professor_id

        if not titulo or not conteudo:
            flash('Título e conteúdo são obrigatórios.', 'danger')
        else:
            with academic_engine.connect() as connection:
                trans = connection.begin()
                try:
                    stmt = insert(anuncio_table).values(
                        professor_id=professor_id,
                        titulo=titulo,
                        conteudo=conteudo,
                        data_postagem=datetime.now()
                    )
                    connection.execute(stmt)
                    trans.commit()
                    flash('Anúncio publicado com sucesso!', 'success')
                    return redirect(url_for('professor_bp.gerenciar_anuncios'))
                except Exception as e:
                    trans.rollback()
                    flash(f'Erro ao publicar anúncio: {e}', 'danger')

    # Para requisições GET, busca os anúncios existentes para exibi-los
    anuncios_publicados = []
    with academic_engine.connect() as connection:
        query = select(anuncio_table).where(anuncio_table.c.professor_id == current_user.professor_id).order_by(
            anuncio_table.c.data_postagem.desc())
        anuncios_publicados = connection.execute(query).all()

    return render_template(
        'professor/anuncios.html',
        username=current_user.username,
        user_role=current_user.role,
        anuncios=anuncios_publicados
    )


@professor_bp.route('/materiais', methods=['GET', 'POST'])
@login_required
def gerenciar_materiais():
    # ===== INÍCIO DA CORREÇÃO =====
    # Verifica se as tabelas essenciais foram carregadas. Se não, mostra um erro claro.
    if material_aula_table is None or turma_table is None or disciplina_table is None:
        flash(
            'Erro crítico: Uma ou mais tabelas acadêmicas não foram encontradas no banco de dados. Verifique a conexão e os nomes das tabelas.',
            'danger')
        return redirect(url_for('main_bp.get_files'))
    # ===== FIM DA CORREÇÃO =====

    professor_id_logado = current_user.professor_id
    academic_engine = db.get_engine(bind='academic')

    with academic_engine.connect() as connection:
        join_turmas = join(turma_table, professores_turmas_disciplinas_table,
                           turma_table.c.turma_id == professores_turmas_disciplinas_table.c.turma_id)
        query_turmas = select(
            distinct(turma_table.c.turma_id),
            turma_table.c.turma,
            turma_table.c.turno
        ).select_from(join_turmas).where(
            professores_turmas_disciplinas_table.c.professor_id == professor_id_logado
        ).order_by(turma_table.c.turma, turma_table.c.turno)
        turmas_atribuidas = connection.execute(query_turmas).all()

    if request.method == 'POST':
        turma_id = request.form.get('turma_id')
        disciplina_id = request.form.get('disciplina_id')
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        arquivo = request.files.get('arquivo')

        if not all([turma_id, disciplina_id, titulo, arquivo]):
            flash('Todos os campos, incluindo o arquivo, são obrigatórios.', 'danger')
        else:
            filename = secure_filename(arquivo.filename)
            upload_path = os.path.join('uploads', 'materiais')
            os.makedirs(upload_path, exist_ok=True)
            arquivo.save(os.path.join(upload_path, filename))

            with academic_engine.connect() as connection:
                trans = connection.begin()
                try:
                    stmt = insert(material_aula_table).values(
                        professor_id=professor_id_logado,
                        turma_id=turma_id,
                        disciplina_id=disciplina_id,
                        titulo=titulo,
                        descricao=descricao,
                        link_arquivo=filename,
                        data_upload=datetime.now()
                    )
                    connection.execute(stmt)
                    trans.commit()
                    flash('Material enviado com sucesso!', 'success')
                    return redirect(url_for('professor_bp.gerenciar_materiais'))
                except Exception as e:
                    trans.rollback()
                    flash(f'Erro ao enviar material: {e}', 'danger')

    materiais_enviados = []
    with academic_engine.connect() as connection:
        j = join(material_aula_table, turma_table, material_aula_table.c.turma_id == turma_table.c.turma_id)
        j = join(j, disciplina_table, material_aula_table.c.disciplina_id == disciplina_table.c.disciplina_id)
        query_materiais = select(
            material_aula_table, turma_table.c.turma, disciplina_table.c.disciplina
        ).select_from(j).where(
            material_aula_table.c.professor_id == professor_id_logado
        ).order_by(material_aula_table.c.data_upload.desc())
        materiais_enviados = connection.execute(query_materiais).all()

    return render_template(
        'professor/materiais.html',
        username=current_user.username,
        user_role=current_user.role,
        turmas=turmas_atribuidas,
        materiais=materiais_enviados
    )


@professor_bp.route('/materiais/<path:filename>')
@login_required
def download_material(filename):
    """
    Rota segura para servir os arquivos da pasta de uploads de materiais.
    """
    materiais_directory = os.path.join(current_app.root_path, '..', 'uploads', 'materiais')
    return send_from_directory(directory=materiais_directory, path=filename)


@professor_bp.route('/materiais/excluir/<int:material_id>', methods=['POST'])
@login_required
def excluir_material(material_id):
    professor_id_logado = current_user.professor_id
    academic_engine = db.get_engine(bind='academic')

    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            query_material = select(material_aula_table).where(material_aula_table.c.material_id == material_id)
            material = connection.execute(query_material).first()

            if not material:
                flash('Material não encontrado.', 'danger')
                return redirect(url_for('professor_bp.gerenciar_materiais'))

            if material.professor_id != professor_id_logado:
                flash('Você não tem permissão para excluir este material.', 'danger')
                return redirect(url_for('professor_bp.gerenciar_materiais'))

            if material.link_arquivo:
                caminho_arquivo = os.path.join('uploads', 'materiais', material.link_arquivo)
                if os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)

            stmt = material_aula_table.delete().where(material_aula_table.c.material_id == material_id)
            connection.execute(stmt)

            trans.commit()
            flash('Material removido com sucesso!', 'success')

        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao excluir material: {e}", exc_info=True)
            flash(f'Erro ao remover material: {e}', 'danger')

    return redirect(url_for('professor_bp.gerenciar_materiais'))