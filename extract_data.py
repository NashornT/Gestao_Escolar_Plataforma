import xlrd
import pandas as pd
import os
from storage.mysql import send_to_mysql


class ExtractData:

    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.file = None
        self.workbook = None
        self.sheet = None
        self.studant_dict = dict()
        self.disciplines_columns = ['Língua Portuguesa', 'Artes', 'Ciências', 'Matemática', 'Geografia', 'História',
                                    'Cidadania/Ética', 'Inglês','MATEMÁTICA','HIST. e GEOGR.','CIÊNCIAS','PORTUGUÊS']

    def open_file(self):
        """Open the .xls file."""
        self.workbook = xlrd.open_workbook(self.file)
        self.sheet = self.workbook.sheet_by_index(0)


    def get_data(self):
        """Extract data from the .xls file."""
        self.open_file()

        studant_key = str
        for row_idx in range(self.sheet.nrows):
            studant_data = list()
            for data in self.sheet.row_values(row_idx):
                if "Aluno" in str(data):
                    studant_key = data
                    self.studant_dict.update({studant_key: {}})
                elif data != "":
                    studant_data.append(data)

            if len(studant_data) > 1:
                key = studant_data[1]

                key, studant_key = self.adjustment_keys(key,studant_key, studant_data)

                if key != studant_key:
                    self.studant_dict.get(studant_key).update({key: studant_data})

    def adjustment_keys(self, key ,studant_key, studant_data):
        """Adjust the keys for the dictionary."""

        if studant_key == 'Aluno(a):':
            del self.studant_dict[studant_key]
            studant_key = studant_data[0]
            self.studant_dict.update({studant_key: {}})

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


    def normalize_data(self, df):
                """Normaliza os dados do DataFrame para um formato relacional."""

                # Garantir que os nomes das colunas estejam corretos
                df.columns = [col.strip() for col in df.columns]  # Remove espaços extras

                # Identificar colunas de escolaridade dinamicamente
                shift_columns = [col for col in df.columns if
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

                if not shift_columns:
                    raise KeyError("Nenhuma coluna de escolaridade encontrada no DataFrame.")

                # Tabela de alunos
                students = []
                for student in df.index:
                    for col in shift_columns:
                        if col in df.columns:
                            value = df.loc[student, col]
                            if isinstance(value, (list, tuple)) and len(value) == 2:
                                grade_level, shift = value
                            else:
                                grade_level, shift = value, None  # Caso não seja iterável, atribua `None` ao turno
                            students.append({
                                "aluno_id": hash(student),  # Gerar um ID único
                                "nome": student.replace("Aluno(a):", "").strip(),
                                "nivel_escolar": col,
                                "turno": shift.replace("Turno:", "").strip() if shift else None
                            })



                # Tabela de disciplinas
                disciplines = list()
                for d in self.disciplines_columns:
                    if d in df.columns:
                        disciplines.append({"disciplina_id": disciplines_id[d], "nome": d})

                # Tabela de notas
                grades = []
                for student in df.index:
                    student_id = hash(student)
                    for discipline in self.disciplines_columns:
                        if discipline in df.columns:
                            len_grades = len(df.loc[student, discipline])
                            grades_list = df.loc[student, discipline]

                            # Inicializa as variáveis para as notas
                            first_grade = first_grade_rc = second_grade = second_grade_rc = None
                            third_grade = third_grade_rc = fourth_grade = fourth_grade_rc = None
                            sum_grades = average_grades = None

                            # Lógica para processar as notas
                            for index, grade in enumerate(grades_list):
                                if index == len_grades - 2:  # Penúltimo elemento é a soma das notas
                                    sum_grades = grade
                                elif index == len_grades - 1:  # Último elemento é a média das notas
                                    average_grades = grade
                                else:
                                    # Verifica se a próxima nota é menor e diferente
                                    if index + 1 < len_grades and isinstance(grade, (int, float)):
                                        next_grade = grades_list[index + 1]
                                        if isinstance(next_grade, (int, float)) and next_grade < grade:
                                            grade = max(grade, next_grade)

                                    # Atribui as notas às variáveis correspondentes
                                    if index == 0:
                                        first_grade = grade
                                    elif index == 1:
                                        first_grade_rc = grade
                                    elif index == 2:
                                        second_grade = grade
                                    elif index == 3:
                                        second_grade_rc = grade
                                    elif index == 4:
                                        third_grade = grade
                                    elif index == 5:
                                        third_grade_rc = grade
                                    elif index == 6:
                                        fourth_grade = grade
                                    elif index == 7:
                                        fourth_grade_rc = grade

                            # Adiciona os dados processados à lista de notas
                            grades.append({
                                "aluno_id": student_id,
                                "disciplina_id": disciplines_id[discipline],
                                "1_bim_nota": first_grade,
                                "1_bim_nota_rc": first_grade_rc,
                                "2_bim_nota": second_grade,
                                "2_bim_nota_rc": second_grade_rc,
                                "3_bim_nota": third_grade,
                                "3_bim_nota_rc": third_grade_rc,
                                "4_bim_nota": fourth_grade,
                                "4_bim_nota_rc": fourth_grade_rc,
                                "total_notas": sum_grades,
                                "media_notas": average_grades,
                            })

                return pd.DataFrame(students), pd.DataFrame(disciplines), pd.DataFrame(grades)


    def manipulate_data(self):
        """Manipulate the extracted data."""
        self.get_data()

        # Convert the dictionary to a DataFrame
        df = pd.DataFrame.from_dict(self.studant_dict, orient='index')

        # Remove unwanted columns
        colunas_para_remover = ['ÁREAS DE', 'RB', 'LEGENDA', 'CONHECIMENTO','N','Disciplinas']

        for column in colunas_para_remover:
            if column in df.columns:
                df = df.drop(columns=column)

        output_folder = self.folder_path + "/outputs"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        students, disciplines, grades = self.normalize_data(df)

        send_to_mysql(df_students=students,df_disciplines=disciplines,df_grades=grades)

        # json_file = self.file.replace(".xls", ".json")
        # json_file = os.path.join(output_folder, os.path.basename(json_file))

        # print(f"Arquivo JSON criado em: {json_file}")


    def run(self):
        """Run the extraction and manipulation process."""
        
        for file in os.listdir(self.folder_path):
            if file.endswith('.xls'):
                self.file = os.path.join(self.folder_path, file)
                self.studant_dict = {}
                self.manipulate_data()
