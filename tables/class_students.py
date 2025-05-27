import uuid

class ClassStudents:
    def __init__(self, dataframe, student_year, class_columns, shift):
        self.dataframe = dataframe
        self.student_year = student_year
        self.class_columns = class_columns
        self.shift = shift

    def create_schema(self):
        """Get classes data from the DataFrame.
        :param df: DataFrame with classes data
        :return: List of dictionaries with classes data
        """
        classes = list()
        df = self.dataframe
        student_class = self.class_columns[0]
        student_class_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(student_class) + str(self.shift) + str(self.student_year)))
        for student in df.index:
            classes.append({
                "turma": student_class,
                "turma_id": student_class_id,
                "ano_escolar": self.student_year,
                "turno": self.shift,
            })

        return classes