import uuid
from methods.generate_uuid import generate_uuid

class Students:
    def __init__(self, dataframe, class_columns, student_year):
        self.dataframe = dataframe
        self.class_columns = class_columns
        self.student_year = student_year

    def create_schema(self):
        """ Get students data from the DataFrame. """
        df = self.dataframe
        students = list()
        shifts_dict = dict()
        student_class = self.class_columns[0]

        for student in map(str, df.index):  # Converte o índice para string
            if student_class in df.columns:
                value = df.loc[student, student_class]
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    grade_level, shift = value
                else:
                    grade_level, shift = value, None  # Caso não seja iterável, atribua `None` ao turno

                # Todo: Change this Later
                if student_class == "6° Ano de Escolaridade - 601" or student_class == "6° Ano de Escolaridade - 602":
                    shift = "Manhã"

                shift = shift.replace("Turno:", "").strip() if shift else None
                shifts_dict.update({student: shift})

                unique_identifier = f"{student}{student_class}{self.student_year}"

                students.append({
                    "aluno_id": generate_uuid(unique_identifier),  # Gera um ID único
                    "aluno": student.replace("Aluno(a):", "").strip(),
                    "matricula": "NOT IMPLEMENTED",
                    "resonsavel_id": "NOT IMPLEMENTED",
                    "data_nascimento": "NOT IMPLEMENTED",
                    "endereco": "NOT IMPLEMENTED",
                    "sexo": "NOT IMPLEMENTED",
                    "status": "Inativo"
                })

        return students, shifts_dict