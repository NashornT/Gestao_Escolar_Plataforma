from flask import Flask, render_template, request, redirect, flash, send_file, url_for
from methods.extract_data import ExtractData
import os
import shutil
from methods.create_school_history import school_history
from methods.download_data import download_school_data
from datetime import datetime
from flask_socketio import SocketIO, emit # Importar SocketIO e emit

UPLOAD_FOLDER = 'Files'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

app = Flask(__name__)
app.secret_key = 'sua_chave_super_secreta' # Mantenha esta chave secreta e considere usar uma variável de ambiente
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Inicializar SocketIO
socketio = SocketIO(app, async_mode='eventlet') # Usar eventlet para async_mode

# Limpar a pasta UPLOAD_FOLDER no início da aplicação para garantir um estado limpo
# Esta parte pode ser refeita para limpar apenas arquivos de processamento anterior,
# se necessário, para evitar apagar arquivos importantes caso o Flask reinicie.
# Por enquanto, manteremos como está, mas é algo a considerar.
if os.path.exists(UPLOAD_FOLDER):
    shutil.rmtree(UPLOAD_FOLDER)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_files_async(folder_path, sid):
    """
    Função para processar arquivos em uma thread separada.
    Agora recebe o Session ID (sid) para emitir eventos SocketIO.
    """
    try:
        ExtractData(folder_path=folder_path).run()
        # Enviar mensagem de sucesso para o cliente específico
        socketio.emit('processing_complete', {'status': 'success', 'message': 'Arquivos processados com sucesso!'}, room=sid)
    except Exception as e:
        # Enviar mensagem de erro para o cliente específico
        socketio.emit('processing_complete', {'status': 'error', 'message': f'Ocorreu um erro durante o processamento: {str(e)}'}, room=sid)
    finally:
        # Limpar a pasta após o processamento, independentemente do sucesso ou falha
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True) # Recria a pasta vazia


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Captura o Session ID do SocketIO se disponível
        # Se não houver um SID (por exemplo, na primeira carga da página sem SocketIO conectado),
        # você pode lidar com isso ou garantir que o SocketIO esteja sempre conectado.
        # Por enquanto, faremos a verificação no JavaScript.
        # O SID será passado do cliente via um campo oculto no formulário ou através do JavaScript após a conexão do SocketIO.
        # Para simplificar agora, vamos assumir que o `request.sid` pode ser usado se o SocketIO estiver integrado
        # na mesma requisição POST, mas é mais comum o SocketIO ter um SID separado.
        # Uma abordagem mais robusta é usar um campo oculto no formulário.
        client_sid = request.form.get('socket_id') # Adicionar um campo oculto no form para o SID

        if 'files' not in request.files:
            flash('Nenhum arquivo enviado.', 'warning')
            return redirect(request.url)

        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            flash('Nenhum arquivo selecionado.', 'warning')
            return redirect(request.url)

        # Garante que a pasta de upload esteja limpa antes de salvar novos arquivos
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            shutil.rmtree(app.config['UPLOAD_FOLDER'])
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        files_saved = False
        for file in files:
            if file and allowed_file(file.filename):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)
                files_saved = True
            else:
                flash(f'Tipo de arquivo inválido: {file.filename}. Use apenas arquivos .xls ou .xlsx.', 'danger')

        if files_saved:
            if client_sid:
                # Inicia o processamento em uma nova thread, passando o SID
                # Flask-SocketIO lida com o contexto de aplicação para emissões
                socketio.start_background_task(process_files_async, app.config['UPLOAD_FOLDER'], client_sid)
                flash('Processamento dos arquivos iniciado em segundo plano.', 'info')
            else:
                flash('Erro: Não foi possível obter o ID de sessão para notificação. O processamento pode ter começado, mas você não será notificado.', 'warning')
        else:
            flash('Nenhum arquivo válido foi selecionado para processamento.', 'warning')

        return redirect(request.url)

    return render_template('index.html')

@app.route('/relatorio', methods=['GET'])
def relatorio():
    return redirect("http://localhost:8501")


@app.route('/historico', methods=['POST'])
def historico():
    aluno_nome = request.form.get('aluno')

    if not aluno_nome:
        flash('Por favor, digite o nome do aluno para baixar o histórico.', 'warning')
        return redirect(url_for('index'))

    output, error = school_history(studant=aluno_nome)

    if error:
        flash(f'Erro ao gerar histórico para {aluno_nome}: {error}', 'danger')
        return redirect(url_for('index'))

    try:
        return send_file(output, as_attachment=True, download_name=f"historico_{aluno_nome}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o arquivo de histórico: {str(e)}', 'danger')
        return redirect(url_for('index'))


@app.route('/baixar_dados', methods=['GET'])
def baixar_dados():
    output, error = download_school_data()

    if error:
        flash(f'Erro ao baixar dados: {error}', 'danger')
        return redirect(url_for('index'))

    try:
        return send_file(output, as_attachment=True, download_name=f"dados_alunos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Erro ao enviar o arquivo de dados: {str(e)}', 'danger')
        return redirect(url_for('index'))

@socketio.on('connect')
def test_connect():
    # Emitir o SID de volta para o cliente quando ele se conectar
    emit('my_response', {'data': 'Conectado', 'sid': request.sid})
    print(f'Cliente conectado: {request.sid}')

@socketio.on('disconnect')
def test_disconnect():
    print('Cliente desconectado')


if __name__ == '__main__':
    # Use socketio.run(app) em vez de app.run(debug=True)
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug=True para evitar aviso em debug