from os import mkdir
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from flask_login import current_user
from flask_socketio import emit
from app import db, socketio, logger
from app.models import User
from methods.extract_data import ExtractData
from methods.create_school_history import school_history
from methods.download_data import download_school_data
import os
import shutil
import time
from datetime import datetime

main_bp = Blueprint('main_bp', __name__, template_folder='../templates')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@main_bp.route('/')
@main_bp.route('/get_files')
@jwt_required()
def get_files():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()

    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem acessar esta área.', 'danger')
        return redirect(url_for('auth_bp.login'))

    return render_template('index.html', username=username_jwt, is_admin=user.is_admin, user_role=user.role)


@main_bp.route('/processar_arquivos', methods=['POST'])
@jwt_required()
def processar_arquivos():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()

    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem processar arquivos.', 'danger')
        return redirect(url_for('auth_bp.login'))

    # Alteração: Pega a lista de arquivos do 'request.files.getlist'
    files = request.files.getlist('file')  # Agora 'file' pode conter múltiplos arquivos

    if not files or all(file.filename == '' for file in files):
        flash('Nenhum arquivo enviado ou selecionado.', 'danger')
        return redirect(url_for('main_bp.get_files'))

    upload_folder = current_app.config['UPLOAD_FOLDER']

    # Limpar pasta de uploads antes de salvar novos arquivos
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

    sid = request.sid
    # A função de processamento assíncrono precisa ser capaz de lidar com múltiplos arquivos na pasta.
    # Assumimos que ExtractData().run() já lida com todos os arquivos na pasta.
    socketio.start_background_task(target=process_files_async, folder_path=upload_folder, sid=sid)

    return redirect(url_for('main_bp.get_files'))


@main_bp.route('/historico', methods=['POST'])
@jwt_required()
def historico():
    username_jwt = get_jwt_identity()
    user = User.query.filter_by(username=username_jwt).first()
    if not user or not user.is_admin:
        flash('Acesso negado. Apenas administradores podem gerar históricos.', 'danger')
        return redirect(url_for('auth_bp.login'))

    aluno_nome = request.form.get('aluno_nome')
    if not aluno_nome:
        flash('Nome do aluno não fornecido.', 'danger')
        return redirect(url_for('main_bp.get_files'))  # Use get_files aqui

    output, error = school_history(studant=aluno_nome)

    if error:
        flash(f'Erro ao gerar histórico para {aluno_nome}: {error}', 'danger')
        return redirect(url_for('main_bp.get_files'))  # Use get_files aqui

    try:
        return send_file(output, as_attachment=True, download_name=f"historico_{aluno_nome}.xlsx",
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o histórico: {str(e)}', 'danger')
        return redirect(url_for('main_bp.get_files'))  # Use get_files aqui


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
        return redirect(url_for('main_bp.get_files'))  # Use get_files aqui

    try:
        return send_file(output, as_attachment=True,
                         download_name=f"dados_alunos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o arquivo de dados: {str(e)}', 'danger')
        return redirect(url_for('main_bp.get_files'))  # Use get_files aqui


def process_files_async(folder_path, sid):
    try:
        time.sleep(1.0)  # Pequeno atraso para garantir que os arquivos estejam salvos
        # Verifica se a pasta existe e não está vazia
        if not os.path.exists(folder_path) or not os.listdir(folder_path):
            logger.warning(
                f"Pasta de uploads '{folder_path}' não encontrada ou vazia durante o processamento assíncrono.")
            socketio.emit('processing_complete',
                          {'status': 'error', 'message': 'Nenhum arquivo para processar na pasta de uploads.'},
                          room=sid)
            return

        logger.info(f"Arquivos detectados para processamento: {os.listdir(folder_path)}")
        ExtractData(folder_path=folder_path).run()  # Assume que ExtractData().run() lida com todos os arquivos na pasta
        socketio.emit('processing_complete', {'status': 'success', 'message': 'Arquivos processados com sucesso!'},
                      room=sid)
    except Exception as e:
        logger.error(f"Erro no processamento assíncrono: {e}", exc_info=True)
        socketio.emit('processing_complete', {'status': 'error', 'message': f'Erro ao processar arquivos: {e}'},
                      room=sid)