import xlrd
import pandas as pd
import os


class ExtractData:

    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.file = None
        self.workbook = None
        self.sheet = None
        self.studant = None
        self.studant_dict = dict()
        self.disciplines_columns = ['Língua Portuguesa', 'Artes', 'Ciências', 'Matemática', 'Geografia', 'História',
                                    'Cidadania/Ética', 'Inglês']
        self.other_columns = ['CÓDIGOS E', 'FALTAS', 'RC', '1° Ano de Escolaridade']

    def open_file(self):
        """Open the .xls file."""
        self.workbook = xlrd.open_workbook(self.file)
        self.sheet = self.workbook.sheet_by_index(0)


    def get_data(self):
        """Extract data from the .xls file."""
        for row_idx in range(self.sheet.nrows):
            studant_data = list()
            for numb, data in enumerate(self.sheet.row_values(row_idx)):
                if "Aluno" in str(data):
                    self.studant = data
                    self.studant_dict.update({self.studant: {}})
                elif data != "":
                    studant_data.append(data)

            if len(studant_data) > 1:
                key = studant_data[1]
                if key == "CÓDIGOS E":
                    key = studant_data[2]
                    studant_data.remove("CÓDIGOS E")
                elif key not in self.disciplines_columns:
                    key = studant_data[0]

                if key in self.disciplines_columns:
                    for data in studant_data:
                        if type(data) == str:
                            studant_data.remove(data)

                if key in studant_data:
                    studant_data.remove(key)

                self.studant_dict.get(self.studant).update({key: studant_data})


    def manipulate_data(self):
        """Manipulate the extracted data."""
        # Convert the dictionary to a DataFrame
        df = pd.DataFrame.from_dict(self.studant_dict, orient='index')

        # Remove unwanted columns
        colunas_para_remover = ['ÁREAS DE', 'RB', 'LEGENDA', 'CONHECIMENTO']
        df = df.drop(columns=colunas_para_remover)

        output_folder = self.folder_path + "/outputs"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        json_file = self.file.replace(".xls", ".json")
        json_file = os.path.join(output_folder, os.path.basename(json_file))

        df.to_json(json_file, orient='index', force_ascii=False, indent=4)

        print(f"Arquivo JSON criado em: {json_file}")


    def run(self):
        """Run the extraction and manipulation process."""
        
        for file in os.listdir(self.folder_path):
            if file.endswith('.xls'):
                self.file = os.path.join(self.folder_path, file)
                self.studant_dict = {}
                self.open_file()
                self.get_data()
                self.manipulate_data()
