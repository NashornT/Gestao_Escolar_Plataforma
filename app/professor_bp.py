from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.sql import select, update, insert, join, distinct
from app import db, logger
from app import turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table, professor_table, professores_turmas_disciplinas_table
from datetime import datetime
import decimal

professor_bp = Blueprint('professor_bp', __name__, url_prefix='/professor')


@professor_bp.before_request
@login_required
def check_professor_permission():
    if not (current_user.is_professor or current_user.is_admin):
        flash('Acesso negado. Esta área é restrita a professores e administradores.', 'danger')
        return redirect(url_for('main_bp.get_files'))


@professor_bp.route('/notas')
def gerenciar_notas():
    username = current_user.username
    user_role = current_user.role

    # Pega o ID do professor a partir do usuário logado
    professor_id_logado = current_user.professor_id

    turmas_atribuidas = []
    disciplinas_atribuidas = []

    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        if professor_id_logado:
            # ===== INÍCIO DA CORREÇÃO =====

            # Query para buscar apenas as TURMAS atribuídas a este professor
            join_turmas = join(turma_table, professores_turmas_disciplinas_table,
                               turma_table.c.turma_id == professores_turmas_disciplinas_table.c.turma_id)

            query_turmas = select(
                distinct(turma_table.c.turma_id),
                turma_table.c.turma,
                turma_table.c.turno
            ).select_from(join_turmas).where(
                professores_turmas_disciplinas_table.c.professor_id == professor_id_logado
            ).order_by(turma_table.c.turma, turma_table.c.turno)

            turmas_atribuidas = connection.execute(query_turmas).all()

            # Query para buscar apenas as DISCIPLINAS atribuídas a este professor
            join_disciplinas = join(disciplina_table, professores_turmas_disciplinas_table,
                                    disciplina_table.c.disciplina_id == professores_turmas_disciplinas_table.c.disciplina_id)

            query_disciplinas = select(
                distinct(disciplina_table.c.disciplina_id),
                disciplina_table.c.disciplina
            ).select_from(join_disciplinas).where(
                professores_turmas_disciplinas_table.c.professor_id == professor_id_logado
            ).order_by(disciplina_table.c.disciplina)

            disciplinas_atribuidas = connection.execute(query_disciplinas).all()

            # ===== FIM DA CORREÇÃO =====

    return render_template(
        'professor/notas.html',
        turmas=turmas_atribuidas,
        disciplinas=disciplinas_atribuidas,
        username=username,
        user_role=user_role
    )


# O restante do arquivo (api_dados_turma, api_atualizar_dados) não precisa de alterações,
# pois ele já opera com os IDs de turma e disciplina que o professor seleciona na interface.
@professor_bp.route('/api/dados_turma')
def api_dados_turma():
    turma_id = request.args.get('turma_id')
    disciplina_id = request.args.get('disciplina_id', type=int)

    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    dados_formatados = []
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        query_ano_letivo = select(turma_table.c.ano_escolar).where(turma_table.c.turma_id == turma_id)
        ano_letivo = connection.execute(query_ano_letivo).scalar_one_or_none()

        if not ano_letivo:
            ano_letivo = str(datetime.now().year)

        j = join(aluno_table, alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
        query_alunos = select(aluno_table.c.aluno_id, aluno_table.c.aluno).select_from(j).where(
            alunos_turma_table.c.turma_id == turma_id).order_by(aluno_table.c.aluno)
        alunos = connection.execute(query_alunos).all()

        for aluno in alunos:
            query_nota = select(nota_table).where(
                nota_table.c.aluno_id == aluno.aluno_id,
                nota_table.c.disciplina_id == disciplina_id
            )
            registro_nota = connection.execute(query_nota).first()

            if not registro_nota:
                stmt = insert(nota_table).values(aluno_id=aluno.aluno_id, disciplina_id=disciplina_id,
                                                 ano_letivo=ano_letivo)
                result = connection.execute(stmt)
                connection.commit()
                registro_nota = connection.execute(
                    select(nota_table).where(nota_table.c.nota_id == result.inserted_primary_key[0])).first()

            notas_aluno = {
                'nota_id': registro_nota.nota_id,
                'bimestres': {
                    'b1': {'valor': registro_nota.nota_1_bimestre},
                    'b2': {'valor': registro_nota.nota_2_bimestre},
                    'b3': {'valor': registro_nota.nota_3_bimestre},
                    'b4': {'valor': registro_nota.nota_4_bimestre}
                },
                'total_faltas': registro_nota.total_faltas
            }
            dados_formatados.append({'id': aluno.aluno_id, 'nome': aluno.aluno, 'dados_nota': notas_aluno})

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
                nota_id = item.get('nota_id')
                campo = item.get('campo')
                valor_str = item.get('valor')
                valor = None

                if valor_str not in [None, '']:
                    try:
                        numeric_value = float(valor_str)
                    except ValueError:
                        raise ValueError(f"Valor '{valor_str}' não é um número válido.")

                    if 'nota' in campo:
                        if not (0 <= numeric_value <= 10):
                            raise ValueError("A nota deve estar entre 0 e 10.")
                        valor = numeric_value
                    else:
                        if numeric_value < 0:
                            raise ValueError("O número de faltas não pode ser negativo.")
                        valor = int(numeric_value)

                stmt = update(nota_table).where(nota_table.c.nota_id == nota_id).values({campo: valor})
                connection.execute(stmt)

            connection.commit()
            return jsonify({'success': True, 'message': 'Dados atualizados com sucesso!'})
        except Exception as e:
            connection.rollback()
            logger.error(f"Erro de banco de dados ao atualizar: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Ocorreu um erro: {str(e)}'}), 500