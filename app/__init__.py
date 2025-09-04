from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from methods.logging_config import setup_logging
from sqlalchemy import Table, MetaData, Column, Integer, String, DateTime, Text, Date
import logging

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
logger = logging.getLogger(__name__)

# Declaração de todas as variáveis de tabela
turma_table = None
disciplina_table = None
aluno_table = None
nota_table = None
alunos_turma_table = None
professor_table = None
professores_turmas_disciplinas_table = None
anuncio_table = None
material_aula_table = None
comentario_anuncio_table = None
notificacao_table = None
audit_log_table = None
diario_de_classe_table = None


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

    global turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table, professor_table, \
        professores_turmas_disciplinas_table, anuncio_table, material_aula_table, comentario_anuncio_table, notificacao_table, \
        diario_de_classe_table

    with app.app_context():
        try:
            logger.info("Tentando refletir as tabelas dos bancos de dados...")

            # Reflete a tabela do banco de auditoria
            audit_engine = db.get_engine()

            # Definição explícita da tabela de auditoria para garantir sua criação
            audit_log_table = Table('audit_log', db.metadata,
                                    Column('id', Integer, primary_key=True),
                                    Column('data_acao', DateTime, default=datetime.now),
                                    Column('usuario_id', Integer, nullable=True),  # Permitir nulo para ações do sistema
                                    Column('acao', String(20)),
                                    Column('tabela_afetada', String(100)),
                                    Column('registro_afetado_id', String(255), nullable=True),
                                    Column('valor_anterior', Text, nullable=True),
                                    Column('valor_novo', Text, nullable=True)
                                    )

            notificacao_table = Table('notificacoes', db.metadata, autoload_with=audit_engine)
            db.metadata.create_all(bind=audit_engine, tables=[audit_log_table])


            # Inicializa o módulo de log com a tabela
            from app import audit_log
            audit_log.audit_log_table = audit_log_table

            # Reflete as tabelas do banco acadêmico
            academic_engine = db.get_engine(bind='academic')
            academic_metadata = MetaData()
            turma_table = Table('turmas', academic_metadata, autoload_with=academic_engine)
            disciplina_table = Table('materias', academic_metadata, autoload_with=academic_engine)
            aluno_table = Table('alunos', academic_metadata, autoload_with=academic_engine)
            nota_table = Table('notas', academic_metadata, autoload_with=academic_engine)
            alunos_turma_table = Table('alunos_turma', academic_metadata, autoload_with=academic_engine)
            professor_table = Table('professores', academic_metadata, autoload_with=academic_engine)
            professores_turmas_disciplinas_table = Table('professores_turmas_disciplinas', academic_metadata,
                                                         autoload_with=academic_engine)
            anuncio_table = Table('anuncios', academic_metadata, autoload_with=academic_engine)
            material_aula_table = Table('materiais_aula', academic_metadata, autoload_with=academic_engine)
            comentario_anuncio_table = Table('comentarios_anuncios', academic_metadata, autoload_with=academic_engine)


            diario_de_classe_table = Table('diario_de_classe', academic_metadata,
                                            Column('diario_id', Integer, primary_key=True),
                                            Column('professor_id', String(255)),
                                            Column('turma_id', String(255)),
                                            Column('disciplina_id', Integer),
                                            Column('data_aula', Date),
                                            Column('conteudo_ministrado', Text),
                                            Column('observacoes', Text, nullable=True),
                                            autoload_with=academic_engine)

            logger.info("Tabelas refletidas com sucesso.")
        except Exception as e:
            logger.error(f"Falha CRÍTICA ao refletir as tabelas: {e}", exc_info=True)

    # Registra os Blueprints
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)
    from app.main import main_bp
    app.register_blueprint(main_bp)
    from app.professor_bp import professor_bp
    app.register_blueprint(professor_bp)
    from app.aluno_bp import aluno_bp
    app.register_blueprint(aluno_bp)
    from app.account_bp import account_bp
    app.register_blueprint(account_bp)
    from app.notification_bp import notification_bp
    app.register_blueprint(notification_bp)

    # Configura o user_loader do Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app