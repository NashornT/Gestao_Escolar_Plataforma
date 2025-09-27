import uuid
from datetime import datetime

class Audit:
    def __init__(self):
        pass

    def create_audit_entry(self, user_id, action, table_affected, record_id=None,
                           old_value=None, new_value=None):
        """
        :param user_id: ID do usuário que realizou a ação.
        :param action: Tipo de ação (e.g., "CREATE", "UPDATE", "DELETE").
        :param table_affected: Nome da tabela afetada.
        :param record_id: ID do registro afetado (opcional).
        :param old_value: Valor anterior do registro (JSON ou ID, opcional).
        :param new_value: Novo valor do registro (JSON ou ID, opcional).
        :return: Dicionário representando o registro de auditoria.
        """
        audit_entry = {
            "audit_id": str(uuid.uuid4()),
            "data_atualizacao": datetime.now().isoformat(), # Data e hora da auditoria
            "usuario_acao_id": user_id, # Usuário que realizou a ação
            "acao": action,
            "tabela_afetada": table_affected,
            "registro_afetado_id": record_id,
            "valor_anterior_json": old_value, # Pode ser um JSON string ou ID
            "valor_novo_json": new_value # Pode ser um JSON string ou ID
        }
        return audit_entry

    def get_audit_schema(self):
        """
        Retorna a estrutura esperada do esquema de auditoria.
        """
        return {
            "audit_id": "STRING (PK)",
            "data_atualizacao": "DATETIME",
            "usuario_acao_id": "STRING (FK para Usuário)",
            "acao": "STRING (CREATE, UPDATE, DELETE)",
            "tabela_afetada": "STRING",
            "registro_afetado_id": "STRING (ID do registro na tabela afetada, opcional)",
            "valor_anterior_json": "JSON (estado do registro antes da ação, opcional)",
            "valor_novo_json": "JSON (estado do registro após a ação, opcional)"
        }