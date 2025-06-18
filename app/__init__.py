from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager, unset_jwt_cookies
from flask_socketio import SocketIO
from methods.logging_config import setup_logging
import eventlet # Necessário para async_mode='eventlet'
import os

db = SQLAlchemy()
login_manager = LoginManager()
jwt = JWTManager()
socketio = SocketIO()
logger = setup_logging()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config') # Carrega as configurações do config.py

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login' # Define para onde redirecionar se não logado
    jwt.init_app(app)
    socketio.init_app(app, async_mode='eventlet')

    # Importar e registrar os Blueprints
    from app.auth import auth_bp
    from app.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Registro do user_loader para Flask-Login (ainda útil para current_user em templates)
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Rotas de erro JWT (ainda em app/__init__.py ou em um blueprint específico de erros)
    @jwt.unauthorized_loader
    def unauthorized_response(callback):
        #flash('Você precisa estar logado para acessar esta página.', 'danger')
        return redirect(url_for('auth_bp.login')) # Note a mudança para 'auth_bp.login'

    @jwt.invalid_token_loader
    def invalid_token_response(callback):
        flash('Token de autenticação inválido. Por favor, faça login novamente.', 'danger')
        return redirect(url_for('auth_bp.login')) # Note a mudança

    @jwt.expired_token_loader
    def expired_token_response(callback):
        flash('Sua sessão expirou. Por favor, faça login novamente.', 'warning')
        response = redirect(url_for('auth_bp.login')) # Note a mudança
        unset_jwt_cookies(response)
        return response

    # Garante que a pasta de upload exista
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


    return app