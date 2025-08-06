from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user

aluno_bp = Blueprint('aluno', __name__, url_prefix='/aluno', template_folder='../templates/aluno')

@aluno_bp.before_request
@login_required
def check_student_permission():
    """Verifica se o usuário logado tem o papel de 'student'."""
    if current_user.role != 'student':
        flash('Acesso negado. Esta área é restrita a alunos.', 'danger')
        return redirect(url_for('main_bp.get_files'))

@aluno_bp.route('/painel')
def painel():
    """Exibe o painel principal do aluno."""
    return render_template(
        'painel.html',
        username=current_user.username
    )