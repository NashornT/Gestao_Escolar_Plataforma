# Importe as ferramentas necessárias
from app import db
from app.models import User


def create_admin(app):
    """
    Cria o usuário 'admin' se ele não existir, dentro do contexto da aplicação.
    """
    # app.app_context() "acorda" a aplicação para que possamos usar o db
    with app.app_context():
        # Verifica se o usuário já existe
        admin_user = User.query.filter_by(username='admin').first()

        if not admin_user:
            print("Usuário 'admin' não encontrado, criando...")

            # Cria a nova instância do usuário
            new_admin = User(username='admin', is_admin=True, role='admin')
            new_admin.set_password('senha123')

            # Salva no banco de dados
            db.session.add(new_admin)
            db.session.commit()
            print("Usuário 'admin' criado com sucesso!")
        else:
            print("Usuário 'admin' já existe.")