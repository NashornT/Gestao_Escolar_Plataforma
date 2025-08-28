from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy.sql import select, update, insert, join, distinct
from app import db, logger
from app import turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table, \
    professores_turmas_disciplinas_table, anuncio_table, material_aula_table, comentario_anuncio_table, notificacao_table, socketio
from datetime import datetime
from werkzeug.utils import secure_filename
from app.models import User
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
                    # CORREÇÃO: Busca as notas FINAIS para exibir na tabela
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
        # Agrupa todas as atualizações por nota_id para otimizar
        updates_por_nota = {}
        for item in data['dados']:
            nota_id = item.get('nota_id')
            if nota_id not in updates_por_nota:
                updates_por_nota[nota_id] = {}
            updates_por_nota[nota_id][item.get('campo')] = item.get('valor')

        trans = connection.begin()
        try:
            for nota_id, campos_para_atualizar in updates_por_nota.items():
                # 1. Busca o registro atual da nota
                registro_atual = connection.execute(
                    select(nota_table).where(nota_table.c.nota_id == nota_id)
                ).first()
                if not registro_atual:
                    continue

                valores_finais = {
                    "nota_1_bimestre_final": registro_atual.nota_1_bimestre_final,
                    "nota_2_bimestre_final": registro_atual.nota_2_bimestre_final,
                    "nota_3_bimestre_final": registro_atual.nota_3_bimestre_final,
                    "nota_4_bimestre_final": registro_atual.nota_4_bimestre_final,
                    "total_faltas": registro_atual.total_faltas
                }

                # 2. Atualiza os valores com os dados recebidos
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

                # 3. Recalcula a média e o total
                notas_validas = [n for n in [
                    valores_finais['nota_1_bimestre_final'], valores_finais['nota_2_bimestre_final'],
                    valores_finais['nota_3_bimestre_final'], valores_finais['nota_4_bimestre_final']
                ] if n is not None]

                nota_total = sum(notas_validas)
                media_final = nota_total / len(notas_validas) if notas_validas else 0

                valores_finais['nota_total'] = nota_total
                valores_finais['media_final'] = round(media_final, 2)

                # 4. Executa o update com todos os campos (originais + atualizados + calculados)
                stmt = update(nota_table).where(nota_table.c.nota_id == nota_id).values(valores_finais)
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
                conn_academic.execute(stmt_anuncio)
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

            stmt = anuncio_table.delete().where(anuncio_table.c.anuncio_id == anuncio_id)
            connection.execute(stmt)

            trans.commit()
            flash('Anúncio removido com sucesso!', 'success')

        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao excluir anúncio: {e}", exc_info=True)
            flash(f'Erro ao remover anúncio: {e}', 'danger')

    return redirect(url_for('professor_bp.gerenciar_anuncios'))


@professor_bp.route('/api/dados_graficos')
@login_required
def api_dados_graficos():
    turma_id = request.args.get('turma_id')
    disciplina_id = request.args.get('disciplina_id', type=int)

    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        # 1. Obter notas da turma na disciplina
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

        # 2. Calcular médias por bimestre
        soma_b1, count_b1 = 0, 0
        soma_b2, count_b2 = 0, 0
        soma_b3, count_b3 = 0, 0
        soma_b4, count_b4 = 0, 0

        todas_as_medias_finais = []

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

        # 3. Calcular distribuição de notas (média final)
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
    # Esta rota apenas renderiza a página e carrega as turmas do professor
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

        # Se o aluno ainda não tem um registro de nota para essa disciplina, cria um
        if not nota:
            # Precisamos do ano letivo da turma para criar a nova entrada de nota
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

            # Busca novamente para retornar o objeto completo
            nota = connection.execute(query_nota).mappings().first()

        return jsonify(dict(nota) if nota else {})


@professor_bp.route('/lancar-nota', methods=['POST'])
@login_required
def salvar_nota_individual():
    try:
        nota_id = request.form.get('nota_id')
        turma_id = request.form.get('turma_id')  # Adicionado para contexto

        if not nota_id:
            flash('Erro: ID da nota não encontrado. Não foi possível salvar.', 'danger')
            return redirect(url_for('professor_bp.lancar_nota_individual_page'))

        # Pega as notas do formulário, tratando valores vazios como None
        n1 = request.form.get('nota_1_bimestre_final', default=None, type=float)
        n2 = request.form.get('nota_2_bimestre_final', default=None, type=float)
        n3 = request.form.get('nota_3_bimestre_final', default=None, type=float)
        n4 = request.form.get('nota_4_bimestre_final', default=None, type=float)
        faltas = request.form.get('total_faltas', default=None, type=int)

        # Calcula a nota total e a média final
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

    # Redireciona de volta para a página, mantendo o filtro da turma selecionado
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
        # A query busca o registro de nota completo
        query_historico = select(nota_table).where(
            nota_table.c.aluno_id == aluno_id,
            nota_table.c.disciplina_id == disciplina_id
        )
        historico = connection.execute(query_historico).mappings().first()

        if not historico:
            return jsonify({'error': 'Histórico não encontrado para este aluno nesta disciplina.'}), 404

        return jsonify(dict(historico))

