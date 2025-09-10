from flask import current_app
from flask_login import current_user
from app import db
from sqlalchemy.sql import insert
from datetime import datetime
import json

# A tabela será importada do __init__ quando a app for criada
audit_log_table = None

def log_action(action, table_affected, record_id=None, old_value=None, new_value=None):
    """
    Registra uma ação na trilha de auditoria.
    """
    # Garante que temos a tabela carregada
    global audit_log_table
    if audit_log_table is None:
        audit_log_table = db.metadata.tables.get('audit_log')
        if audit_log_table is None:
            current_app.logger.error("Tabela de auditoria 'audit_log' não encontrada.")
            return

    try:
        # Garante que o usuário está autenticado para pegar o ID
        user_id = current_user.id if current_user.is_authenticated else None

        # Converte dicionários para string JSON
        old_value_json = json.dumps(old_value) if isinstance(old_value, dict) else old_value
        new_value_json = json.dumps(new_value) if isinstance(new_value, dict) else new_value

        stmt = insert(audit_log_table).values(
            data_acao=datetime.now(),
            usuario_id=user_id,
            acao=action.upper(),
            tabela_afetada=table_affected,
            registro_afetado_id=str(record_id) if record_id else None,
            valor_anterior=old_value_json,
            valor_novo=new_value_json
        )

        # Usa o engine de auditoria (padrão) para executar
        with db.engine.connect() as connection:
            connection.execute(stmt)
            connection.commit()

    except Exception as e:
        current_app.logger.error(f"Falha ao registrar ação de auditoria: {e}", exc_info=True)