import unittest
import pandas as pd
from tables.professors import Professors

class TestProfessors(unittest.TestCase):
    def setUp(self):
        self.data = {
            "Nome": ["Professor1", "Professor2"],
            "Email": ["email1@example.com", "email2@example.com"]
        }
        self.df = pd.DataFrame(self.data)
        self.professors = Professors(self.df)

    def test_create_schema(self):
        result = self.professors.create_schema()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), len(self.df.index))
        expected_keys = ["professor_id", "nome", "email", "telefone", "endereco_id"]
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys))

if __name__ == "__main__":
    unittest.main()