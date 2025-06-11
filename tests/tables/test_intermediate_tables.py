import unittest
import pandas as pd
from tables.intermediate_tables import IntermediateTables

class TestIntermediateTables(unittest.TestCase):
    def setUp(self):
        self.data = {
            "Aluno": ["Aluno1", "Aluno2"],
            "Disciplina": ["Disciplina1", "Disciplina2"]
        }
        self.df = pd.DataFrame(self.data)
        self.intermediate_tables = IntermediateTables(self.df, ["Disciplina"], {"Disciplina1": "ID1"}, ["Turma"], "2023", {"Aluno1": "Manhã", "Aluno2": "Tarde"})

    def test_create_schema(self):
        studants_classes, disciplines_classes, professors_disciplines = self.intermediate_tables.create_schema()
        self.assertIsInstance(studants_classes, list)
        self.assertIsInstance(disciplines_classes, list)
        self.assertIsInstance(professors_disciplines, list)
        expected_keys_students = ["aluno_id", "turma_id"]
        expected_keys_disciplines = ["disciplina_id", "turma_id"]
        for item in studants_classes:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys_students))
        for item in disciplines_classes:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys_disciplines))

if __name__ == "__main__":
    unittest.main()