from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager # A estrela do nosso novo sistema de segurança
from flask_socketio import SocketIO
from methods.logging_config import setup_logging
from sqlalchemy import Table
import logging


db = SQLAlchemy()
login_manager = LoginManager() # Apenas o LoginManager para autenticação
socketio = SocketIO()
logger = logging.getLogger(__name__)

turma_table = None
disciplina_table = None
aluno_table = None
nota_table = None

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)
    # Define para onde o usuário é redirecionado se tentar acessar uma página protegida sem estar logado
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'
    setup_logging()

    global turma_table, disciplina_table, aluno_table, nota_table
    with app.app_context():
        try:
            academic_engine = db.get_engine(bind='academic')
            turma_table = Table('turmas', db.metadata, autoload_with=academic_engine)
            disciplina_table = Table('materias', db.metadata, autoload_with=academic_engine)
            aluno_table = Table('alunos', db.metadata, autoload_with=academic_engine)
            nota_table = Table('notas', db.metadata, autoload_with=academic_engine)
            logger.info("Tabelas do banco de dados acadêmico refletidas com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao refletir as tabelas do banco 'academic': {e}", exc_info=True)

    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.main import main_bp
    app.register_blueprint(main_bp)

    from app.professor_bp import professor_bp
    app.register_blueprint(professor_bp)

    # 6. Configura o user_loader do Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        # O Flask-Login armazena o ID do usuário na sessão e usa esta função para obter o objeto User a cada request
        return User.query.get(int(user_id))

    return app