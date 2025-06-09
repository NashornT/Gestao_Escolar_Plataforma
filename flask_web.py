from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from methods.extract_data import ExtractData
import os
import shutil
from methods.create_school_history import school_history
from methods.download_data import download_school_data
from datetime import datetime
from flask_socketio import SocketIO, emit
import eventlet # Necessário para async_mode='eventlet'

UPLOAD_FOLDER = 'Files'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

app = Flask(__name__)
app.secret_key = 'sua_chave_super_secreta' # Mantenha esta chave secreta e considere usar uma variável de ambiente em produção
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db' # Nome do seu arquivo de banco de dados SQLite
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Desativa o rastreamento de modificações para economizar recursos

db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='eventlet')

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Define a rota para onde o usuário será redirecionado se não estiver logado

# --- Modelos do Banco de Dados ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # Exemplo de campo adicional

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# Callback para recarregar o usuário do Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Limpeza da pasta de upload (considerar ajustar para produção) ---
if os.path.exists(UPLOAD_FOLDER):
    shutil.rmtree(UPLOAD_FOLDER)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Funções Auxiliares ---
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

# --- Rotas da Aplicação ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Você já está logado.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Nome de usuário já existe. Por favor, escolha outro.', 'danger')
            return render_template('register.html')

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Cadastro realizado com sucesso! Faça o login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Você já está logado.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Bem-vindo, {user.username}!', 'success')
            next_page = request.args.get('next') # Redireciona para a página que o usuário tentou acessar
            return redirect(next_page or url_for('index'))
        else:
            flash('Login ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required # Só pode acessar se estiver logado
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # ... (Sua lógica existente para processar arquivos) ...
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
                socketio.start_background_task(process_files_async, app.config['UPLOAD_FOLDER'], client_sid)
                flash('Processamento dos arquivos iniciado em segundo plano.', 'info')
            else:
                flash('Erro: Não foi possível obter o ID de sessão para notificação. O processamento pode ter começado, mas você não será notificado.', 'warning')
        else:
            flash('Nenhum arquivo válido foi selecionado para processamento.', 'warning')

        return redirect(request.url)

    return render_template('index.html')


@app.route('/relatorio', methods=['GET'])
@login_required # Protege a rota
def relatorio():
    return redirect("http://localhost:8501")

@app.route('/historico', methods=['POST'])
@login_required # Protege a rota
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
@login_required # Protege a rota
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

# --- SocketIO Handlers (permanecem os mesmos) ---
@socketio.on('connect')
def test_connect():
    emit('my_response', {'data': 'Conectado', 'sid': request.sid})
    print(f'Cliente conectado: {request.sid}')

@socketio.on('disconnect')
def test_disconnect():
    print('Cliente desconectado')


# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Cria as tabelas do banco de dados (se não existirem)
        # Opcional: Criar um usuário admin inicial se o banco estiver vazio
        if User.query.filter_by(username='admin').first() is None:
            admin_user = User(username='admin', is_admin=True)
            admin_user.set_password('admin123') # Troque por uma senha forte!
            db.session.add(admin_user)
            db.session.commit()
            print("Usuário 'admin' criado com senha 'admin123'. Por favor, altere em produção!")

    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)