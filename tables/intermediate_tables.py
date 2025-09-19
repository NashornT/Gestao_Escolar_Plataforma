import uuid

from pandas.core.array_algos.transforms import shift

from methods.generate_uuid import generate_uuid


class IntermediateTables:
    def __init__(self, dataframe, disciplines_columns, discipline_id, class_columns, student_year, shifts_dict, aluno_id_map):
        self.dataframe = dataframe
        self.disciplines_columns = disciplines_columns
        self.discipline_id = discipline_id
        self.class_columns = class_columns
        self.student_year = student_year
        self.shifts_dict = shifts_dict
        self.aluno_id_map = aluno_id_map

    def create_schema(self):
        studants_classes = list()
        disciplines_classes = list()
        professors_disciplines = list()
        duplicate_disciplines = set()

        df = self.dataframe
        student_class = self.class_columns[0]

        primeiro_aluno = df.index[0]
        shift = self.shifts_dict.get(primeiro_aluno, None)
        turma_id_consistente = generate_uuid(str(student_class) + str(shift) + str(self.student_year))

        for student in df.index:
            shift = self.shifts_dict.get(student, None)
            aluno_id = self.aluno_id_map.get(student.replace("Aluno(a):", "").strip())
            for discipline in self.disciplines_columns:
                if discipline in df.columns and discipline not in duplicate_disciplines:
                    disciplines_classes.append({
                        "disciplina_id": self.discipline_id.get(discipline),
                        "turma_id": turma_id_consistente,

                    })
                    duplicate_disciplines.add(discipline)

            studants_classes.append({
                "aluno_id":  aluno_id,
                "turma_id":turma_id_consistente,
            })


            # TODO: Implement logic to retrieve professor_id and disciplina_id
            # professors_disciplines.append({
            #     "professor_id": "NOT IMPLEMENTED",
            #     "disciplina_id": "NOT IMPLEMENTED",
            # })


        professors_disciplines.append({
            "professor_id": "NOT IMPLEMENTED",
            "disciplina_id": "NOT IMPLEMENTED",
        })

        return studants_classes, disciplines_classes, professors_disciplines


