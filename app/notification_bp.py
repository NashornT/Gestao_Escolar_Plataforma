from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app import db, notificacao_table
from sqlalchemy.sql import select, update

notification_bp = Blueprint('notification', __name__, url_prefix='/notificacoes')


@notification_bp.route('/buscar')
@login_required
def buscar_notificacoes():
    """Busca as notificações não lidas do usuário logado."""
    audit_engine = db.get_engine()
    with audit_engine.connect() as connection:
        query = select(notificacao_table).where(
            notificacao_table.c.user_id_destino == current_user.id,
            notificacao_table.c.lida == False
        ).order_by(notificacao_table.c.data_criacao.desc())

        resultados = connection.execute(query).mappings().all()
        notificacoes = [dict(row) for row in resultados]

    return jsonify(notificacoes=notificacoes, count=len(notificacoes))


@notification_bp.route('/marcar-como-lida', methods=['POST'])
@login_required
def marcar_como_lida():
    """Marca todas as notificações do usuário como lidas."""
    audit_engine = db.get_engine()
    with audit_engine.connect() as connection:
        trans = connection.begin()
        try:
            stmt = update(notificacao_table).where(
                notificacao_table.c.user_id_destino == current_user.id
            ).values(lida=True)
            connection.execute(stmt)
            trans.commit()
            return jsonify(success=True)
        except Exception:
            trans.rollback()
            return jsonify(success=False), 500