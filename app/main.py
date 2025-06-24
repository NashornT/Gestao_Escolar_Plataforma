from os import mkdir

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import current_user # Ainda pode ser útil para renderização de templates se você quiser exibir o nome de usuário do Flask-Login
from flask_socketio import emit

from app import db, socketio, logger # Importa os objetos inicializados
from app.models import User # Importa o modelo User
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

def process_files_async(folder_path, sid):
    try:
        time.sleep(1.0)
        logger.info(f"Arquivos detectados para processamento: {os.listdir(folder_path)}")
        ExtractData(folder_path=folder_path).run()
        socketio.emit('processing_complete', {'status': 'success', 'message': 'Arquivos processados com sucesso!'}, room=sid)
    except Exception as e:
        socketio.emit('processing_complete', {'status': 'error', 'message': f'Ocorreu um erro durante o processamento: {str(e)}'}, room=sid)
    finally:
        for f in os.listdir(folder_path):
            os.remove(os.path.join(folder_path, f))
        logger.info("Pasta de upload limpa após processamento.")


@main_bp.route('/', methods=['GET', 'POST'])
@jwt_required()
def get_files():
    # Para obter o usuário do JWT:
    current_username_jwt = get_jwt_identity()
    user_from_jwt = User.query.filter_by(username=current_username_jwt).first()

    if request.method == 'POST':
        client_sid = request.form.get('socket_id')

        if 'files' not in request.files:
            flash('Nenhum arquivo enviado.', 'warning')
            return redirect(request.url)

        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            flash('Nenhum arquivo selecionado.', 'warning')
            return redirect(request.url)

        files_saved = False
        for file in files:
            if file and allowed_file(file.filename):
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)
                files_saved = True
            else:
                flash(f'Tipo de arquivo inválido: {file.filename}. Use apenas arquivos .xls ou .xlsx.', 'danger')

        if files_saved:
            if client_sid:
                socketio.start_background_task(process_files_async, current_app.config['UPLOAD_FOLDER'], client_sid)
                flash('Processamento dos arquivos iniciado em segundo plano.', 'info')
            else:
                flash('Erro: Não foi possível obter o ID de sessão.', 'warning')
        else:
            flash('Nenhum arquivo válido foi selecionado para processamento.', 'warning')

        return redirect(request.url)

    return render_template('index.html', current_user_jwt=user_from_jwt) # Passa o usuário do JWT para o template


@main_bp.route('/relatorio', methods=['GET'])
@jwt_required()
def relatorio():
    return redirect("http://localhost:8501")

@main_bp.route('/historico', methods=['POST'])
@jwt_required()
def historico():
    aluno_nome = request.form.get('aluno')

    if not aluno_nome:
        flash('Por favor, digite o nome do aluno.', 'warning')
        return redirect(url_for('main_bp.index'))

    output, error = school_history(studant=aluno_nome)

    if error:
        flash(f'Erro ao gerar histórico para {aluno_nome}: {error}', 'danger')
        return redirect(url_for('main_bp.index'))

    try:
        return send_file(output, as_attachment=True, download_name=f"historico_{aluno_nome}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o histórico: {str(e)}', 'danger')
        return redirect(url_for('main_bp.index'))

@main_bp.route('/baixar_dados', methods=['GET'])
@jwt_required()
def baixar_dados():
    output, error = download_school_data()

    if error:
        flash(f'Erro ao baixar dados: {error}', 'danger')
        return redirect(url_for('main_bp.index'))

    try:
        return send_file(output, as_attachment=True, download_name=f"dados_alunos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o arquivo de dados: {str(e)}', 'danger')
        return redirect(url_for('main_bp.index'))

# Rotas de SocketIO
@socketio.on('connect')
def test_connect():
    emit('my_response', {'data': 'Conectado', 'sid': request.sid})
    logger.info(f'Cliente conectado: {request.sid}')

@socketio.on('disconnect')
def test_disconnect():
    logger.info(f'Cliente desconectado')