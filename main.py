import argparse
from extract_data import ExtractData

def main():
    # Configuração da CLI
    parser = argparse.ArgumentParser(description="Processa arquivos .xls para ETL.")
    parser.add_argument(
        '--folder_path',
        type=str,
        required=True,
        help="Caminho para a pasta contendo os arquivos .xls"
    )

    args = parser.parse_args()

    # Executa o processo de ETL
    ExtractData(folder_path=args.folder_path).run()

if __name__ == '__main__':
    main()