from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.models import User
from app import db
from flask_login import login_user, logout_user, login_required, current_user
from app import turma_table, disciplina_table, professor_table, professores_turmas_disciplinas_table
from datetime import datetime

# A correção está na linha abaixo.
# Apontamos para a pasta 'templates' na raiz do projeto.
auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Evita que um usuário já logado acesse a página de login novamente
    if current_user.is_authenticated:
        return redirect(url_for('main_bp.get_files'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Usuário ou senha inválidos. Por favor, verifique seus dados e tente novamente.', 'danger')
            return redirect(url_for('auth.login'))

        # Registra o login do usuário
        login_user(user, remember=remember)

        # Atualiza o campo last_login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Redireciona para a página principal após o login
        return redirect(url_for('main_bp.get_files'))

    # Agora o Flask saberá encontrar 'auth/login.html' dentro da pasta 'templates'
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado com sucesso.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('Este nome de usuário já existe.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, role='student')  # Define um papel padrão
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash('Conta criada com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')