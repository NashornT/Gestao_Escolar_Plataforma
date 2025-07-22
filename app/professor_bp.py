from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.sql import select, update, insert, join
from app import db, logger
from app import turma_table, disciplina_table, aluno_table, nota_table, alunos_turma_table  # Importa a nova tabela
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
    turma_id = request.args.get('turma_id')
    disciplina_id = request.args.get('disciplina_id', type=int)
    if not turma_id or not disciplina_id:
        return jsonify({'error': 'ID da Turma e da Disciplina são obrigatórios'}), 400

    dados_formatados = []
    academic_engine = db.get_engine(bind='academic')
    with academic_engine.connect() as connection:
        # CORREÇÃO: Faz o JOIN entre alunos e alunos_turma para encontrar os alunos certos
        j = join(aluno_table, alunos_turma_table, aluno_table.c.aluno_id == alunos_turma_table.c.aluno_id)
        query_alunos = select(aluno_table.c.aluno_id, aluno_table.c.aluno).select_from(j).where(
            alunos_turma_table.c.turma_id == turma_id).order_by(aluno_table.c.aluno)
        alunos = connection.execute(query_alunos).all()

        for aluno in alunos:
            # Busca a ÚNICA linha de nota para este aluno e disciplina
            query_nota = select(nota_table).where(
                nota_table.c.aluno_id == aluno.aluno_id,
                nota_table.c.disciplina_id == disciplina_id
            )
            registro_nota = connection.execute(query_nota).first()

            if not registro_nota:
                # Se não existir, insere uma linha de nota vazia para o aluno
                stmt = insert(nota_table).values(aluno_id=aluno.aluno_id, disciplina_id=disciplina_id,
                                                 ano_letivo=turma_id.split('-')[-1].strip())
                result = connection.execute(stmt)
                connection.commit()
                # Busca o registro recém-criado
                registro_nota = connection.execute(
                    select(nota_table).where(nota_table.c.nota_id == result.inserted_primary_key[0])).first()

            # CORREÇÃO: Monta a estrutura de bimestres a partir das colunas
            notas_aluno = {
                'nota_id': registro_nota.nota_id,
                'bimestres': {
                    'b1': {'valor': registro_nota.nota_1_bimestre if registro_nota.nota_1_bimestre is not None else ''},
                    'b2': {'valor': registro_nota.nota_2_bimestre if registro_nota.nota_2_bimestre is not None else ''},
                    'b3': {'valor': registro_nota.nota_3_bimestre if registro_nota.nota_3_bimestre is not None else ''},
                    'b4': {'valor': registro_nota.nota_4_bimestre if registro_nota.nota_4_bimestre is not None else ''}
                },
                'total_faltas': registro_nota.total_faltas if registro_nota.total_faltas is not None else ''
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
                campo = item.get('campo')  # Ex: 'nota_1_bimestre' ou 'total_faltas'
                valor_str = item.get('valor')

                # Validação
                valor = None
                if valor_str not in [None, '']:
                    if 'nota' in campo:
                        valor = decimal.Decimal(valor_str)
                        if not (0 <= valor <= 10):
                            raise ValueError("Nota fora do intervalo (0-10).")
                    else:  # Faltas
                        valor = int(valor_str)
                        if valor < 0:
                            raise ValueError("Faltas não podem ser negativas.")

                # CORREÇÃO: Monta o UPDATE para a coluna específica
                stmt = update(nota_table).where(nota_table.c.nota_id == nota_id).values({campo: valor})
                connection.execute(stmt)

            connection.commit()
            return jsonify({'success': True, 'message': 'Dados atualizados com sucesso!'})
        except Exception as e:
            connection.rollback()
            logger.error(f"Erro de banco de dados ao atualizar: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Ocorreu um erro: {e}'}), 500