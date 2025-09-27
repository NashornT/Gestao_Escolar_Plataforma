from methods.generate_uuid import generate_uuid

class StudentsGuardian:
    def __init__(self, dataframe, aluno_id_map):
        self.dataframe = dataframe
        self.aluno_id_map = aluno_id_map

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
            aluno_id = self.aluno_id_map.get(student.replace("Aluno(a):", "").strip())
            students_guardian.append({
                "aluno_id": aluno_id,
                "nome": "NOT IMPLEMENTED",
                "telefone": "NOT IMPLEMENTED",
                "endereco_id": "NOT IMPLEMENTED",
                "cpf": "NOT IMPLEMENTED",
                "email": "NOT IMPLEMENTED",
                "parentesco": "NOT IMPLEMENTED",
            })

        return students_guardian
