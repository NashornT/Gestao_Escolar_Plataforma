from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from methods.logging_config import setup_logging
from sqlalchemy import (Table, MetaData, Column, Integer, String, DateTime, Text, Date, ForeignKey, BOOLEAN, BIGINT)
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
        professores_turmas_disciplinas_table, anuncio_table, material_aula_table, comentario_anuncio_table, \
        notificacao_table, audit_log_table, diario_de_classe_table

    with app.app_context():
        try:
            logger.info("Verificando e definindo as tabelas dos bancos de dados...")

            # --- BANCO DE DADOS DE AUDITORIA E USUÁRIOS (PADRÃO) ---
            audit_engine = db.get_engine()

            audit_log_table = Table('audit_log', db.metadata,
                                    Column('id', Integer, primary_key=True, autoincrement=True),
                                    Column('data_acao', DateTime, default=datetime.now),
                                    Column('usuario_id', Integer, ForeignKey('user.id'), nullable=True),
                                    Column('acao', String(20)),
                                    Column('tabela_afetada', String(100)),
                                    Column('registro_afetado_id', String(255), nullable=True),
                                    Column('valor_anterior', Text, nullable=True),
                                    Column('valor_novo', Text, nullable=True)
                                    )

            notificacao_table = Table('notificacoes', db.metadata,
                                      Column('notificacao_id', Integer, primary_key=True, autoincrement=True),
                                      Column('user_id_destino', Integer, ForeignKey('user.id', ondelete='CASCADE'),
                                             nullable=False),
                                      Column('mensagem', String(255), nullable=False),
                                      Column('link', String(255)),
                                      Column('data_criacao', DateTime, nullable=False),
                                      Column('lida', BOOLEAN, nullable=False, default=False)
                                      )
            # Cria as tabelas de auditoria e notificação se não existirem
            db.metadata.create_all(bind=audit_engine, tables=[audit_log_table, notificacao_table])

            from app import audit_log
            audit_log.audit_log_table = audit_log_table

            # --- BANCO DE DADOS ACADÊMICO ---
            academic_engine = db.get_engine(bind='academic')
            academic_metadata = MetaData()

            # Definição das tabelas que vêm do ETL (com estrutura básica)
            professor_table = Table('professores', academic_metadata,
                                    Column('professor_id', String(255), primary_key=True),
                                    autoload_with=academic_engine, extend_existing=True)
            turma_table = Table('turmas', academic_metadata, Column('turma_id', String(255), primary_key=True),
                                autoload_with=academic_engine, extend_existing=True)
            disciplina_table = Table('materias', academic_metadata, Column('disciplina_id', BIGINT, primary_key=True),
                                     autoload_with=academic_engine, extend_existing=True)
            aluno_table = Table('alunos', academic_metadata, Column('aluno_id', String(255), primary_key=True),
                                autoload_with=academic_engine, extend_existing=True)

            # Definição explícita das tabelas de relacionamento
            anuncio_table = Table('anuncios', academic_metadata,
                                  Column('anuncio_id', Integer, primary_key=True, autoincrement=True),
                                  Column('professor_id', String(255), ForeignKey('professores.professor_id'),
                                         nullable=False),
                                  Column('titulo', String(255), nullable=False),
                                  Column('conteudo', Text, nullable=False),
                                  Column('data_postagem', DateTime, nullable=False)
                                  )

            material_aula_table = Table('materiais_aula', academic_metadata,
                                        Column('material_id', Integer, primary_key=True, autoincrement=True),
                                        Column('professor_id', String(255), ForeignKey('professores.professor_id'),
                                               nullable=False),
                                        Column('turma_id', String(255), ForeignKey('turmas.turma_id'), nullable=False),
                                        Column('disciplina_id', BIGINT, ForeignKey('materias.disciplina_id'),
                                               nullable=False),
                                        Column('titulo', String(255), nullable=False),
                                        Column('descricao', Text),
                                        Column('link_arquivo', String(255), nullable=False),
                                        Column('data_upload', DateTime, nullable=False)
                                        )

            professores_turmas_disciplinas_table = Table('professores_turmas_disciplinas', academic_metadata,
                                                         Column('id', Integer, primary_key=True, autoincrement=True),
                                                         Column('professor_id', String(255),
                                                                ForeignKey('professores.professor_id'), nullable=False),
                                                         Column('turma_id', String(255), ForeignKey('turmas.turma_id'),
                                                                nullable=False),
                                                         Column('disciplina_id', BIGINT,
                                                                ForeignKey('materias.disciplina_id'), nullable=False),
                                                         Column('ano_letivo', String(4), nullable=False)
                                                         )

            comentario_anuncio_table = Table('comentarios_anuncios', academic_metadata,
                                             Column('comentario_id', Integer, primary_key=True, autoincrement=True),
                                             Column('anuncio_id', Integer,
                                                    ForeignKey('anuncios.anuncio_id', ondelete='CASCADE'),
                                                    nullable=False),
                                             Column('user_id', Integer, nullable=False),
                                             Column('nome_usuario', String(255), nullable=False),
                                             Column('conteudo', Text, nullable=False),
                                             Column('data_comentario', DateTime, nullable=False)
                                             )

            diario_de_classe_table = Table('diario_de_classe', academic_metadata,
                                           Column('diario_id', Integer, primary_key=True, autoincrement=True),
                                           Column('professor_id', String(255), nullable=False),
                                           Column('turma_id', String(255), nullable=False),
                                           Column('disciplina_id', Integer, nullable=False),
                                           Column('data_aula', Date, nullable=False),
                                           Column('conteudo_ministrado', Text, nullable=False),
                                           Column('observacoes', Text, nullable=True)
                                           )

            # Carrega as tabelas restantes que dependem do ETL
            nota_table = Table('notas', academic_metadata, autoload_with=academic_engine, extend_existing=True)
            alunos_turma_table = Table('alunos_turma', academic_metadata, autoload_with=academic_engine,
                                       extend_existing=True)

            # Cria APENAS as tabelas que foram definidas explicitamente (as de relacionamento) se não existirem
            academic_metadata.create_all(bind=academic_engine)
            logger.info("Tabelas definidas e verificadas com sucesso.")

        except Exception as e:
            logger.error(f"Falha CRÍTICA ao definir as tabelas: {e}", exc_info=True)

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