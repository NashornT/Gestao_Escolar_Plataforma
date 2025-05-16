import xlrd
import pandas as pd
import os
from storage.mysql import send_to_mysql
import unicodedata


class ExtractData:

    def __init__(self, folder_path):
        self.__folder_path = folder_path
        self.__file = None
        self.__workbook = None
        self.__sheet = None
        self.__student_year = None
        self.__student_dict = dict()
        self.__disciplines_columns = ['Língua Portuguesa', 'Artes', 'Ciências', 'Matemática', 'Geografia', 'História',
                                    'Cidadania/Ética', 'Inglês','MATEMÁTICA','HIST. e GEOGR.','CIÊNCIAS','PORTUGUÊS']

    def __open_file(self):
        """Open the .xls file."""
        self.__workbook = xlrd.open_workbook(self.__file)
        self.__sheet = self.__workbook.sheet_by_index(0)


    def __get_data(self):
        """Extract data from the .xls file."""
        self.__open_file()

        studant_key = str
        for row_idx in range(self.__sheet.nrows):
            studant_data = list()
            for data in self.__sheet.row_values(row_idx):
                year = None

                if "Aluno" in str(data):
                    studant_key = data
                    self.__student_dict.update({studant_key: {}})
                elif "Ano Letivo:" in str(data):
                    self.__student_year = data.replace("Ano Letivo:", "").strip()
                elif data != "":
                    studant_data.append(data)


                if '20' in str(data) and 4 <= len(str(data).replace('.0','')) <= 6:
                    year = str(data).replace('.0','')
                    self.__student_year = year

            if len(studant_data) > 1:
                key = studant_data[1]

                key, studant_key = self.__adjustment_keys(key,studant_key, studant_data)

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
        elif key not in self.__disciplines_columns:
            key = studant_data[0]

        if key == 'BASE NACIONAL COMUM':
            key = studant_data[2]
            studant_data.remove(studant_data[0])
            studant_data.remove(studant_data[1])

        if key in self.__disciplines_columns:
            for data in studant_data:
                if type(data) == str:
                    studant_data.remove(data)

        if key in studant_data:
            studant_data.remove(key)

        return key, studant_key


    def __remove_accentuation(self, string):
        """"Remove accentuation from a string."""
        normalize_string = unicodedata.normalize('NFKD', string)
        return ''.join([c for c in normalize_string if not unicodedata.combining(c)])

    def __get_students(self, df, shift_columns):
        """ Get students data from the DataFrame.
        :param df: DataFrame with student data
        :param shift_columns: List of columns with shift information
        :return: List of dictionaries with student data
        """

        students = list()
        for student in df.index:
            for col in shift_columns:
                if col in df.columns:
                    value = df.loc[student, col]
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        grade_level, shift = value
                    else:
                        grade_level, shift = value, None  # Caso não seja iterável, atribua `None` ao turno

                    # Todo: Change this Later
                    if col == "6° Ano de Escolaridade - 601" or col == "6° Ano de Escolaridade - 602":
                        shift = "Manhã"

                    tot_absences = df['FALTAS'][student][-1] if isinstance(df['FALTAS'][student], list) else 0.0

                    students.append({
                        "aluno_id": str(hash(student)),  # Gerar um ID único
                        "aluno": student.replace("Aluno(a):", "").strip(),
                        "nivel_escolar": col,
                        "ano_escolar": self.__student_year,
                        "turno": shift.replace("Turno:", "").strip() if shift else None,
                        "total_faltas": tot_absences
                    })

        return students

    def __get_disciplines(self, df, disciplines_id):
        """"Get disciplines data from the DataFrame.
        :param df: DataFrame with disciplines data
        :param disciplines_id: Dictionary with disciplines IDs
        :return: List of dictionaries with disciplines data
        """
        disciplines = list()
        for d in self.__disciplines_columns:
            if d in df.columns:
                if d == "Língua Portuguesa":
                    d_name = "PORTUGUÊS"
                elif d == "HIST. e GEOGR.":
                    d_name = "HISTÓRIA_E_GEOGRAFIA"
                elif d == "Cidadania/Ética":
                    d_name = "CIDADANIA_ETICA"
                else:
                    d_name = d.upper()

                disciplines.append({"disciplina_id": disciplines_id[d], "disciplina": self.__remove_accentuation(d_name)})

        return disciplines

    def __get_grades(self, df, disciplines_id):
        """"Get grades data from the DataFrame.
        :param df: DataFrame with grades data
        :param disciplines_id: Dictionary with disciplines IDs
        :return: List of dictionaries with grades data
        """
        grades = list()
        for student in df.index:
            student_id = str(hash(student))
            for discipline in self.__disciplines_columns:
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
                        "primeiro_bimestre_nota": first_grade,
                        "primeiro_bimestre_nota_recuperacao": first_grade_rc,
                        "segundo_bimestre_nota": second_grade,
                        "segundo_bimestre_nota_recuperacao": second_grade_rc,
                        "terceiro_bimestre_nota": third_grade,
                        "terceiro_bimestre_nota_recuperacao": third_grade_rc,
                        "quarto_bimestre_nota": fourth_grade,
                        "quarto_bimestre_nota_recuperacao": fourth_grade_rc,
                        "total_notas": sum_grades,
                        "media_notas": average_grades,
                    })

        return grades

    def __normalize_data(self, df):
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
        students = self.__get_students(df, shift_columns)

        # Tabela de disciplinas
        disciplines = self.__get_disciplines(df, disciplines_id)

        # Tabela de notas
        grades = self.__get_grades(df, disciplines_id)


        return pd.DataFrame(students), pd.DataFrame(disciplines), pd.DataFrame(grades)


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

        students, disciplines, grades = self.__normalize_data(df)
        send_to_mysql(df_students=students,df_disciplines=disciplines,df_grades=grades)


    def run(self):
        """Run the extraction and manipulation process."""
        
        for file in os.listdir(self.__folder_path):
            if file.endswith('.xls'):
                self.__file = os.path.join(self.__folder_path, file)
                self.__student_dict = {}
                self.__manipulate_data()
