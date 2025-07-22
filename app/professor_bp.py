from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.sql import select, update, insert
from app import db, logger
# Importa os objetos de tabela refletidos do __init__.py
from app import turma_table, disciplina_table, aluno_table, nota_table
# Importa o modelo User do models.py
from app.models import User
import decimal

professor_bp = Blueprint('professor_bp', __name__, url_prefix='/professor', template_folder='../templates/professor')


@professor_bp.before_request
@login_required
def check_professor_permission():
    if not (current_user.is_professor or current_user.is_admin):
        flash('Acesso negado. Esta área é restrita a professores e administradores.', 'danger')
        return redirect(url_for('main_bp.get_files'))


@professor_bp.route('/notas')
def gerenciar_notas():
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        turmas = connection.execute(select(turma_table).order_by(turma_table.c.turma)).all()
        disciplinas = connection.execute(select(disciplina_table).order_by(disciplina_table.c.disciplina)).all()

    return render_template(
        'professor/notas.html',
        turmas=turmas,
        disciplinas=disciplinas,
        username=current_user.username,
        user_role=current_user.role
    )

@professor_bp.route('/api/dados_turma')
def api_dados_turma():
    turma_id = request.args.get('turma_id', type=int)
    disciplina_id = request.args.get('disciplina_id', type=int)
    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    dados_formatados = []
    # --- QUERIES NO BANCO ACADÊMICO ---
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query_alunos = select(aluno_table).where(aluno_table.c.turma_id == turma_id).order_by(aluno_table.c.nome)
        alunos = connection.execute(query_alunos).all()

        for aluno in alunos:
            notas_aluno = {}
            for bimestre in range(1, 5):
                query_nota = select(nota_table).where(
                    nota_table.c.aluno_id == aluno.id,
                    nota_table.c.disciplina_id == disciplina_id,
                    nota_table.c.bimestre == bimestre
                )
                registro = connection.execute(query_nota).first()

                if not registro:
                    # Se não existir, insere um registro vazio
                    stmt = insert(nota_table).values(aluno_id=aluno.id, disciplina_id=disciplina_id, bimestre=bimestre)
                    result = connection.execute(stmt)
                    # Busca o registro recém-criado para obter os valores padrão
                    registro = connection.execute(
                        select(nota_table).where(nota_table.c.id == result.inserted_primary_key[0])).first()

                notas_aluno[f'b{bimestre}'] = {
                    'id': registro.id,
                    'valor': registro.valor if registro.valor is not None else '',
                    'faltas': registro.faltas if registro.faltas is not None else ''
                }
            dados_formatados.append({'id': aluno.id, 'nome': aluno.nome, 'notas': notas_aluno})

        connection.commit()  # Comita todas as inserções de uma vez

    return jsonify(dados_formatados)


@professor_bp.route('/api/atualizar_dados', methods=['POST'])
def api_atualizar_dados():
    data = request.get_json()
    if not data or 'dados' not in data:
        return jsonify({'success': False, 'message': 'Requisição inválida.'}), 400

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        try:
            for item in data['dados']:
                # ... (sua lógica de validação aqui, exatamente como antes) ...
                stmt = (
                    update(nota_table)
                    .where(nota_table.c.id == item.get('id'))
                    .values(valor=item.get('valor'), faltas=item.get('faltas'))
                # Adapte os nomes dos campos se necessário
                )
                connection.execute(stmt)

            connection.commit()
            return jsonify({'success': True, 'message': 'Dados atualizados com sucesso!'})
        except Exception as e:
            connection.rollback()
            logger.error(f"Erro de banco de dados ao atualizar: {e}", exc_info=True)
            return jsonify({'success': False, 'message': 'Ocorreu um erro interno ao salvar os dados.'}), 500