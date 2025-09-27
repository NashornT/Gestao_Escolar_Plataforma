import unittest
import pandas as pd
from tables.grades import Grades

class TestGrades(unittest.TestCase):
    def setUp(self):
        # Certifique-se de que os dados estão no formato esperado
        self.data = {
            "Disciplina1": [[5, 6, 7, 8], [6, 7, 8, 9]],
            "Disciplina2": [[4, 5, 6, 7], [5, 6, 7, 8]]
        }
        self.df = pd.DataFrame(self.data, index=["Aluno1", "Aluno2"])
        self.grades = Grades(self.df, {"Disciplina1": "ID1", "Disciplina2": "ID2"}, "2023", ["Disciplina1", "Disciplina2"], "xls")

    def test_create_schema(self):
        # Executa o método create_schema
        result = self.grades.create_schema()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0, "A lista retornada está vazia. Verifique os dados de entrada e a lógica.")

        # Verifica se cada item contém as chaves esperadas
        expected_keys = ["nota_id", "aluno_id", "ano_letivo", "disciplina_id", "nota_1_bimestre", "nota_total", "media_final"]
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys))

if __name__ == "__main__":
    unittest.main()