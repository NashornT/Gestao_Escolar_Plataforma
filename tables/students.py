import uuid
from methods.generate_uuid import generate_uuid

class Students:
    def __init__(self, dataframe, class_columns, student_year):
        self.dataframe = dataframe
        self.class_columns = class_columns
        self.student_year = student_year

    def create_schema(self):
        """ Get students data from the DataFrame.
        :param df: DataFrame with student data
        :param class_columns: List of columns with shift information
        :return: List of dictionaries with student data
        """
        df = self.dataframe
        students = list()
        shift = None
        shifts_dict = dict()
        for student in df.index:
            for col in self.class_columns:
                if col in df.columns:
                    value = df.loc[student, col]
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        grade_level, shift = value
                    else:
                        grade_level, shift = value, None  # Caso não seja iterável, atribua `None` ao turno

                    # Todo: Change this Later
                    if col == "6° Ano de Escolaridade - 601" or col == "6° Ano de Escolaridade - 602":
                        shift = "Manhã"

                    if isinstance(df['FALTAS'][student], list):
                        if "=SUM" in str(df['FALTAS'][student][-1]):
                            df['FALTAS'][student].pop()
                            absences_list = df['FALTAS'][student]
                            if absences_list:
                                tot_absences = sum(absences_list)
                            else:
                                tot_absences = 0.0
                        else:
                            tot_absences = df['FALTAS'][student][-1] if isinstance(df['FALTAS'][student], list) else 0.0
                    else:
                        tot_absences = 0.0

                    shift = shift.replace("Turno:", "").strip() if shift else None
                    shifts_dict.update({student: shift})

                    students.append({
                        "aluno_id": generate_uuid(str(student)),  # Gerar um ID único
                        "aluno": student.replace("Aluno(a):", "").strip(),
                        "turma_id": generate_uuid(str(col) + str(shift) + str(self.student_year)),
                        "total_faltas": tot_absences,
                        "matricula": "NOT IMPLEMENTED",
                        "resonsavel_id": "NOT IMPLEMENTED",
                        "data_nascimento": "NOT IMPLEMENTED",
                        "endereco": "NOT IMPLEMENTED",
                        "sexo": "NOT IMPLEMENTED",
                        "status": "Ativo"
                    })

        return students, shifts_dict