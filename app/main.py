from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db, socketio, logger
from app.models import User
from methods.extract_data import ExtractData
from methods.create_school_history import school_history
from methods.download_data import download_school_data
import os
import shutil
import time
from datetime import datetime

main_bp = Blueprint('main_bp', __name__, template_folder='../templates/main')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@main_bp.route('/get_files')
@jwt_required()
def get_files():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()

    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem acessar esta área.', 'danger')
        return redirect(url_for('auth_bp.login'))

    return render_template('index.html', username=username_jwt, is_admin=user.is_admin,
                           user_role="Administrador" if user.is_admin else "Professor" if user.is_professor else "Usuário Comum")


@main_bp.route('/processar_arquivos', methods=['POST'])
@jwt_required()
def processar_arquivos():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()

    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem processar arquivos.', 'danger')
        return redirect(url_for('auth_bp.login'))

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
@jwt_required()
def baixar_dados():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()
    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem baixar dados.', 'danger')
        return redirect(url_for('auth_bp.login'))

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
@jwt_required()
def historico():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()
    if not user or (not user.is_admin and not user.is_professor):
        flash('Acesso negado. Você não tem permissão para esta ação.', 'danger')
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
@jwt_required()
def listar_usuarios():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()

    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem listar usuários.', 'danger')
        return redirect(url_for('auth_bp.login'))

    users = User.query.all()
    return render_template('listar_usuarios.html', users=users, username=username_jwt, is_admin=user.is_admin,
                           user_role="Administrador")


@main_bp.route('/criar_usuario', methods=['GET', 'POST'])
@jwt_required()
def criar_usuario():
    username_jwt = get_jwt_identity()
    current_admin_user = User.query.filter_by(username=username_jwt).first()

    if not current_admin_user or not current_admin_user.is_admin:
        flash('Acesso negado. Apenas administradores podem criar usuários.', 'danger')
        return redirect(url_for('auth_bp.login'))

    # Obtenha o token CSRF diretamente do cookie
    # O nome do cookie é definido por JWT_ACCESS_COOKIE_NAME ou JWT_COOKIE_CSRF_PROTECT
    # Se JWT_CSRF_IN_COOKIES for True, o nome padrão é 'csrf_access_token'
    csrf_token = request.cookies.get('csrf_access_token')

    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        is_admin = 'is_admin' in request.form
        is_professor = 'is_professor' in request.form

        if not username or not password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('criar_usuario.html', username=username_jwt, is_admin=current_admin_user.is_admin,
                                   user_role="Administrador", csrf_token=csrf_token) # Passe o token aqui

        if len(password) < 8 or not any(char.isdigit() for char in password) or not any(
                char.isupper() for char in password) or not any(char.islower() for char in password):
            flash('A senha deve ter pelo menos 8 caracteres e incluir letras maiúsculas, minúsculas e números.',
                  'danger')
            return render_template('criar_usuario.html', username=username_jwt, is_admin=current_admin_user.is_admin,
                                   user_role="Administrador", csrf_token=csrf_token) # Passe o token aqui

        if password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('criar_usuario.html', username=username_jwt, is_admin=current_admin_user.is_admin,
                                   user_role="Administrador", csrf_token=csrf_token) # Passe o token aqui

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Nome de usuário já existe. Por favor, escolha outro.', 'danger')
            return render_template('criar_usuario.html', username=username_jwt, is_admin=current_admin_user.is_admin,
                                   user_role="Administrador", csrf_token=csrf_token) # Passe o token aqui

        # Define a role com base nas permissões
        user_role = 'student'  # Valor padrão
        if is_admin:
            user_role = 'admin'
        elif is_professor:
            user_role = 'professor'

        # Cria o novo usuário com a role correta
        new_user = User(username=username, is_admin=is_admin, is_professor=is_professor, role=user_role)

        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f'Usuário {username} criado com sucesso com o papel de \'{user_role}\'!', 'success')
        return redirect(url_for('main_bp.listar_usuarios'))

    # Para requisições GET:
    return render_template('criar_usuario.html', username=username_jwt, is_admin=current_admin_user.is_admin,
                           user_role="Administrador", csrf_token=csrf_token) # <--- ALTERADA ESTA LINHA

@main_bp.route('/excluir_usuario/<int:user_id>', methods=['POST'])
@jwt_required()
def excluir_usuario(user_id):
    username_jwt = get_jwt_identity()
    current_user = User.query.filter_by(username=username_jwt).first()

    if not current_user or not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem excluir usuários.', 'danger')
        return redirect(url_for('main_bp.listar_usuarios'))

    user_to_delete = User.query.get_or_404(user_id)

    if user_to_delete.username == username_jwt:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('main_bp.listar_usuarios'))

    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Usuário {user_to_delete.username} foi excluído com sucesso.', 'success')
    return redirect(url_for('main_bp.listar_usuarios'))

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