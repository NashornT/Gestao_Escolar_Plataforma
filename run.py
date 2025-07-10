# run.py
from app import create_app, db, socketio, logger
from app.models import User # Importa o modelo User

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Cria todas as tabelas no banco de dados

        if User.query.filter_by(username='admin').first() is None:
            admin_user = User(username='admin', is_admin=True, role='admin')
            admin_user.set_password('admin123') # Senha para o usuário admin
            db.session.add(admin_user)
            db.session.commit()
            logger.info("Usuário 'admin' criado com senha 'admin123' e role 'admin'. Altere em produção!")
        else:
            logger.info("Usuário 'admin' já existe.")
            existing_admin = User.query.filter_by(username='admin').first()
            if existing_admin and (existing_admin.is_admin == False or existing_admin.role != 'admin'):
                existing_admin.is_admin = True
                existing_admin.role = 'admin'
                db.session.commit()
                logger.info("Informações do usuário 'admin' atualizadas (is_admin=True, role='admin').")


    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)