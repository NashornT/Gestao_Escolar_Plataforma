from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy.sql import select, update, insert, join, distinct
from app import db, logger
from app import (turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table, \
    professores_turmas_disciplinas_table, anuncio_table, material_aula_table, comentario_anuncio_table,
                 notificacao_table, socketio, diario_de_classe_table, presenca_table)
from datetime import datetime
from werkzeug.utils import secure_filename
from app.models import User
from app.audit_log import log_action
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
                        'bimestres': {
                            'b1': {'valor': registro_nota.nota_1_bimestre_final},
                            'b2': {'valor': registro_nota.nota_2_bimestre_final},
                            'b3': {'valor': registro_nota.nota_3_bimestre_final},
                            'b4': {'valor': registro_nota.nota_4_bimestre_final}
                        },
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
            return jsonify({'error': 'Ocorreu um erro interno no servidor.'}), 500
    return jsonify(dados_formatados)


@professor_bp.route('/api/atualizar_dados', methods=['POST'])
@login_required
def api_atualizar_dados():
    data = request.get_json()
    if not data or 'dados' not in data:
        return jsonify({'success': False, 'message': 'Requisição inválida.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        updates_por_nota = {}
        for item in data['dados']:
            nota_id = item.get('nota_id')
            if nota_id not in updates_por_nota:
                updates_por_nota[nota_id] = {}
            updates_por_nota[nota_id][item.get('campo')] = item.get('valor')

        trans = connection.begin()
        try:
            for nota_id, campos_para_atualizar in updates_por_nota.items():
                registro_atual = connection.execute(
                    select(nota_table).where(nota_table.c.nota_id == nota_id)
                ).first()
                if not registro_atual:
                    continue

                old_values = {
                    "nota_1_bimestre_final": registro_atual.get('nota_1_bimestre_final'),
                    "nota_2_bimestre_final": registro_atual.get('nota_2_bimestre_final'),
                    "nota_3_bimestre_final": registro_atual.get('nota_3_bimestre_final'),
                    "nota_4_bimestre_final": registro_atual.get('nota_4_bimestre_final'),
                    "total_faltas": registro_atual.get('total_faltas')
                }

                valores_finais = dict(registro_atual)

                for campo, valor_str in campos_para_atualizar.items():
                    valor = None
                    if valor_str not in [None, '']:
                        numeric_value = float(str(valor_str).replace(',', '.'))
                        if 'nota' in campo:
                            if not (0 <= numeric_value <= 10):
                                raise ValueError(f"A nota '{numeric_value}' deve estar entre 0 e 10.")
                            valor = numeric_value
                        else:
                            if numeric_value < 0:
                                raise ValueError("O número de faltas não pode ser negativo.")
                            valor = int(numeric_value)
                    valores_finais[campo] = valor

                notas_validas = [n for n in [
                    valores_finais['nota_1_bimestre_final'], valores_finais['nota_2_bimestre_final'],
                    valores_finais['nota_3_bimestre_final'], valores_finais['nota_4_bimestre_final']
                ] if n is not None]

                nota_total = sum(notas_validas)
                media_final = nota_total / len(notas_validas) if notas_validas else 0

                valores_finais['nota_total'] = nota_total
                valores_finais['media_final'] = round(media_final, 2)

                stmt = update(nota_table).where(nota_table.c.nota_id == nota_id).values(valores_finais)
                connection.execute(stmt)

                log_action(
                    action='UPDATE',
                    table_affected='notas',
                    record_id=nota_id,
                    old_value=old_values,
                    new_value={k: valores_finais[k] for k in old_values.keys()}
                )

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

        if not titulo or not conteudo:
            flash('Título e conteúdo são obrigatórios.', 'danger')
            return redirect(url_for('professor_bp.gerenciar_anuncios'))

        with academic_engine.connect() as conn_academic:
            trans_academic = conn_academic.begin()
            try:
                stmt_anuncio = insert(anuncio_table).values(
                    professor_id=current_user.professor_id,
                    titulo=titulo,
                    conteudo=conteudo,
                    data_postagem=datetime.now()
                )
                result = conn_academic.execute(stmt_anuncio)

                novo_anuncio_id = result.inserted_primary_key[0]
                log_action(
                    action='CREATE',
                    table_affected='anuncios',
                    record_id=novo_anuncio_id,
                    new_value={'titulo': titulo}
                )

                trans_academic.commit()

                alunos = User.query.filter_by(role='student').all()
                if alunos:
                    mensagem = f"Novo anúncio publicado: '{titulo[:30]}...'"
                    link = url_for('aluno.painel')
                    novas_notificacoes = [{'user_id_destino': aluno.id, 'mensagem': mensagem, 'link': link,
                                           'data_criacao': datetime.now()} for aluno in alunos]

                    audit_engine = db.get_engine()
                    with audit_engine.connect() as conn_audit:
                        trans_audit = conn_audit.begin()
                        conn_audit.execute(insert(notificacao_table), novas_notificacoes)
                        trans_audit.commit()

                    for aluno in alunos:
                        socketio.emit('nova_notificacao', {'count': 1}, room=f'user_{aluno.id}')

                flash('Anúncio publicado e alunos notificados!', 'success')
                return redirect(url_for('professor_bp.gerenciar_anuncios'))
            except Exception as e:
                trans_academic.rollback()
                flash(f'Erro ao publicar anúncio: {e}', 'danger')
                return redirect(url_for('professor_bp.gerenciar_anuncios'))

    anuncios_com_comentarios = []
    with academic_engine.connect() as connection:
        query_anuncios = select(anuncio_table).where(
            anuncio_table.c.professor_id == current_user.professor_id).order_by(anuncio_table.c.data_postagem.desc())
        anuncios_publicados = connection.execute(query_anuncios).all()

        for anuncio in anuncios_publicados:
            query_comentarios = select(comentario_anuncio_table).where(
                comentario_anuncio_table.c.anuncio_id == anuncio.anuncio_id
            ).order_by(comentario_anuncio_table.c.data_comentario.asc())
            comentarios = connection.execute(query_comentarios).all()
            anuncios_com_comentarios.append({'anuncio': anuncio, 'comentarios': comentarios})

    return render_template(
        'professor/anuncios.html',
        username=current_user.username,
        user_role=current_user.role,
        anuncios_data=anuncios_com_comentarios
    )

@professor_bp.route('/materiais', methods=['GET', 'POST'])
@login_required
def gerenciar_materiais():
    if material_aula_table is None or turma_table is None or disciplina_table is None:
        flash(
            'Erro crítico: Uma ou mais tabelas acadêmicas não foram encontradas no banco de dados. Verifique a conexão e os nomes das tabelas.',
            'danger')
        return redirect(url_for('main_bp.get_files'))

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


@professor_bp.route('/anuncios/excluir/<int:anuncio_id>', methods=['POST'])
@login_required
def excluir_anuncio(anuncio_id):
    professor_id_logado = current_user.professor_id
    academic_engine = db.get_engine(bind='academic')

    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            query_anuncio = select(anuncio_table).where(
                anuncio_table.c.anuncio_id == anuncio_id,
                anuncio_table.c.professor_id == professor_id_logado
            )
            anuncio = connection.execute(query_anuncio).first()

            if not anuncio:
                flash('Anúncio não encontrado ou você não tem permissão para excluí-lo.', 'danger')
                return redirect(url_for('professor_bp.gerenciar_anuncios'))

            log_action(
                action='DELETE',
                table_affected='anuncios',
                record_id=anuncio_id,
                old_value={'titulo': anuncio.titulo}
            )

            stmt = anuncio_table.delete().where(anuncio_table.c.anuncio_id == anuncio_id)
            connection.execute(stmt)

            trans.commit()
            flash('Anúncio removido com sucesso!', 'success')

        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao excluir anúncio: {e}", exc_info=True)
            flash(f'Erro ao remover anúncio: {e}', 'danger')

    return redirect(url_for('professor_bp.gerenciar_anuncios'))


@professor_bp.route('/api/anuncio/<int:anuncio_id>')
@login_required
def api_get_anuncio(anuncio_id):
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query = select(anuncio_table).where(
            anuncio_table.c.anuncio_id == anuncio_id,
            anuncio_table.c.professor_id == current_user.professor_id
        )
        anuncio = connection.execute(query).mappings().first()
        if not anuncio:
            return jsonify({'error': 'Anúncio não encontrado ou não autorizado'}), 404
        return jsonify(dict(anuncio))


@professor_bp.route('/anuncios/editar/<int:anuncio_id>', methods=['POST'])
@login_required
def editar_anuncio(anuncio_id):
    titulo = request.form.get('titulo')
    conteudo = request.form.get('conteudo')

    if not titulo or not conteudo:
        flash('Título e conteúdo são obrigatórios.', 'danger')
        return redirect(url_for('professor_bp.gerenciar_anuncios'))

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            query_anuncio_antigo = select(anuncio_table.c.titulo, anuncio_table.c.conteudo).where(
                anuncio_table.c.anuncio_id == anuncio_id,
                anuncio_table.c.professor_id == current_user.professor_id
            )
            anuncio_antigo = connection.execute(query_anuncio_antigo).first()
            if not anuncio_antigo:
                flash('Anúncio não encontrado ou você não tem permissão para editá-lo.', 'danger')
                trans.rollback()
                return redirect(url_for('professor_bp.gerenciar_anuncios'))

            stmt = update(anuncio_table).where(
                anuncio_table.c.anuncio_id == anuncio_id
            ).values(
                titulo=titulo,
                conteudo=conteudo
            )
            connection.execute(stmt)

            log_action(
                action='UPDATE',
                table_affected='anuncios',
                record_id=anuncio_id,
                old_value={'titulo': anuncio_antigo.titulo, 'conteudo': anuncio_antigo.conteudo},
                new_value={'titulo': titulo, 'conteudo': conteudo}
            )

            trans.commit()
            flash('Anúncio atualizado com sucesso!', 'success')

        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao editar anúncio: {e}", exc_info=True)
            flash(f'Erro ao atualizar o anúncio: {e}', 'danger')

    return redirect(url_for('professor_bp.gerenciar_anuncios'))


# ===== NOVAS ROTAS PARA EDIÇÃO DE MATERIAIS =====

@professor_bp.route('/api/material/<int:material_id>')
@login_required
def api_get_material(material_id):
    """Retorna os dados de um material específico em JSON."""
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query = select(material_aula_table).where(
            material_aula_table.c.material_id == material_id,
            material_aula_table.c.professor_id == current_user.professor_id
        )
        material = connection.execute(query).mappings().first()
        if not material:
            return jsonify({'error': 'Material não encontrado ou não autorizado'}), 404
        return jsonify(dict(material))


@professor_bp.route('/materiais/editar/<int:material_id>', methods=['POST'])
@login_required
def editar_material(material_id):
    """Processa a edição dos detalhes de um material."""
    titulo = request.form.get('titulo')
    descricao = request.form.get('descricao')

    if not titulo:
        flash('O título é obrigatório.', 'danger')
        return redirect(url_for('professor_bp.gerenciar_materiais'))

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            query_material_antigo = select(material_aula_table.c.titulo, material_aula_table.c.descricao).where(
                material_aula_table.c.material_id == material_id,
                material_aula_table.c.professor_id == current_user.professor_id
            )
            material_antigo = connection.execute(query_material_antigo).first()
            if not material_antigo:
                flash('Material não encontrado ou você não tem permissão para editá-lo.', 'danger')
                trans.rollback()
                return redirect(url_for('professor_bp.gerenciar_materiais'))

            stmt = update(material_aula_table).where(
                material_aula_table.c.material_id == material_id
            ).values(
                titulo=titulo,
                descricao=descricao
            )
            connection.execute(stmt)

            log_action(
                action='UPDATE',
                table_affected='materiais_aula',
                record_id=material_id,
                old_value={'titulo': material_antigo.titulo, 'descricao': material_antigo.descricao},
                new_value={'titulo': titulo, 'descricao': descricao}
            )

            trans.commit()
            flash('Material atualizado com sucesso!', 'success')

        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao editar material: {e}", exc_info=True)
            flash(f'Erro ao atualizar o material: {e}', 'danger')

    return redirect(url_for('professor_bp.gerenciar_materiais'))

# =======================================================


@professor_bp.route('/api/dados_graficos')
@login_required
def api_dados_graficos():
    turma_id = request.args.get('turma_id')
    disciplina_id = request.args.get('disciplina_id', type=int)

    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        j = join(nota_table, alunos_turma_table, nota_table.c.aluno_id == alunos_turma_table.c.aluno_id)
        query_notas = select(
            nota_table.c.nota_1_bimestre_final,
            nota_table.c.nota_2_bimestre_final,
            nota_table.c.nota_3_bimestre_final,
            nota_table.c.nota_4_bimestre_final
        ).select_from(j).where(
            alunos_turma_table.c.turma_id == turma_id,
            nota_table.c.disciplina_id == disciplina_id
        )

        resultados = connection.execute(query_notas).all()

        if not resultados:
            return jsonify({
                'media_bimestres': [0, 0, 0, 0],
                'distribuicao_notas': [0, 0, 0, 0, 0]
            })

        soma_b1, count_b1 = 0, 0
        soma_b2, count_b2 = 0, 0
        soma_b3, count_b3 = 0, 0
        soma_b4, count_b4 = 0, 0

        for row in resultados:
            if row.nota_1_bimestre_final is not None:
                soma_b1 += row.nota_1_bimestre_final
                count_b1 += 1
            if row.nota_2_bimestre_final is not None:
                soma_b2 += row.nota_2_bimestre_final
                count_b2 += 1
            if row.nota_3_bimestre_final is not None:
                soma_b3 += row.nota_3_bimestre_final
                count_b3 += 1
            if row.nota_4_bimestre_final is not None:
                soma_b4 += row.nota_4_bimestre_final
                count_b4 += 1

        media_b1 = round(soma_b1 / count_b1, 1) if count_b1 > 0 else 0
        media_b2 = round(soma_b2 / count_b2, 1) if count_b2 > 0 else 0
        media_b3 = round(soma_b3 / count_b3, 1) if count_b3 > 0 else 0
        media_b4 = round(soma_b4 / count_b4, 1) if count_b4 > 0 else 0

        query_medias_finais = select(nota_table.c.media_final).select_from(j).where(
            alunos_turma_table.c.turma_id == turma_id,
            nota_table.c.disciplina_id == disciplina_id,
            nota_table.c.media_final.isnot(None)
        )
        medias_finais = connection.execute(query_medias_finais).scalars().all()

        abaixo_de_5 = sum(1 for nota in medias_finais if nota < 5)
        entre_5_e_6_9 = sum(1 for nota in medias_finais if 5 <= nota <= 6.9)
        entre_7_e_8_9 = sum(1 for nota in medias_finais if 7 <= nota <= 8.9)
        acima_de_9 = sum(1 for nota in medias_finais if nota >= 9)

    return jsonify({
        'media_bimestres': [media_b1, media_b2, media_b3, media_b4],
        'distribuicao_notas': [abaixo_de_5, entre_5_e_6_9, entre_7_e_8_9, acima_de_9]
    })



@professor_bp.route('/lancar-nota', methods=['GET'])
@login_required
def lancar_nota_individual_page():
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
        'professor/lancar_nota.html',
        turmas=turmas_atribuidas,
        username=current_user.username,
        user_role=current_user.role
    )


@professor_bp.route('/api/alunos_por_turma')
@login_required
def api_alunos_por_turma():
    turma_id = request.args.get('turma_id')
    if not turma_id:
        return jsonify({'error': 'ID da Turma é obrigatório'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        j = join(aluno_table, alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
        query_alunos = select(
            aluno_table.c.aluno_id,
            aluno_table.c.aluno
        ).select_from(j).where(
            alunos_turma_table.c.turma_id == turma_id
        ).order_by(aluno_table.c.aluno)

        alunos = connection.execute(query_alunos).mappings().all()
        return jsonify([dict(row) for row in alunos])


@professor_bp.route('/api/nota_aluno')
@login_required
def api_nota_aluno():
    aluno_id = request.args.get('aluno_id')
    disciplina_id = request.args.get('disciplina_id')
    if not aluno_id or not disciplina_id:
        return jsonify({'error': 'IDs do Aluno e da Disciplina são obrigatórios'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query_nota = select(nota_table).where(
            nota_table.c.aluno_id == aluno_id,
            nota_table.c.disciplina_id == disciplina_id
        )
        nota = connection.execute(query_nota).mappings().first()

        if not nota:
            turma_id = request.args.get('turma_id')
            query_ano_letivo = select(turma_table.c.ano_escolar).where(turma_table.c.turma_id == turma_id)
            ano_letivo = connection.execute(query_ano_letivo).scalar_one_or_none() or str(datetime.now().year)

            novo_nota_id = str(uuid.uuid4())
            nova_nota = {
                'nota_id': novo_nota_id, 'aluno_id': aluno_id, 'disciplina_id': disciplina_id,
                'ano_letivo': ano_letivo
            }
            connection.execute(insert(nota_table).values(nova_nota))
            connection.commit()

            nota = connection.execute(query_nota).mappings().first()

        return jsonify(dict(nota) if nota else {})


@professor_bp.route('/lancar-nota', methods=['POST'])
@login_required
def salvar_nota_individual():
    try:
        nota_id = request.form.get('nota_id')
        turma_id = request.form.get('turma_id')

        if not nota_id:
            flash('Erro: ID da nota não encontrado. Não foi possível salvar.', 'danger')
            return redirect(url_for('professor_bp.lancar_nota_individual_page'))

        n1 = request.form.get('nota_1_bimestre_final', default=None, type=float)
        n2 = request.form.get('nota_2_bimestre_final', default=None, type=float)
        n3 = request.form.get('nota_3_bimestre_final', default=None, type=float)
        n4 = request.form.get('nota_4_bimestre_final', default=None, type=float)
        faltas = request.form.get('total_faltas', default=None, type=int)

        notas_validas = [n for n in [n1, n2, n3, n4] if n is not None]
        nota_total = sum(notas_validas)
        media_final = nota_total / len(notas_validas) if notas_validas else 0

        stmt = (
            update(nota_table)
            .where(nota_table.c.nota_id == nota_id)
            .values(
                nota_1_bimestre_final=n1,
                nota_2_bimestre_final=n2,
                nota_3_bimestre_final=n3,
                nota_4_bimestre_final=n4,
                total_faltas=faltas,
                nota_total=nota_total,
                media_final=media_final
            )
        )

        academic_engine = db.get_engine(bind='academic')
        with academic_engine.connect() as connection:
            trans = connection.begin()
            try:
                connection.execute(stmt)
                trans.commit()
                flash('Notas salvas com sucesso!', 'success')
            except Exception as e:
                trans.rollback()
                logger.error(f"Erro ao salvar nota individual: {e}", exc_info=True)
                flash(f'Erro ao salvar as notas: {str(e)}', 'danger')

    except Exception as e:
        logger.error(f"Erro no processamento do formulário de nota individual: {e}", exc_info=True)
        flash('Ocorreu um erro inesperado ao processar sua solicitação.', 'danger')

    return redirect(url_for('professor_bp.lancar_nota_individual_page', turma_id=turma_id))



@professor_bp.route('/api/historico_aluno_disciplina')
@login_required
def api_historico_aluno_disciplina():
    aluno_id = request.args.get('aluno_id')
    disciplina_id = request.args.get('disciplina_id')
    if not aluno_id or not disciplina_id:
        return jsonify({'error': 'IDs do Aluno e da Disciplina são obrigatórios'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query_historico = select(nota_table).where(
            nota_table.c.aluno_id == aluno_id,
            nota_table.c.disciplina_id == disciplina_id
        )
        historico = connection.execute(query_historico).mappings().first()

        if not historico:
            return jsonify({'error': 'Histórico não encontrado para este aluno nesta disciplina.'}), 404

        return jsonify(dict(historico))



@professor_bp.route('/diario')
@login_required
def diario_de_classe():
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

    return render_template('professor/diario_de_classe.html',
                           turmas=turmas_atribuidas,
                           username=current_user.username,
                           user_role=current_user.role)

@professor_bp.route('/api/diario/salvar', methods=['POST'])
@login_required
def salvar_entrada_diario():
    data = request.get_json()
    turma_id = data.get('turma_id')
    disciplina_id = data.get('disciplina_id')
    data_aula_str = data.get('data_aula')
    conteudo = data.get('conteudo_ministrado')
    observacoes = data.get('observacoes', '')
    presencas = data.get('presencas', {})

    if not all([turma_id, disciplina_id, data_aula_str, conteudo]):
        return jsonify({'message': 'Todos os campos obrigatórios devem ser preenchidos.'}), 400

    try:
        data_aula = datetime.strptime(data_aula_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Formato de data inválido. Use AAAA-MM-DD.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            stmt_diario = insert(diario_de_classe_table).values(
                professor_id=current_user.professor_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                data_aula=data_aula,
                conteudo_ministrado=conteudo,
                observacoes=observacoes
            )
            result = connection.execute(stmt_diario)
            diario_id = result.inserted_primary_key[0]

            if presencas and diario_id:
                registros_presenca = []
                for aluno_id, status in presencas.items():
                    registros_presenca.append({
                        'diario_id': diario_id,
                        'aluno_id': aluno_id,
                        'status_presenca': status
                    })
                if registros_presenca:
                    connection.execute(insert(presenca_table), registros_presenca)

            trans.commit()
            return jsonify({'message': 'Registro de aula e presenças salvo com sucesso!'})
        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao salvar entrada no diário: {e}", exc_info=True)
            return jsonify({'message': f'Erro no servidor: {e}'}), 500


@professor_bp.route('/api/diario/entradas')
@login_required
def buscar_entradas_diario():
    turma_id = request.args.get('turma_id')
    disciplina_id = request.args.get('disciplina_id')

    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query = select(diario_de_classe_table).where(
            diario_de_classe_table.c.turma_id == turma_id,
            diario_de_classe_table.c.disciplina_id == disciplina_id
        ).order_by(diario_de_classe_table.c.data_aula.desc())

        resultados = connection.execute(query).mappings().all()
        entradas = [
            {**row, 'data_aula': row['data_aula'].isoformat()}
            for row in resultados
        ]

    return jsonify(entradas)


@professor_bp.route('/api/diario/detalhes/<int:diario_id>')
@login_required
def detalhes_diario(diario_id):
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query_diario = select(diario_de_classe_table).where(diario_de_classe_table.c.diario_id == diario_id)
        diario = connection.execute(query_diario).mappings().first()

        if not diario:
            return jsonify({'error': 'Registro de aula não encontrado.'}), 404

        j = join(presenca_table, aluno_table, presenca_table.c.aluno_id == aluno_table.c.aluno_id)
        query_ausentes = select(aluno_table.c.aluno).select_from(j).where(
            presenca_table.c.diario_id == diario_id,
            presenca_table.c.status_presenca == 'Ausente'
        ).order_by(aluno_table.c.aluno)

        alunos_ausentes = connection.execute(query_ausentes).scalars().all()

        return jsonify({
            'conteudo': diario.conteudo_ministrado,
            'observacoes': diario.observacoes,
            'ausentes': alunos_ausentes
        })