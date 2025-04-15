import xlrd
import json

# Caminho do arquivo
arquivo_xls = r"C:\Users\gusta\PycharmProjects\PythonProject\1° ANO - T.xls"

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
    


arquivo_json = arquivo_xls.replace(".xls", ".json")

# Salvar o dicionário como JSON
with open(arquivo_json, 'w', encoding='utf-8') as jsonfile:
    json.dump(studant_dict, jsonfile, ensure_ascii=False, indent=4)

print(f"Arquivo JSON criado em: {arquivo_json}")
