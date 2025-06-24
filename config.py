import os
from datetime import timedelta
from storage.db_keys import user,password,host,port,database_audit

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_super_secret_please_change_in_production')
    # SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db' # SQLite,
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{user}:{password}@{host}:{port}/{database_audit}?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'Files'
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

    JWT_SECRET_KEY = 'sua_chave_segura'
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_COOKIE_SECURE = False  # True se for HTTPS
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_CSRF_IN_COOKIES = True
    JWT_CSRF_IN_HEADERS = True

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # Configurações JWT
    #JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'super-secret-jwt-key-prod') # MUDAR
    #JWT_TOKEN_LOCATION = ["cookies"]
    #JWT_COOKIE_SECURE = False # True para HTTPS
    #JWT_COOKIE_CSRF_PROTECT = True # True para proteger contra CSRF