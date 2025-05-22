import uuid

class Address:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def create_schema(self):
        """Get address data from the DataFrame.
        :param df: DataFrame with address data
        :return: List of dictionaries with address data
        """
        address = list()
        df = self.dataframe
        for student in df.index:
            #if "ENDEREÇO" in df.columns:
            address.append({
                "aluno_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, str(student))),
                "logradouro": "NOT IMPLEMENTED",
                "numero": "NOT IMPLEMENTED",
                "complemento": "NOT IMPLEMENTED",
                "bairro": "NOT IMPLEMENTED",
                "cidade": "NOT IMPLEMENTED",
                "cep": "NOT IMPLEMENTED",
                "endereco_id": "NOT IMPLEMENTED"
            })

        return address