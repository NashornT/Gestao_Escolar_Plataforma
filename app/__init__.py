# app/__init__.py
from datetime import datetime, timezone, timedelta

from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager, unset_jwt_cookies, get_jwt, create_access_token, get_jwt_identity, \
    set_access_cookies
from flask_socketio import SocketIO
from methods.logging_config import setup_logging  # Certifique-se de que este módulo existe e funciona
import eventlet  # Necessário para async_mode='eventlet'
import os

db = SQLAlchemy()
login_manager = LoginManager()
jwt = JWTManager()
socketio = SocketIO()
logger = setup_logging()  # Inicializa o logger


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')  # Carrega as configurações do config.py

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth_bp.login'  # Define para onde redirecionar se não logado
    jwt.init_app(app)
    socketio.init_app(app, async_mode='eventlet')

    # Importar e registrar os Blueprints
    from app.auth import auth_bp
    from app.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Registro do user_loader para Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        # Retorna o objeto User com base no user_id do Flask-Login
        return User.query.get(int(user_id))

    # Handlers de erro JWT
    @jwt.unauthorized_loader
    def unauthorized_response(callback):
        logger.warning(f"JWT_ERROR: Unauthorized - {callback}")
        flash('Você precisa estar logado para acessar esta página.', 'danger')
        response = redirect(url_for('auth_bp.login'))
        unset_jwt_cookies(response)  # Garante que cookies antigos sejam limpos
        return response

    @jwt.invalid_token_loader
    def invalid_token_response(callback):
        logger.warning(f"JWT_ERROR: Invalid Token - {callback}")
        flash('Token de autenticação inválido. Por favor, faça login novamente.', 'danger')
        response = redirect(url_for('auth_bp.login'))
        unset_jwt_cookies(response)  # Garante que cookies antigos sejam limpos
        return response

    @jwt.expired_token_loader
    def expired_token_response(callback):
        logger.warning(f"JWT_ERROR: Expired Token - {callback}")
        flash('Sua sessão expirou. Por favor, faça login novamente.', 'warning')
        response = redirect(url_for('auth_bp.login'))
        unset_jwt_cookies(response)  # Garante que cookies antigos sejam limpos
        return response

    # Hook para limpar cookies JWT ao fazer logout via Flask-Login
    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            exp_timestamp = get_jwt()['exp']
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            # Token não disponível ou outro erro, apenas continue
            return response

    return app