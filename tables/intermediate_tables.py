import uuid

class IntermediateTables:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def create_schema(self):
        studants_classes = list()
        disciplines_classes = list()
        professors_disciplines = list()

        df = self.dataframe
        for student in df.index:
            student_id = str(hash(student))
            # for discipline in self.disciplines_columns:
            #     if discipline in df.columns:
            #         discipline_id = self.disciplines_columns.index(discipline) + 1
            #         pass

            studants_classes.append({
                "aluno_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, str(student))),
                "turma_id": "NOT IMPLEMENTED",
            })

            disciplines_classes.append({
                "disciplina_id": "NOT IMPLEMENTED",
                "turma_id": "NOT IMPLEMENTED",

            })

            professors_disciplines.append({
                "professor_id": "NOT IMPLEMENTED",
                "disciplina_id": "NOT IMPLEMENTED",
            })

        return studants_classes, disciplines_classes, professors_disciplines


