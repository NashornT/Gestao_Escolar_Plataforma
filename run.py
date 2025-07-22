# ETL_Excel/run.py

from app import create_app, socketio

# Cria a instância da aplicação usando a factory function do __init__.py
app = create_app()

if __name__ == '__main__':
    # Usa o socketio.run() para que o servidor web suporte WebSockets,
    # que é necessário para a comunicação em tempo real do processamento de arquivos.
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)