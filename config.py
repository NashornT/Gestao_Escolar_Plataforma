import os
from storage.db_keys import user, password, host, port, database_audit, database


class Config:
    # Chave secreta para proteger as sessões do Flask-Login
    SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-secreta-para-sessoes-flask-login')

    # Configuração dos Bancos de Dados (continua igual)
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{user}:{password}@{host}:{port}/{database_audit}?charset=utf8mb4'
    SQLALCHEMY_BINDS = {
        'academic': f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4'
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configurações do Projeto (continua igual)
    UPLOAD_FOLDER = 'Files'
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)