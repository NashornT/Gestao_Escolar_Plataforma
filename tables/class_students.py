from methods.generate_uuid import generate_uuid

class ClassStudents:
    def __init__(self, dataframe, student_year, class_columns, shifts_dict):
        self.dataframe = dataframe
        self.student_year = student_year
        self.class_columns = class_columns
        self.shifts_dict = shifts_dict

    def create_schema(self):
        """Get classes data from the DataFrame.
        :param df: DataFrame with classes data
        :return: List of dictionaries with classes data
        """
        classes = list()
        df = self.dataframe
        student_class = self.class_columns[0]
        prev_element = None
        for student in df.index:
            shift = self.shifts_dict.get(student, None)
            student_class_id = generate_uuid(str(student_class) + str(shift) + str(self.student_year))
            if prev_element == student_class_id:
                continue
            classes.append({
                "turma": student_class,
                "turma_id": student_class_id,
                "ano_escolar": self.student_year,
                "turno": shift,
                "fk_turma": student_class_id,  # Generate a unique identifier for the class
            })
            prev_element = student_class_id

        return classes