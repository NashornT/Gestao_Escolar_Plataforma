from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db, login_manager, jwt # Importa os objetos inicializados
from app.models import User
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies, \
    set_access_cookies, get_csrf_token
from flask_login import current_user, logout_user # Importar current_user e logout_user
from datetime import timedelta

auth_bp = Blueprint('auth_bp', __name__, template_folder='../templates')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Você já está logado.', 'info')
        return redirect(url_for('main_bp.index')) # Note a mudança para 'main_bp.index'

    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('register.html')

        if len(password) < 8 or not any(char.isdigit() for char in password) or not any(char.isupper() for char in password) or not any(char.islower() for char in password) or not any(char in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for char in password):
            flash('A senha deve ter pelo menos 8 caracteres, incluindo letras maiúsculas, minúsculas, números e caracteres especiais.', 'danger')
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
        return redirect(url_for('auth_bp.login'))

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            access_token = create_access_token(identity=user.username)

            response = redirect(url_for('main_bp.index'))
            set_access_cookies(response, access_token)

            flash(f"Bem-vindo, {user.username}!", "success")
            return response
        else:
            flash("Usuário ou senha inválidos", "danger")

    return render_template("login.html")


@auth_bp.route('/logout')
def logout():
    response = redirect(url_for('auth_bp.login'))
    unset_jwt_cookies(response)
    logout_user() # Mantém o logout do Flask-Login para consistência, se ainda estiver usando
    flash('Você foi desconectado.', 'info')
    return response
