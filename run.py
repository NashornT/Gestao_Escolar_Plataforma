from app import create_app, db, socketio, logger
from app.models import User # Importa o modelo User para create_all e criação do admin

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Garante que um usuário admin exista
        if User.query.filter_by(username='admin').first() is None:
            admin_user = User(username='admin', is_admin=True)
            admin_user.set_password('admin123') # Considere usar uma variável de ambiente para isso em produção
            db.session.add(admin_user)
            db.session.commit()
            logger.info("Usuário 'admin' criado com senha 'admin123'. Altere em produção!")

    socketio.run(app, debug=False, allow_unsafe_werkzeug=True)