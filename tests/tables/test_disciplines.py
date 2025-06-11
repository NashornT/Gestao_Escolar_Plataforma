import unittest
import pandas as pd
from tables.disciplinas import Disciplina

class TestDisciplina(unittest.TestCase):
    def setUp(self):
        self.data = {
            "Língua Portuguesa": ["Nota1", "Nota2"],
            "HIST. e GEOGR.": ["Nota3", "Nota4"]
        }
        self.df = pd.DataFrame(self.data)
        self.disciplina = Disciplina(self.df, ["Língua Portuguesa", "HIST. e GEOGR."], {"Língua Portuguesa": "ID1", "HIST. e GEOGR.": "ID2"})

    def test_create_schema(self):
        result = self.disciplina.create_schema()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), len(self.disciplina.disciplines_columns))
        expected_keys = ["disciplina_id", "disciplina"]
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys))

if __name__ == "__main__":
    unittest.main()