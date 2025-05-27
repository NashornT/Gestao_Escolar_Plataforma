import uuid

class Grades:
    def __init__(self, dataframe, disciplines_id, student_year, disciplines_columns):
        self.dataframe = dataframe
        self.disciplines_id = disciplines_id
        self.student_year = student_year
        self.disciplines_columns = disciplines_columns

    def create_schema(self):
        """"Get grades data from the DataFrame.
        :param df: DataFrame with grades data
        :param disciplines_id: Dictionary with disciplines IDs
        :return: List of dictionaries with grades data
        """
        grades = list()
        df = self.dataframe
        for student in df.index:
            student_id = str(hash(student))
            for discipline in self.disciplines_columns:
                if discipline in df.columns:
                    len_grades = len(df.loc[student, discipline])
                    grades_list = df.loc[student, discipline]

                    # Inicializa as variáveis para as notas
                    first_grade = first_grade_rc = second_grade = second_grade_rc = None
                    third_grade = third_grade_rc = fourth_grade = fourth_grade_rc = None
                    sum_grades = average_grades = None

                    # Lógica para processar as notas
                    if "=SUM" in str(grades_list[-1]):
                        grades_list.pop()
                    elif "=" in str(grades_list[-1]):
                        clean_grades = list()
                        for grade in grades_list:
                            if '=' not in str(grade):
                                clean_grades.append(grade)
                            else:
                                clean_grades.append(0.0)
                        grades_list.clear()
                        grades_list = clean_grades
                    else:
                        pass


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
                        "nota_id":"NOT IMPLEMENTED",
                        "aluno_id": student_id,
                        "ano_letivo": self.student_year,
                        "disciplina_id": self.disciplines_id[discipline],
                        "nota_1_bimestre": first_grade,
                        "nota_1_bimestre_recuperacao": first_grade_rc,
                        "nota_2_bimestre": second_grade,
                        "nota_2_bimestre_recuperacao": second_grade_rc,
                        "nota_3_bimestre": third_grade,
                        "nota_3_bimestre_recuperacao": third_grade_rc,
                        "nota_4_bimestre": fourth_grade,
                        "nota_4_bimestre_recuperacao": fourth_grade_rc,
                        "nota_total": sum_grades,
                        "media_final": average_grades,
                    })

        return grades
