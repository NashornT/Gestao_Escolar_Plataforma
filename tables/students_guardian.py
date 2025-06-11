from methods.generate_uuid import generate_uuid

class StudentsGuardian:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def create_schema(self):
        """Get responsible data from the DataFrame.
                :param df: DataFrame with responsible data
                :return: List of dictionaries with responsible data
                """
        students_guardian = list()
        df = self.dataframe
        for student in df.index:
            # if "RESPONSÁVEL" in df.columns:
            student_str = str(student) if student is not None else ""
            students_guardian.append({
                "aluno_id": generate_uuid(student_str),
                "nome": "NOT IMPLEMENTED",
                "telefone": "NOT IMPLEMENTED",
                "endereco_id": "NOT IMPLEMENTED",
                "cpf": "NOT IMPLEMENTED",
                "email": "NOT IMPLEMENTED",
                "parentesco": "NOT IMPLEMENTED",
            })

        return students_guardian
