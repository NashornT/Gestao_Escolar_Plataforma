import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,  # Define o nível mínimo de log
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),  # Salva os logs em um arquivo
            logging.StreamHandler()  # Exibe os logs no console
        ]
    )
    return logging.getLogger(__name__)