from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from methods.logging_config import setup_logging
from sqlalchemy import Table
import logging

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
logger = logging.getLogger(__name__)

turma_table = None
disciplina_table = None
aluno_table = None
nota_table = None
alunos_turma_table = None
professor_table = None
professores_turmas_disciplinas_table = None

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'
    setup_logging()

    # Carrega as tabelas do banco acadêmico
    global turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table, professor_table, professores_turmas_disciplinas_table
    with app.app_context():
        try:
            academic_engine = db.get_engine(bind='academic')
            turma_table = Table('turmas', db.metadata, autoload_with=academic_engine)
            disciplina_table = Table('materias', db.metadata, autoload_with=academic_engine)
            aluno_table = Table('alunos', db.metadata, autoload_with=academic_engine)
            nota_table = Table('notas', db.metadata, autoload_with=academic_engine)
            alunos_turma_table = Table('alunos_turma', db.metadata, autoload_with=academic_engine)
            professor_table = Table('professores', db.metadata, autoload_with=academic_engine) # <-- ADICIONADO
            professores_turmas_disciplinas_table = Table('professores_turmas_disciplinas', db.metadata, autoload_with=academic_engine) # <-- ADICIONADO
            logger.info("Tabelas do banco de dados acadêmico refletidas com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao refletir as tabelas do banco 'academic': {e}", exc_info=True)

    # Registra os Blueprints
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.main import main_bp
    app.register_blueprint(main_bp)

    from app.professor_bp import professor_bp
    app.register_blueprint(professor_bp)

    # Configura o user_loader do Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app