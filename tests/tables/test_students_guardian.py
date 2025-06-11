import unittest
import pandas as pd
from tables.students_guardian import StudentsGuardian

class TestStudentsGuardian(unittest.TestCase):
    def setUp(self):
        self.data = {
            "Nome": ["Aluno1", "Aluno2"],
            "RESPONSÁVEL": ["Responsável1", "Responsável2"]
        }
        self.df = pd.DataFrame(self.data)
        self.df["Nome"] = self.df["Nome"].astype(str)  # Garante que os valores sejam strings
        self.students_guardian = StudentsGuardian(self.df)

    def test_create_schema(self):

        result = self.students_guardian.create_schema()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), len(self.df.index))
        expected_keys = ["aluno_id", "nome", "telefone", "endereco_id", "cpf", "email", "parentesco"]
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys))

if __name__ == "__main__":
    unittest.main()