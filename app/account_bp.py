from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db

account_bp = Blueprint('account', __name__, url_prefix='/conta', template_folder='../templates/account')


@account_bp.route('/mudar-senha', methods=['GET', 'POST'])
@login_required
def mudar_senha():
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')

        # Verifica se a senha atual está correta
        if not current_user.check_password(senha_atual):
            flash('A senha atual está incorreta.', 'danger')
            return redirect(url_for('account.mudar_senha'))

        # Verifica se a nova senha e a confirmação são iguais
        if nova_senha != confirmar_senha:
            flash('A nova senha e a confirmação não coincidem.', 'danger')
            return redirect(url_for('account.mudar_senha'))

        #TODO: Adicione aqui regras de complexidade para a nova senha
        if len(nova_senha) < 8:
            flash('A nova senha deve ter pelo menos 8 caracteres.', 'danger')
            return redirect(url_for('account.mudar_senha'))

        # Se tudo estiver correto, atualiza a senha
        current_user.set_password(nova_senha)
        db.session.commit()

        flash('Sua senha foi alterada com sucesso!', 'success')

        # Redireciona para o painel correto com base no papel do usuário
        if current_user.role == 'student':
            return redirect(url_for('aluno.painel'))
        else:
            return redirect(url_for('main_bp.get_files'))

    return render_template('mudar_senha.html', user_role=current_user.role, username=current_user.username)