from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db, login_manager, jwt  # Importa os objetos inicializados
from app.models import User
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies, \
    set_access_cookies, get_csrf_token  # Importe get_csrf_token
from flask_login import current_user, logout_user
from datetime import timedelta  # Importe timedelta

auth_bp = Blueprint('auth_bp', __name__, template_folder='../templates/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Você já está logado.', 'info')
        return redirect(url_for('main_bp.index'))

    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('register.html')

        if len(password) < 8 or not any(char.isdigit() for char in password) or not any(
                char.isupper() for char in password) or not any(char.islower() for char in password):
            flash('A senha deve ter no mínimo 8 caracteres, incluindo letras maiúsculas, minúsculas e números.',
                  'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Nome de usuário já existe. Por favor, escolha outro.', 'danger')
            return render_template('register.html')

        # Por padrão, novos usuários registrados são 'student' e is_admin=False
        new_user = User(username=username, is_admin=False, role='student')
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Cadastro realizado com sucesso! Faça o login.', 'success')
        return redirect(url_for('auth_bp.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # Cria o token de acesso. A 'identity' deve ser algo único do usuário.
            access_token = create_access_token(identity=user.username)

            response = redirect(url_for('main_bp.get_files'))  # Redireciona para a página principal após o login

            # Define os cookies JWT de acesso e CSRF
            set_access_cookies(response, access_token)

            flash(f"Bem-vindo, {user.username}! Você está logado como {user.role}.", "success")
            return response
        else:
            flash("Usuário ou senha inválidos", "danger")

    return render_template("login.html")


@auth_bp.route('/logout')
@jwt_required(optional=True)  # Permite logout mesmo se o token já expirou ou não existe
def logout():
    response = redirect(url_for('auth_bp.login'))
    unset_jwt_cookies(response)  # Remove todos os cookies JWT
    logout_user()  # Desloga do Flask-Login
    flash('Você foi desconectado.', 'info')
    return response


# Rota para obter o token CSRF para requisições AJAX
@auth_bp.route('/csrf-token', methods=['GET'])
@jwt_required()
def get_csrf():
    return {'csrf_token': get_csrf_token()}