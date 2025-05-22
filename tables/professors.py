import uuid

class Professors:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def create_schema(self):
        """Get professors data from the DataFrame.
        :param df: DataFrame with professors data
        :return: List of dictionaries with professors data
        """
        professors = list()
        df = self.dataframe
        for student in df.index:
            #if "PROFESSOR" in df.columns:
            professors.append({
                "professor_id": "NOT IMPLEMENTED",
                "nome": "NOT IMPLEMENTED",
                "email": "NOT IMPLEMENTED",
                "telefone": "NOT IMPLEMENTED",
                "endereco_id": "NOT IMPLEMENTED",
            })

        return professors