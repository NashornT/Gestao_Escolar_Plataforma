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
        #for student in df.index:
            #if "PROFESSOR" in df.columns:
            # professors.append({
            #     "professor_id": "NOT IMPLEMENTED",
            #     "nome": "NOT IMPLEMENTED",
            #     "email": "NOT IMPLEMENTED",
            #     "telefone": "NOT IMPLEMENTED",
            #     "endereco_id": "NOT IMPLEMENTED",
            #     "fk_professor": str(uuid.uuid4()),  # Generate a unique identifier for the professor
            # })

        professor_id = str(uuid.uuid4())
        professors.append({
            "professor_id": professor_id,
            "nome": "NOT IMPLEMENTED",
            "email": "NOT IMPLEMENTED",
            "telefone": "NOT IMPLEMENTED",
            "endereco_id": "NOT IMPLEMENTED",
            "fk_professor": professor_id,  # Generate a unique identifier for the professor
        })

        return professors