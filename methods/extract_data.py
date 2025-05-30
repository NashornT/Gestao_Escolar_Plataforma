import xlrd
import pandas as pd
import os
import openpyxl
from storage.mysql import send_to_mysql


class ExtractData:

    def __init__(self, folder_path):
        self.__folder_path = folder_path
        self.__file = None
        self.__workbook = None
        self.__sheet = None
        self.student_year = None
        self.file_type = None
        self.__student_dict = dict()
        self.disciplines_columns = ['Língua Portuguesa', 'Artes', 'Ciências', 'Matemática', 'Geografia', 'História',
                                    'Cidadania/Ética', 'Inglês','MATEMÁTICA','HIST. e GEOGR.','CIÊNCIAS','PORTUGUÊS']

    def __open_file(self):
        """Open the .xls file."""
        if self.__file.endswith('.xls'):
            self.__workbook = xlrd.open_workbook(self.__file)
            self.__sheet = self.__workbook.sheet_by_index(0)
            self.file_type = 'xls'
        elif self.__file.endswith('.xlsx'):
            self.__workbook = openpyxl.load_workbook(self.__file)
            self.__sheet = self.__workbook.active
            self.file_type = 'xlsx'

    def __get_data(self):
        """Extrai os dados do arquivo .xls ou .xlsx."""
        self.__open_file()

        studant_key = str
        if isinstance(self.__sheet, xlrd.sheet.Sheet):  # Caso seja um arquivo .xls
            for row_idx in range(self.__sheet.nrows):
                studant_data = list()
                for data in self.__sheet.row_values(row_idx):
                    if "Aluno" in str(data):
                        studant_key = data
                        self.__student_dict.update({studant_key: {}})
                    elif "Ano Letivo:" in str(data):
                        self.student_year = data.replace("Ano Letivo:", "").strip()
                    elif data != "":
                        studant_data.append(data)

                    if '20' in str(data) and 4 <= len(str(data).replace('.0', '')) <= 6:
                        year = str(data).replace('.0', '')
                        self.student_year = year

                if len(studant_data) > 1:
                    key = studant_data[1]
                    key, studant_key = self.__adjustment_keys(key, studant_key, studant_data)
                    if key != studant_key:
                        self.__student_dict.get(studant_key).update({key: studant_data})
        else:  # Caso seja um arquivo .xlsx
            for row in self.__sheet.iter_rows(values_only=True):
                studant_data = list()
                for data in row:
                    if data:
                        if "Aluno" in str(data):
                            studant_key = data
                            self.__student_dict.update({studant_key: {}})
                        elif "Ano Letivo:" in str(data):
                            self.student_year = data.replace("Ano Letivo:", "").strip()
                        elif data != "":
                            studant_data.append(data)

                        if '20' in str(data) and 4 <= len(str(data).replace('.0', '')) <= 6:
                            year = str(data).replace('.0', '')
                            self.student_year = year

                if len(studant_data) > 1:
                    key = studant_data[1]
                    key, studant_key = self.__adjustment_keys(key, studant_key, studant_data)
                    if key != studant_key:
                        self.__student_dict.get(studant_key).update({key: studant_data})

    def __adjustment_keys(self, key ,studant_key, studant_data):
        """Adjust the keys for the dictionary."""

        if studant_key == 'Aluno(a):':
            del self.__student_dict[studant_key]
            studant_key = studant_data[0]
            self.__student_dict.update({studant_key: {}})

        if key == "CÓDIGOS E":
            key = studant_data[2]
            studant_data.remove("CÓDIGOS E")
        elif key not in self.disciplines_columns:
            key = studant_data[0]

        if key == 'BASE NACIONAL COMUM':
            key = studant_data[2]
            studant_data.remove(studant_data[0])
            studant_data.remove(studant_data[1])

        if key in self.disciplines_columns:
            for data in studant_data:
                if type(data) == str:
                    studant_data.remove(data)

        if key in studant_data:
            studant_data.remove(key)

        return key, studant_key


    def __get_tables(self, df):
        """Normaliza os dados do DataFrame para um formato relacional."""

        # Garantir que os nomes das colunas estejam corretos
        df.columns = [col.strip() for col in df.columns]  # Remove espaços extras

        # Identificar colunas de escolaridade dinamicamente
        class_columns = [col for col in df.columns if
                                "Ano de Escolaridade" in col or "PRÉ" in col or 'Pré' in col]

        disciplines_id = {
            "Língua Portuguesa": 1,
            "Artes": 2,
            "Ciências": 3,
            "Matemática": 4,
            "Geografia": 5,
            "História": 6,
            "Cidadania/Ética": 7,
            "Inglês": 8,
            "MATEMÁTICA": 4,
            "HIST. e GEOGR.": 9,
            "CIÊNCIAS": 3,
            "PORTUGUÊS": 1
        }

        if not class_columns:
            raise KeyError("Nenhuma coluna de escolaridade encontrada no DataFrame.")

        # Tabela de alunos
        from tables.students import Students
        students, shift = Students(df, class_columns, self.student_year).create_schema()

        # Tabela de disciplinas
        from tables.disciplinas import Disciplina
        disciplines = Disciplina(df,self.disciplines_columns, disciplines_id).create_schema()

        # Tabela de notas
        from tables.grades import Grades
        grades = Grades(df, disciplines_id, self.student_year, self.disciplines_columns,
                        self.file_type).create_schema()

        # Tabela de endereços
        from tables.address import Address
        address = Address(df).create_schema()

        # Tabela de professores
        from tables.professors import Professors
        professors = Professors(df).create_schema()

        # Tabela de responsáveis
        from tables.students_guardian import StudentsGuardian
        students_guardian = StudentsGuardian(df).create_schema()

        # Tabela de turmas
        from tables.class_students import ClassStudents
        classes = ClassStudents(df, self.student_year, class_columns, shift).create_schema()

        # Tabelas intermediárias
        from tables.intermediate_tables import IntermediateTables
        (studants_classes,
         disciplines_classes,
         professors_disciplines) = IntermediateTables(df, self.disciplines_columns,
                                                      disciplines_id,
                                                      class_columns, self.student_year, shift).create_schema()


        return (pd.DataFrame(students), pd.DataFrame(disciplines), pd.DataFrame(grades), pd.DataFrame(address),
                pd.DataFrame(professors), pd.DataFrame(students_guardian), pd.DataFrame(classes),
                pd.DataFrame(studants_classes), pd.DataFrame(disciplines_classes), pd.DataFrame(professors_disciplines))


    def __manipulate_data(self):
        """Manipulate the extracted data."""
        self.__get_data()

        # Convert the dictionary to a DataFrame
        df = pd.DataFrame.from_dict(self.__student_dict, orient='index')

        # Remove unwanted columns
        colunas_para_remover = ['ÁREAS DE', 'RB', 'LEGENDA', 'CONHECIMENTO','N','Disciplinas']

        for column in colunas_para_remover:
            if column in df.columns:
                df = df.drop(columns=column)

        (students, disciplines, grades, adress, professors, students_guardian, classes, students_classes,
         disciplines_classes, professors_disciplines) = self.__get_tables(df)

        send_to_mysql(df_students=students,df_disciplines=disciplines,df_grades=grades
                      ,df_address=adress,df_professors=professors,df_students_guardian=students_guardian,
                      df_classes=classes,df_students_classes=students_classes,df_disciplines_classes=disciplines_classes,
                      df_professors_disciplines=professors_disciplines)


    def run(self):
        """Run the extraction and manipulation process."""
        
        for file in os.listdir(self.__folder_path):
            if file.endswith('.xls') or file.endswith('xlsx'):
                self.__file = os.path.join(self.__folder_path, file)
                self.__student_dict = {}
                self.__manipulate_data()
