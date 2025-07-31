import uuid
import unicodedata

class Disciplina:
    def __init__(self, dataframe, disciplines_columns, disciplines_id):
        self.dataframe = dataframe
        self.disciplines_columns = disciplines_columns
        self.disciplines_id = disciplines_id


    def create_schema(self):
        """"Get disciplines data from the DataFrame.
                :param df: DataFrame with disciplines data
                :param disciplines_id: Dictionary with disciplines IDs
                :return: List of dictionaries with disciplines data
                """
        disciplines = list()
        df = self.dataframe
        for d in self.disciplines_columns:
            if d in df.columns:
                if d == "Língua Portuguesa":
                    d_name = "PORTUGUÊS"
                elif d == "HIST. e GEOGR.":
                    d_name = "HISTÓRIA_E_GEOGRAFIA"
                elif d == "Cidadania/Ética":
                    d_name = "CIDADANIA_ETICA"
                else:
                    d_name = d.upper()

                disciplines.append(
                    {"disciplina_id": self.disciplines_id[d], "disciplina": self.__remove_accentuation(d_name),
                "fk_disciplina": self.disciplines_id[d]})

        return disciplines


    def __remove_accentuation(self, string):
        """"Remove accentuation from a string."""
        normalize_string = unicodedata.normalize('NFKD', string)
        return ''.join([c for c in normalize_string if not unicodedata.combining(c)])