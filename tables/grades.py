import uuid
from methods.generate_uuid import generate_uuid

class Grades:
    def __init__(self, dataframe, disciplines_id, student_year, disciplines_columns, file_type):
        self.dataframe = dataframe
        self.disciplines_id = disciplines_id
        self.student_year = student_year
        self.disciplines_columns = disciplines_columns
        self.file_type = file_type


    def __normalize_grades(self, grades_list):
        """Normaliza as notas, removendo valores inválidos e garantindo consistência."""
        normalized_grades = []
        for grade in grades_list:
            try:
                # Converte para float e ignora valores não numéricos
                normalized_grades.append(float(grade))
            except ValueError:
                pass
                #normalized_grades.append(0.0)  # Substitui valores inválidos por 0.0
        return normalized_grades

    def create_schema(self):
        """"Get grades data from the DataFrame.
        :param df: DataFrame with grades data
        :param disciplines_id: Dictionary with disciplines IDs
        :return: List of dictionaries with grades data
        """
        grades = list()
        df = self.dataframe
        for student in df.index:
            for discipline in self.disciplines_columns:
                if discipline in df.columns:
                    len_grades = len(df.loc[student, discipline])
                    grades_list = df.loc[student, discipline]

                    # Normaliza as notas
                    grades_list = self.__normalize_grades(grades_list)

                    skip_grade = False
                    grades_dict = {"notas":[], "notas_rec": [], "notas_final": []}
                    skip_index = 0
                    for index, grade in enumerate(grades_list):
                        if grade <= 10.0:
                            if skip_grade is True:
                                if skip_index == 0:
                                    skip_grade = False
                                else:
                                    skip_index -= 1
                                continue
                            elif self.file_type == 'xls' and (index == len_grades - 2 or index == len_grades - 1):
                                # Últimos elementos são a soma e a média, não são notas
                                continue

                            if grade < 6:
                                grade_rec = grades_list[index + 1] if index + 1 < len_grades else 0.0

                                if grade > grade_rec:
                                    final_grade = grade
                                else:
                                    final_grade = grade_rec

                                grades_dict.get("notas").append(grade)
                                grades_dict.get("notas_rec").append(grade_rec)
                                grades_dict.get("notas_final").append(final_grade)

                                skip_grade = True
                                if self.file_type == 'xls' and grade_rec != 0.0:
                                    skip_index = 1

                            else:
                                grades_dict.get("notas").append(grade)
                                grades_dict.get("notas_rec").append(0.0)
                                grades_dict.get("notas_final").append(grade)
                                if self.file_type == 'xls':
                                    skip_grade = True

                    sum_grades = sum(grades_dict.get("notas_final"))
                    average_grades = sum_grades / 4 if sum_grades else 0.0

                    grades.append({
                            "nota_id": str(uuid.uuid4()),
                            "aluno_id": generate_uuid(str(student)),
                            "ano_letivo": self.student_year,
                            "disciplina_id": self.disciplines_id[discipline],
                            "nota_1_bimestre": grades_dict.get("notas")[0] if len(grades_dict.get("notas")) > 0 else 0.0,
                            "nota_1_bimestre_recuperacao": grades_dict.get("notas_rec")[0] if len(grades_dict.get("notas_rec")) > 0 else 0.0,
                            "nota_1_bimestre_final": grades_dict.get("notas_final")[0] if len(grades_dict.get("notas_final")) > 0 else 0.0,
                            "nota_2_bimestre": grades_dict.get("notas")[1] if len(grades_dict.get("notas")) > 1 else 0.0,
                            "nota_2_bimestre_recuperacao": grades_dict.get("notas_rec")[1] if len(grades_dict.get("notas_rec")) > 1 else 0.0,
                            "nota_2_bimestre_final": grades_dict.get("notas_final")[1] if len(grades_dict.get("notas_final")) > 1 else 0.0,
                            "nota_3_bimestre": grades_dict.get("notas")[2] if len(grades_dict.get("notas")) > 2 else 0.0,
                            "nota_3_bimestre_recuperacao": grades_dict.get("notas_rec")[2] if len(grades_dict.get("notas_rec")) > 2 else 0.0,
                            "nota_3_bimestre_final": grades_dict.get("notas_final")[2] if len(grades_dict.get("notas_final")) > 2 else 0.0,
                            "nota_4_bimestre": grades_dict.get("notas")[3] if len(grades_dict.get("notas")) > 3 else 0.0,
                            "nota_4_bimestre_recuperacao": grades_dict.get("notas_rec")[3] if len(grades_dict.get("notas_rec")) > 3 else 0.0,
                            "nota_4_bimestre_final": grades_dict.get("notas_final")[3] if len(grades_dict.get("notas_final")) > 3 else 0.0,
                            "nota_total": sum_grades,
                            "media_final": average_grades,
                        })

        return grades