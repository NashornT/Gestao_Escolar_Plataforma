#from extract_data import ExtractData
from test_new_extract import  ExtractData

ExtractData(
    folder_path=r'C:\Users\gusta\PycharmProjects\ETL_Excel\Files',
    db_path=r'C:\Users\gusta\PycharmProjects\ETL_Excel\Files\Banco_de_dados\Banco_de_dados.db'
).run()