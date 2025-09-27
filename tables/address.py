from methods.generate_uuid import generate_uuid

class Address:
    def __init__(self, dataframe, student_year, class_columns,aluno_id_map):
        self.dataframe = dataframe
        self.student_year = student_year
        self.class_columns = class_columns
        self.aluno_id_map = aluno_id_map

    def create_schema(self):
        """Get address data from the DataFrame.
        :param df: DataFrame with address data
        :return: List of dictionaries with address data
        """
        address = list()
        df = self.dataframe
        student_class = df.columns[0]
        for student in df.index:
            #if "ENDEREÇO" in df.columns:
            aluno_id = self.aluno_id_map.get(student.replace("Aluno(a):", "").strip())
            address.append({
                "aluno_id": aluno_id,
                "logradouro": "NOT IMPLEMENTED",
                "numero": "NOT IMPLEMENTED",
                "complemento": "NOT IMPLEMENTED",
                "bairro": "NOT IMPLEMENTED",
                "cidade": "NOT IMPLEMENTED",
                "cep": "NOT IMPLEMENTED",
                "endereco_id": "NOT IMPLEMENTED"
            })

        return address