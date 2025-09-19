from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy.sql import select, join, distinct, insert, update, func, desc, delete, text
from app import (db, socketio, logger, turma_table, disciplina_table, professor_table, \
    professores_turmas_disciplinas_table, aluno_table, comentario_anuncio_table, anuncio_table, notificacao_table,
                 nota_table, alunos_turma_table)
from app.models import User
from methods.extract_data import ExtractData
from methods.create_school_history import school_history
from methods.download_data import download_school_data
from datetime import datetime
from app.audit_log import log_action
import os
import shutil
import time
import json
import uuid
from methods.generate_uuid import generate_uuid

main_bp = Blueprint('main_bp', __name__, template_folder='../templates/main')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@main_bp.route('/')
@main_bp.route('/get_files')
@login_required
def get_files():
    # Se o usuário for um administrador, carrega o dashboard
    if current_user.is_admin:
        # Busca os totais de usuários diretamente da tabela User
        total_alunos = User.query.filter_by(role='student').count()
        total_professores = User.query.filter_by(role='professor').count()

        academic_engine = db.get_engine(bind='academic')
        with academic_engine.connect() as connection:
            # Busca o total de turmas ÚNICAS e os dados para o gráfico
            total_turmas = connection.execute(select(func.count(distinct(turma_table.c.turma_id)))).scalar()

            # Dados para o gráfico de alunos por turma
            query_alunos_por_turma = select(
                turma_table.c.turma,
                func.count(alunos_turma_table.c.aluno_id).label('num_alunos')
            ).select_from(
                turma_table.join(alunos_turma_table, turma_table.c.turma_id == alunos_turma_table.c.turma_id)
            ).group_by(turma_table.c.turma).order_by(turma_table.c.turma)

            alunos_por_turma_result = connection.execute(query_alunos_por_turma).mappings().all()

            # Prepara os dados para o JavaScript do gráfico
            chart_labels = [item['turma'] for item in alunos_por_turma_result]
            chart_data = [item['num_alunos'] for item in alunos_por_turma_result]

        return render_template(
            'main/dashboard_admin.html',
            username=current_user.username,
            user_role=current_user.role,
            total_alunos=total_alunos,
            total_professores=total_professores,
            total_turmas=total_turmas,
            chart_labels=json.dumps(chart_labels),
            chart_data=json.dumps(chart_data)
        )

    atribuicoes = []
    # Se o usuário logado for um professor, busca suas atribuições
    if current_user.is_professor:
        academic_engine = db.get_engine(bind='academic')
        with academic_engine.connect() as connection:
            # Query que junta as 3 tabelas para obter os nomes legíveis
            j = join(professores_turmas_disciplinas_table, turma_table,
                     professores_turmas_disciplinas_table.c.turma_id == turma_table.c.turma_id)
            j = join(j, disciplina_table,
                     professores_turmas_disciplinas_table.c.disciplina_id == disciplina_table.c.disciplina_id)

            query = select(
                turma_table.c.turma,
                turma_table.c.turno,
                disciplina_table.c.disciplina
            ).select_from(j).where(
                professores_turmas_disciplinas_table.c.professor_id == current_user.professor_id
            ).order_by(turma_table.c.turma, disciplina_table.c.disciplina)

            atribuicoes = connection.execute(query).all()

    return render_template(
        'main/index.html',
        username=current_user.username,
        user_role=current_user.role,
        atribuicoes=atribuicoes
    )

@main_bp.route('/processar_arquivos', methods=['POST'])
@login_required
def processar_arquivos():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem processar arquivos.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    files = request.files.getlist('file')
    client_sid = request.form.get('socket_id')

    if not client_sid:
        logger.error("Client Socket ID (sid) não recebido na requisição de processamento de arquivos.")
        flash('Erro interno: ID de sessão do cliente não encontrado. Tente recarregar a página.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    upload_folder = current_app.config['UPLOAD_FOLDER']

    if os.path.exists(upload_folder):
        try:
            shutil.rmtree(upload_folder)
        except OSError as e:
            logger.error(f"Erro ao remover pasta de uploads '{upload_folder}': {e}", exc_info=True)
            flash(f"Erro interno do servidor ao limpar pasta de uploads. Tente novamente mais tarde. ({e})", 'danger')
            return redirect(url_for('main_bp.get_files'))

    os.makedirs(upload_folder)

    uploaded_count = 0
    for file in files:
        if file and allowed_file(file.filename):
            filename = os.path.join(upload_folder, file.filename)
            file.save(filename)
            uploaded_count += 1
        else:
            flash(f"O arquivo '{file.filename}' não é um tipo permitido e foi ignorado.", 'warning')

    if uploaded_count == 0:
        flash('Nenhum arquivo válido foi encontrado para processamento.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    flash(f'{uploaded_count} arquivo(s) carregado(s) com sucesso! Processando...', 'success')

    socketio.start_background_task(target=process_files_async, folder_path=upload_folder, sid=client_sid)

    return redirect(url_for('main_bp.get_files'))


@main_bp.route('/baixar_dados', methods=['GET'])
@login_required
def baixar_dados():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem baixar os dados.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    output, error = download_school_data()

    if error:
        flash(f'Erro ao baixar dados: {error}', 'danger')
        return redirect(url_for('main_bp.get_files'))

    try:
        return send_file(output, as_attachment=True,
                         download_name=f"dados_alunos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o arquivo de dados: {str(e)}', 'danger')
        return redirect(url_for('main_bp.get_files'))


@main_bp.route('/historico', methods=['POST'])
@login_required
def historico():
    if not (current_user.is_admin or current_user.is_professor):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    aluno_nome = request.form.get('aluno')

    if not aluno_nome:
        flash('Por favor, digite o nome do aluno.', 'warning')
        return redirect(url_for('main_bp.get_files'))

    output, error = school_history(studant=aluno_nome)

    if error:
        flash(f'Erro ao gerar histórico para {aluno_nome}: {error}', 'danger')
        return redirect(url_for('main_bp.get_files'))

    try:
        return send_file(output, as_attachment=True, download_name=f"historico_{aluno_nome}.xlsx",
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o histórico: {str(e)}', 'danger')
        return redirect(url_for('main_bp.get_files'))


@main_bp.route('/listar_usuarios')
@login_required
def listar_usuarios():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem visualizar os usuários.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('busca', '')
    query = User.query.order_by(User.username)

    if search_term:
        query = query.filter(User.username.ilike(f'%{search_term}%'))

    pagination = query.paginate(page=page, per_page=10, error_out=False)
    users = pagination.items

    return render_template(
        'main/listar_usuarios.html',
        users=users,
        pagination=pagination,
        search_term=search_term, # Envia o termo de busca de volta para o template
        username=current_user.username,
        user_role=current_user.role
    )


@main_bp.route('/criar_usuario', methods=['GET', 'POST'])
@login_required
def criar_usuario():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem criar usuários.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        turmas = connection.execute(select(turma_table).order_by(turma_table.c.turma, turma_table.c.turno)).all()
        disciplinas = connection.execute(select(disciplina_table).order_by(disciplina_table.c.disciplina)).all()

        users_with_aluno_id = db.session.query(User.aluno_id).filter(User.aluno_id.isnot(None)).all()
        assigned_aluno_ids = [item[0] for item in users_with_aluno_id]

        query_alunos = select(aluno_table).where(aluno_table.c.aluno_id.notin_(assigned_aluno_ids)).order_by(
            aluno_table.c.aluno)
        alunos_nao_associados = connection.execute(query_alunos).all()

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password')
        role_type = request.form.get('role_type')  # Pega o valor do radio button ('student', 'professor', 'admin')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(f"O nome de usuário '{username}' já existe. Por favor, escolha outro.", 'danger')
            return redirect(url_for('main_bp.criar_usuario'))

        is_admin = (role_type == 'admin')
        is_professor = (role_type == 'professor')
        is_student = (role_type == 'student')

        nome_completo_prof = request.form.get('nome_completo')
        atribuicoes_json = request.form.get('atribuicoes', '[]')
        aluno_id_selecionado = request.form.get('aluno_id')


        # (Validações de senha, etc.)
        if not all([username, password, role_type]):
            flash('Nome de usuário, senha e papel são obrigatórios.', 'danger')
            return redirect(url_for('main_bp.criar_usuario'))

        if is_student and not aluno_id_selecionado:
            flash('Para o papel de Aluno, é obrigatório selecionar o aluno correspondente.', 'danger')
            return redirect(url_for('main_bp.criar_usuario'))

        session_app = db.session()
        conn_academic = academic_engine.connect()
        trans_academic = conn_academic.begin()
        try:
            user_role = role_type
            new_professor_id = str(uuid.uuid4()) if is_professor else None

            # Cria o usuário
            new_user = User(
                username=username,
                is_admin=is_admin,
                is_professor=is_professor,
                role=user_role,
                professor_id=new_professor_id,
                aluno_id=aluno_id_selecionado if is_student else None
            )
            new_user.set_password(password)
            session_app.add(new_user)

            if is_student and aluno_id_selecionado:
                stmt_ativar_aluno = update(aluno_table).where(
                    aluno_table.c.aluno_id == aluno_id_selecionado
                ).values(status='Ativo')
                conn_academic.execute(stmt_ativar_aluno)

            if is_professor:
                if not nome_completo_prof:
                    raise ValueError("O campo 'Nome Completo' é obrigatório para professores.")

                stmt_prof = professor_table.insert().values(professor_id=new_professor_id, nome=nome_completo_prof)
                conn_academic.execute(stmt_prof)

                atribuicoes = json.loads(atribuicoes_json)
                for atr in atribuicoes:
                    stmt_atr = professores_turmas_disciplinas_table.insert().values(
                        professor_id=new_professor_id,
                        turma_id=atr['turma_id'],
                        disciplina_id=atr['disciplina_id'],
                        ano_letivo=atr['ano_letivo']
                    )
                    conn_academic.execute(stmt_atr)

            session_app.commit()
            trans_academic.commit()

            # Log de auditoria
            log_action('CREATE', table_affected='user', record_id=new_user.id, new_value={'username': new_user.username, 'role': new_user.role})

            flash(f'Usuário {username} criado com sucesso!', 'success')
            return redirect(url_for('main_bp.listar_usuarios'))

        except Exception as e:
            session_app.rollback()
            trans_academic.rollback()
            logger.error(f"Erro ao criar usuário: {e}", exc_info=True)
            flash(f'Erro ao criar usuário: {str(e)}', 'danger')
        finally:
            conn_academic.close()

    return render_template(
        'main/criar_usuario.html',
        username=current_user.username,
        user_role=current_user.role,
        turmas=turmas,
        disciplinas=disciplinas,
        alunos=alunos_nao_associados
    )


@main_bp.route('/excluir_usuario/<int:user_id>', methods=['POST'])
@login_required
def excluir_usuario(user_id):
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem excluir usuários.', 'danger')
        return redirect(url_for('main_bp.listar_usuarios'))

    user_to_delete = User.query.get_or_404(user_id)

    if user_to_delete.id == current_user.id:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('main_bp.listar_usuarios'))


    # Log de auditoria ANTES de deletar
    log_action('DELETE', table_affected='user', record_id=user_to_delete.id, old_value={'username': user_to_delete.username, 'role': user_to_delete.role})


    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Usuário {user_to_delete.username} foi excluído com sucesso.', 'success')
    return redirect(url_for('main_bp.listar_usuarios'))


@main_bp.route('/editar-usuario/<user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    user_a_editar = User.query.get_or_404(user_id)
    academic_engine = db.get_engine(bind='academic')

    with academic_engine.connect() as connection:
        turmas = connection.execute(select(turma_table).order_by(turma_table.c.turma, turma_table.c.turno)).all()
        disciplinas = connection.execute(select(disciplina_table).order_by(disciplina_table.c.disciplina)).all()

        professor_info = None
        atribuicoes_atuais = []
        if user_a_editar.is_professor and user_a_editar.professor_id:
            query_prof = select(professor_table).where(professor_table.c.professor_id == user_a_editar.professor_id)
            professor_info = connection.execute(query_prof).first()

            j = join(professores_turmas_disciplinas_table, turma_table,
                     professores_turmas_disciplinas_table.c.turma_id == turma_table.c.turma_id)
            j = join(j, disciplina_table,
                     professores_turmas_disciplinas_table.c.disciplina_id == disciplina_table.c.disciplina_id)
            query_atr = select(
                professores_turmas_disciplinas_table, turma_table.c.turma, turma_table.c.turno,
                disciplina_table.c.disciplina
            ).select_from(j).where(
                professores_turmas_disciplinas_table.c.professor_id == user_a_editar.professor_id
            )
            atribuicoes_atuais = connection.execute(query_atr).mappings().all()

    if request.method == 'POST':
        nome_completo = request.form.get('nome_completo')
        atribuicoes_json = request.form.get('atribuicoes', '[]')

        with academic_engine.connect() as conn_academic:
            trans_academic = conn_academic.begin()
            try:
                # 1. Atualiza o nome do professor (se houver)
                if nome_completo:
                    stmt_update_prof = update(professor_table).where(
                        professor_table.c.professor_id == user_a_editar.professor_id
                    ).values(nome=nome_completo)
                    conn_academic.execute(stmt_update_prof)

                # 2. Exclui todas as atribuições antigas
                stmt_delete_atr = delete(professores_turmas_disciplinas_table).where(
                    professores_turmas_disciplinas_table.c.professor_id == user_a_editar.professor_id
                )
                conn_academic.execute(stmt_delete_atr)

                # 3. Insere as novas atribuições recebidas do formulário
                atribuicoes = json.loads(atribuicoes_json)
                if atribuicoes:
                    # O professor_id não vem do formulário, então adicionamos aqui
                    for atr in atribuicoes:
                        atr['professor_id'] = user_a_editar.professor_id

                    conn_academic.execute(insert(professores_turmas_disciplinas_table), atribuicoes)

                trans_academic.commit()
                flash(f'Dados do professor {user_a_editar.username} atualizados com sucesso!', 'success')
                return redirect(url_for('main_bp.listar_usuarios'))
            except Exception as e:
                trans_academic.rollback()
                logger.error(f"Erro ao editar usuário: {e}", exc_info=True)
                flash(f'Erro ao editar usuário: {str(e)}', 'danger')

    return render_template(
        'main/editar_usuario.html',
        user_a_editar=user_a_editar,
        professor_info=professor_info,
        turmas=turmas,
        disciplinas=disciplinas,
        atribuicoes_atuais=atribuicoes_atuais
    )



@main_bp.route('/anuncio/comentar/<int:anuncio_id>', methods=['POST'])
@login_required
def comentar_anuncio(anuncio_id):
    conteudo = request.form.get('conteudo')
    if not conteudo:
        flash('O conteúdo do comentário não pode estar vazio.', 'danger')
        return redirect(request.referrer or url_for('main_bp.get_files'))

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as conn_academic:
        trans_academic = conn_academic.begin()
        try:
            # 1. Salva o novo comentário no banco acadêmico
            stmt_comentario = insert(comentario_anuncio_table).values(
                anuncio_id=anuncio_id,
                user_id=current_user.id,
                nome_usuario=current_user.username,
                conteudo=conteudo,
                data_comentario=datetime.now()
            )
            conn_academic.execute(stmt_comentario)
            trans_academic.commit()

            # --- LÓGICA DE NOTIFICAÇÃO PARA O PROFESSOR ---

            # 2. Busca o professor que é o autor do anúncio original
            query_anuncio = select(anuncio_table.c.professor_id).where(anuncio_table.c.anuncio_id == anuncio_id)
            resultado_anuncio = conn_academic.execute(query_anuncio).first()

            if resultado_anuncio:
                professor_id_autor = resultado_anuncio.professor_id

                # 3. Encontra o registro de usuário (login) do professor
                professor_user = User.query.filter_by(professor_id=professor_id_autor).first()

                if professor_user:
                    # 4. Cria a notificação para o professor
                    mensagem = f"'{current_user.username}' comentou no seu anúncio."
                    link = url_for('professor_bp.gerenciar_anuncios')

                    nova_notificacao = {
                        'user_id_destino': professor_user.id,
                        'mensagem': mensagem,
                        'link': link,
                        'data_criacao': datetime.now()
                    }

                    # 5. Salva a notificação no banco de auditoria
                    audit_engine = db.get_engine()
                    with audit_engine.connect() as conn_audit:
                        trans_audit = conn_audit.begin()
                        conn_audit.execute(insert(notificacao_table), [nova_notificacao])
                        trans_audit.commit()

                    # 6. Emite o sinal em tempo real para o professor
                    socketio.emit('nova_notificacao', {'count': 1}, room=f'user_{professor_user.id}')

            flash('Comentário adicionado com sucesso!', 'success')
        except Exception as e:
            trans_academic.rollback()
            logger.error(f"Erro ao adicionar comentário: {e}", exc_info=True)
            flash('Ocorreu um erro ao salvar seu comentário.', 'danger')

    return redirect(request.referrer or url_for('main_bp.get_files'))


@main_bp.route('/relatorios')
@login_required
def relatorios():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem ver os relatórios.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    return render_template(
        'main/relatorios.html',
        username=current_user.username,
        user_role=current_user.role
    )


def process_files_async(folder_path, sid):
    try:
        time.sleep(1.0)
        if not os.path.exists(folder_path) or not os.listdir(folder_path):
            logger.warning(
                f"Pasta de uploads '{folder_path}' não encontrada ou vazia durante o processamento assíncrono.")
            socketio.emit('processing_complete',
                          {'status': 'error', 'message': 'Nenhum arquivo para processar na pasta de uploads.'},
                          room=sid)
            return

        logger.info(f"Arquivos detectados para processamento: {os.listdir(folder_path)}")
        ExtractData(folder_path=folder_path).run()
        socketio.emit('processing_complete', {'status': 'success', 'message': 'Arquivos processados com sucesso!'},
                      room=sid)
    except Exception as e:
        logger.error(f"Erro no processamento assíncrono: {e}", exc_info=True)
        socketio.emit('processing_complete', {'status': 'error', 'message': f'Erro ao processar arquivos: {e}'},
                      room=sid)
    finally:
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                logger.info(f"Pasta de uploads '{folder_path}' removida após processamento.")
            except OSError as e:
                logger.error(f"Erro ao remover pasta de uploads '{folder_path}': {e}", exc_info=True)



@main_bp.route('/gerenciar-matriculas')
@login_required
def gerenciar_matriculas():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem gerenciar matrículas.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        turmas = connection.execute(
            select(turma_table).order_by(turma_table.c.turma, turma_table.c.turno)).all()

    return render_template(
        'main/gerenciar_matriculas.html',
        username=current_user.username,
        user_role=current_user.role,
        turmas=turmas
    )


@main_bp.route('/auditoria')
@login_required
def auditoria():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem visualizar a trilha de auditoria.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    page = request.args.get('page', 1, type=int)

    # Query para buscar os logs com o nome do usuário
    # Usando text() para uma query mais complexa entre bancos de dados (se necessário)
    # ou um join se as tabelas estiverem no mesmo DB.
    # Assumindo que a tabela `user` está no mesmo banco de dados de auditoria
    query = text("""
        SELECT a.id, a.data_acao, u.username, a.acao, a.tabela_afetada, a.registro_afetado_id
        FROM audit_log a
        LEFT JOIN user u ON a.usuario_id = u.id
        ORDER BY a.data_acao DESC
    """)

    # Para simplicidade, vamos usar o query builder do SQLAlchemy
    audit_log_table = db.metadata.tables.get('audit_log')
    user_table = db.metadata.tables.get('user')

    j = audit_log_table.outerjoin(user_table, audit_log_table.c.usuario_id == user_table.c.id)
    query_final = select(
        audit_log_table,
        user_table.c.username
    ).select_from(j).order_by(audit_log_table.c.data_acao.desc())

    # A paginação com join pode ser complexa, vamos buscar todos e paginar na aplicação
    # (Para produção, uma solução mais otimizada seria necessária)
    with db.engine.connect() as connection:
        results = connection.execute(query_final).mappings().all()

    # Paginação manual
    per_page = 20
    start = (page - 1) * per_page
    end = start + per_page
    total_pages = (len(results) + per_page - 1) // per_page

    paginated_results = results[start:end]

    return render_template(
        'main/auditoria.html',
        logs=paginated_results,
        page=page,
        total_pages=total_pages,
        username=current_user.username,
        user_role=current_user.role
    )



# APIs

@main_bp.route('/api/relatorio_desempenho')
@login_required
def api_relatorio_desempenho():
    if not current_user.is_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        # Relatório 1: Média geral por disciplina
        query_media = select(
            disciplina_table.c.disciplina,
            func.avg(nota_table.c.media_final).label('media_geral')
        ).select_from(
            join(nota_table, disciplina_table, nota_table.c.disciplina_id == disciplina_table.c.disciplina_id)
        ).group_by(disciplina_table.c.disciplina).order_by(desc('media_geral'))

        medias_result = connection.execute(query_media).mappings().all()
        media_por_disciplina = [{'disciplina': row['disciplina'], 'media_geral': round(row['media_geral'], 2)} for row
                                in medias_result]

        # Relatório 2: Alunos em risco (média geral abaixo de 6.0)
        subquery = select(
            nota_table.c.aluno_id,
            func.avg(nota_table.c.media_final).label('media_final_geral')
        ).group_by(nota_table.c.aluno_id).having(func.avg(nota_table.c.media_final) < 6.0).alias('medias_alunos')

        query_risco = select(
            aluno_table.c.aluno,
            turma_table.c.turma,
            subquery.c.media_final_geral
        ).select_from(
            join(subquery, aluno_table, subquery.c.aluno_id == aluno_table.c.aluno_id)
            .join(alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
            .join(turma_table, alunos_turma_table.c.turma_id == turma_table.c.turma_id)
        ).order_by(subquery.c.media_final_geral)

        risco_result = connection.execute(query_risco).mappings().all()
        alunos_em_risco = [dict(row) for row in risco_result]

    return jsonify({
        'media_por_disciplina': media_por_disciplina,
        'alunos_em_risco': alunos_em_risco
    })


@main_bp.route('/api/alunos_por_turma_status')
@login_required
def api_alunos_por_turma_status():
    if not current_user.is_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    turma_id = request.args.get('turma_id')
    if not turma_id:
        return jsonify({'error': 'ID da Turma é obrigatório'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        # Alunos já matriculados na turma (consulta permanece a mesma)
        query_matriculados = select(
            aluno_table.c.aluno_id,
            aluno_table.c.aluno,
            aluno_table.c.status
        ).join(
            alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id
        ).where(alunos_turma_table.c.turma_id == turma_id).order_by(aluno_table.c.aluno)
        matriculados = connection.execute(query_matriculados).mappings().all()

        j = aluno_table.outerjoin(alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
        query_disponiveis = select(
            aluno_table.c.aluno_id,
            aluno_table.c.aluno,
            aluno_table.c.status
        ).select_from(j).where(
            alunos_turma_table.c.turma_id == None
        ).order_by(aluno_table.c.aluno)
        disponiveis = connection.execute(query_disponiveis).mappings().all()

    return jsonify({
        'matriculados': [dict(row) for row in matriculados],
        'disponiveis': [dict(row) for row in disponiveis]
    })


@main_bp.route('/api/atualizar_matricula', methods=['POST'])
@login_required
def api_atualizar_matricula():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    data = request.get_json()
    turma_id = data.get('turma_id')
    aluno_id = data.get('aluno_id')
    acao = data.get('acao') # 'matricular' ou 'desmatricular'

    if not all([turma_id, aluno_id, acao]):
        return jsonify({'success': False, 'message': 'Dados incompletos.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            if acao == 'matricular':
                stmt_insert = insert(alunos_turma_table).values(aluno_id=aluno_id, turma_id=turma_id)
                connection.execute(stmt_insert)
                message = 'Aluno matriculado com sucesso!'
            elif acao == 'desmatricular':
                stmt_delete = alunos_turma_table.delete().where(
                    alunos_turma_table.c.aluno_id == aluno_id,
                    alunos_turma_table.c.turma_id == turma_id
                )
                connection.execute(stmt_delete)
                message = 'Aluno removido da turma com sucesso!'
            else:
                raise ValueError("Ação inválida.")

            trans.commit()
            return jsonify({'success': True, 'message': message})
        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao atualizar matrícula: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Erro no servidor: {e}'}), 500


@main_bp.route('/api/criar_aluno', methods=['POST'])
@login_required
def api_criar_aluno():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    data = request.get_json()
    turma_id = data.get('turma_id')
    aluno_nome = data.get('aluno_nome', '').strip()

    if not all([turma_id, aluno_nome]):
        return jsonify({'success': False, 'message': 'O nome do aluno e a turma são obrigatórios.'}), 400

    academic_engine = db.get_engine(bind='academic')
    try:
        with academic_engine.connect() as connection:
            with connection.begin():  # Inicia a transação aqui
                # Verifica se já existe um aluno com o mesmo nome para evitar duplicatas
                aluno_existente = connection.execute(
                    select(aluno_table).where(aluno_table.c.aluno == aluno_nome)
                ).first()
                if aluno_existente:
                    # Usamos um código de status 409 Conflict para indicar a duplicata
                    return jsonify({'success': False, 'message': f'Aluno "{aluno_nome}" já existe.'}), 409

                # 1. Cria o novo aluno na tabela 'alunos'
                novo_aluno_id = generate_uuid(aluno_nome)
                stmt_aluno = insert(aluno_table).values(
                    aluno_id=novo_aluno_id,
                    aluno=aluno_nome,
                    status='Ativo'
                )
                connection.execute(stmt_aluno)

                # 2. Matricula o novo aluno na turma selecionada
                stmt_matricula = insert(alunos_turma_table).values(
                    aluno_id=novo_aluno_id,
                    turma_id=turma_id
                )
                connection.execute(stmt_matricula)

        return jsonify({'success': True, 'message': f'Aluno "{aluno_nome}" criado e matriculado com sucesso!'})

    except Exception as e:
        logger.error(f"Erro ao criar novo aluno: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Erro no servidor ao criar aluno: {e}'}), 500

    @main_bp.route('/api/limpar_turma', methods=['POST'])
    @login_required
    def api_limpar_turma():
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

        data = request.get_json()
        turma_id = data.get('turma_id')

        if not turma_id:
            return jsonify({'success': False, 'message': 'ID da Turma é obrigatório.'}), 400

        academic_engine = db.get_engine(bind='academic')
        try:
            with academic_engine.connect() as connection:
                with connection.begin():  # Gerenciamento automático de transação
                    stmt = delete(alunos_turma_table).where(
                        alunos_turma_table.c.turma_id == turma_id
                    )
                    result = connection.execute(stmt)

                    # O rowcount informa quantos registros foram afetados (excluídos)
                    message = f'{result.rowcount} alunos foram removidos da turma com sucesso!'
                    return jsonify({'success': True, 'message': message})

        except Exception as e:
            logger.error(f"Erro ao limpar a turma: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Erro no servidor ao limpar a turma: {e}'}), 500
@main_bp.route('/criar_turma', methods=['GET'])
@login_required
def criar_turma():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem criar turmas.', 'danger')
        return redirect(url_for('main_bp.get_files'))
    return render_template('main/criar_turma.html')


@main_bp.route('/api/criar_turma', methods=['POST'])
@login_required
def api_criar_turma():
    if not current_user.is_admin:
        return jsonify({'message': 'Acesso negado.'}), 403

    data = request.get_json()
    nome_turma = data.get('nome_turma')
    turno = data.get('turno')
    ano_letivo = data.get('ano_letivo')

    if not all([nome_turma, turno, ano_letivo]):
        return jsonify({'message': 'Todos os campos são obrigatórios.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            # Gera um ID numérico único para a turma usando o timestamp
            novo_turma_id = int(time.time() * 1000)

            nova_turma = {
                "turma_id": novo_turma_id,
                "turma": nome_turma,
                "turno": turno,
                "ano_escolar": ano_letivo
            }
            stmt = insert(turma_table).values(nova_turma)
            connection.execute(stmt)
            trans.commit()
            return jsonify({'message': 'Turma criada com sucesso!'}), 201
        except Exception as e:
            trans.rollback()
            logger.error(f"Erro ao criar turma: {e}", exc_info=True)
            return jsonify({'message': f'Erro no servidor: {e}'}), 500


@main_bp.route('/gerenciar_disciplinas')
@login_required
def gerenciar_disciplinas():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query = select(disciplina_table).order_by(disciplina_table.c.disciplina)
        disciplinas = connection.execute(query).mappings().all()

    return render_template(
        'main/gerenciar_disciplinas.html',
        disciplinas=disciplinas,
        username=current_user.username,
        user_role=current_user.role
    )


@main_bp.route('/api/disciplinas', methods=['POST'])
@login_required
def api_criar_disciplina():
    if not current_user.is_admin:
        return jsonify({'message': 'Acesso negado.'}), 403

    data = request.get_json()
    nome_disciplina = data.get('disciplina')
    if not nome_disciplina:
        return jsonify({'message': 'O nome da disciplina é obrigatório.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            # Encontra o maior disciplina_id existente para criar o próximo
            max_id = connection.execute(select(func.max(disciplina_table.c.disciplina_id))).scalar() or 0
            novo_id = max_id + 1

            stmt = insert(disciplina_table).values(
                disciplina_id=novo_id,
                disciplina=nome_disciplina,
                fk_disciplina=novo_id
            )
            connection.execute(stmt)
            trans.commit()
            log_action('CREATE', 'materias', record_id=novo_id, new_value={'disciplina': nome_disciplina})
            return jsonify({'message': 'Disciplina criada com sucesso!'}), 201
        except Exception as e:
            trans.rollback()
            return jsonify({'message': f'Erro ao criar disciplina: {e}'}), 500


@main_bp.route('/api/disciplinas/<int:disciplina_id>', methods=['PUT', 'DELETE'])
@login_required
def api_modificar_disciplina(disciplina_id):
    if not current_user.is_admin:
        return jsonify({'message': 'Acesso negado.'}), 403

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        trans = connection.begin()
        try:
            if request.method == 'PUT':
                data = request.get_json()
                novo_nome = data.get('disciplina')
                stmt = update(disciplina_table).where(disciplina_table.c.disciplina_id == disciplina_id).values(
                    disciplina=novo_nome)
                connection.execute(stmt)
                message = 'Disciplina atualizada com sucesso!'
                log_action('UPDATE', 'materias', record_id=disciplina_id, new_value={'disciplina': novo_nome})

            elif request.method == 'DELETE':
                stmt = delete(disciplina_table).where(disciplina_table.c.disciplina_id == disciplina_id)
                connection.execute(stmt)
                message = 'Disciplina excluída com sucesso!'
                log_action('DELETE', 'materias', record_id=disciplina_id)

            trans.commit()
            return jsonify({'message': message})
        except Exception as e:
            trans.rollback()
            return jsonify({'message': f'Erro ao processar a solicitação: {e}'}), 500


@main_bp.route('/informacoes_alunos')
@login_required
def informacoes_alunos():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    search_term = request.args.get('busca', '')
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query = select(aluno_table).order_by(aluno_table.c.aluno)
        if search_term:
            query = query.where(aluno_table.c.aluno.ilike(f'%{search_term}%'))
        alunos = connection.execute(query).mappings().all()

    return render_template('main/informacoes_alunos.html',
                           alunos=alunos,
                           search_term=search_term,
                           username=current_user.username,
                           user_role=current_user.role)


@main_bp.route('/api/aluno/<aluno_id>/detalhes')
@login_required
def api_aluno_detalhes(aluno_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        # Busca dados do aluno
        aluno_info = connection.execute(
            select(aluno_table).where(aluno_table.c.aluno_id == aluno_id)).mappings().first()
        if not aluno_info:
            return jsonify({'error': 'Aluno não encontrado'}), 404

        # Busca dados da turma
        turma_info = connection.execute(
            select(turma_table.c.turma, turma_table.c.turno, turma_table.c.turma_id)
            .join(alunos_turma_table, turma_table.c.turma_id == alunos_turma_table.c.turma_id)
            .where(alunos_turma_table.c.aluno_id == aluno_id)
        ).mappings().first()

        # Busca disciplinas da turma (Query Corrigida)
        disciplinas = []
        if turma_info:
            disciplinas_query = select(disciplina_table.c.disciplina).select_from(
                disciplina_table.join(professores_turmas_disciplinas_table,
                                      disciplina_table.c.disciplina_id == professores_turmas_disciplinas_table.c.disciplina_id)
            ).where(professores_turmas_disciplinas_table.c.turma_id == turma_info.turma_id).order_by(
                disciplina_table.c.disciplina)

            disciplinas = connection.execute(disciplinas_query).scalars().all()

        detalhes = {
            "nome": aluno_info.aluno,
            "status": aluno_info.status,
            "turma": f"{turma_info.turma} - {turma_info.turno}" if turma_info else "Não matriculado",
            "disciplinas": disciplinas
            # Campos de responsável foram removidos
        }
        return jsonify(detalhes)


@main_bp.route('/visualizador_logs')
@login_required
def visualizador_logs():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    log_content = "Arquivo de log não encontrado."
    try:
        log_file_path = os.path.join(current_app.root_path, '..', 'app.log')
        # --- CORREÇÃO AQUI ---
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            log_content = "".join(lines[-1000:])
    except FileNotFoundError:
        logger.warning("O arquivo app.log não foi encontrado para visualização.")
    except Exception as e:
        logger.error(f"Erro ao ler o arquivo de log: {e}", exc_info=True)
        log_content = f"Erro ao ler o arquivo de log: {e}"

    return render_template(
        'main/visualizador_logs.html',
        log_content=log_content,
        username=current_user.username,
        user_role=current_user.role
    )