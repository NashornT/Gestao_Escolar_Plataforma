import xlrd
import pandas as pd

# Extraindo dados de um arquivo .xls

# Caminho do arquivo
arquivo_xls = r"C:\Users\gusta\PycharmProjects\ETL_Excel\1° ANO - T.xls"

# Abrir o arquivo .xls
workbook = xlrd.open_workbook(arquivo_xls)

# Selecionar a primeira planilha
sheet = workbook.sheet_by_index(0)

studant = None
studant_dict = dict()
disciplines_columns = ['Língua Portuguesa','Artes', 'Ciências', 'Matemática', 'Geografia', 'História', 'Cidadania/Ética', 'Inglês']
other_columns = ['CÓDIGOS E', 'FALTAS', 'RC', '1° Ano de Escolaridade']

# Iterar pelas linhas
for row_idx in range(sheet.nrows):

    studant_data = list()
    for numb, data in enumerate(sheet.row_values(row_idx)):

        if "Aluno" in str(data):
            studant = data
            studant_dict.update({studant: {}})

        elif data != "":
            studant_data.append(data)


    if len(studant_data) > 1:
        key = studant_data[1]

        if key == "CÓDIGOS E":
            key = studant_data[2]
            studant_data.remove("CÓDIGOS E")

        elif key not in disciplines_columns :
            key = studant_data[0]
        

        if key in disciplines_columns:

            for data in studant_data:
                if type(data) == str:
                    studant_data.remove(data)     

        if key in studant_data:
            studant_data.remove(key)


        studant_dict.get(studant).update({key: studant_data})


    
# Manipulando os dados

# Converter o dicionário em um DataFrame
df = pd.DataFrame.from_dict(studant_dict, orient='index')

# Removendo colunas indesejadas
colunas_para_remover = ['ÁREAS DE','RB','LEGENDA','CONHECIMENTO']
df = df.drop(columns=colunas_para_remover)

# Exibir o DataFrame atualizado
print(df.columns)
print(df.head(100))


# Salvar o DataFrame como JSON
arquivo_json = arquivo_xls.replace(".xls", ".json")
df.to_json(arquivo_json, orient='index', force_ascii=False, indent=4)

print(f"Arquivo JSON criado em: {arquivo_json}")
