from app import create_app, socketio
from tools import create_super_user

# Cria a instância da aplicação usando a factory function do __init__.py
app = create_app()
create_super_user.create_admin(app)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)