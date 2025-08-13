from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy.sql import select, join, distinct, insert, update
from app import db, socketio, logger, turma_table, disciplina_table, professor_table, \
    professores_turmas_disciplinas_table, aluno_table
from app.models import User
from methods.extract_data import ExtractData
from methods.create_school_history import school_history
from methods.download_data import download_school_data
from datetime import datetime
import os
import shutil
import time
import json
import uuid

main_bp = Blueprint('main_bp', __name__, template_folder='../templates/main')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@main_bp.route('/')
@main_bp.route('/get_files')
@login_required
def get_files():
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
        atribuicoes=atribuicoes  # Envia a lista de atribuições para o template
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

    users = User.query.all()
    return render_template(
        'main/listar_usuarios.html',
        users=users,
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

    # Busca o usuário a ser editado no banco de login
    user_a_editar = User.query.get_or_404(user_id)

    # Prepara a conexão com o banco acadêmico
    academic_engine = db.get_engine(bind='academic')

    # Busca os dados necessários para os formulários
    with academic_engine.connect() as connection:
        turmas = connection.execute(select(turma_table).order_by(turma_table.c.turma, turma_table.c.turno)).all()
        disciplinas = connection.execute(select(disciplina_table).order_by(disciplina_table.c.disciplina)).all()

        # Se for um professor, busca seus dados específicos
        professor_info = None
        atribuicoes_atuais = []
        if user_a_editar.is_professor and user_a_editar.professor_id:
            query_prof = select(professor_table).where(professor_table.c.professor_id == user_a_editar.professor_id)
            professor_info = connection.execute(query_prof).first()

            # Busca as atribuições atuais para exibir na tela
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
            atribuicoes_atuais = connection.execute(query_atr).all()

    if request.method == 'POST':
        # Lógica para salvar as alterações
        nome_completo = request.form.get('nome_completo')
        atribuicoes_json = request.form.get('atribuicoes', '[]')

        conn_academic = academic_engine.connect()
        trans_academic = conn_academic.begin()
        try:
            # Atualiza o nome completo na tabela 'professores'
            stmt_update_prof = update(professor_table).where(
                professor_table.c.professor_id == user_a_editar.professor_id
            ).values(nome=nome_completo)
            conn_academic.execute(stmt_update_prof)

            # Exclui todas as atribuições antigas para substituí-las pelas novas
            stmt_delete_atr = professores_turmas_disciplinas_table.delete().where(
                professores_turmas_disciplinas_table.c.professor_id == user_a_editar.professor_id
            )
            conn_academic.execute(stmt_delete_atr)

            # Insere as novas atribuições
            import json
            atribuicoes = json.loads(atribuicoes_json)
            if atribuicoes:
                conn_academic.execute(insert(professores_turmas_disciplinas_table), atribuicoes)

            trans_academic.commit()
            flash(f'Dados do professor {user_a_editar.username} atualizados com sucesso!', 'success')
            return redirect(url_for('main_bp.listar_usuarios'))
        except Exception as e:
            trans_academic.rollback()
            logger.error(f"Erro ao editar usuário: {e}", exc_info=True)
            flash(f'Erro ao editar usuário: {str(e)}', 'danger')
        finally:
            conn_academic.close()

    return render_template(
        'main/editar_usuario.html',
        user_a_editar=user_a_editar,
        professor_info=professor_info,
        turmas=turmas,
        disciplinas=disciplinas,
        atribuicoes_atuais=atribuicoes_atuais
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