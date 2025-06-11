import unittest
import pandas as pd
from tables.students import Students

class TestStudents(unittest.TestCase):
    def setUp(self):
        # Configura o DataFrame de teste com os dados esperados
        self.data = {
            "Nome": ["Aluno1", "Aluno2"],
            "6° Ano de Escolaridade - 601": [["6° Ano", "Manhã"], ["6° Ano", "Tarde"]],
            "FALTAS": [[1, 2, 3], [4, 5, 6]]
        }
        self.df = pd.DataFrame(self.data)
        self.df.index = self.df["Nome"]  # Define o índice como os nomes dos alunos
        self.students = Students(self.df, ["6° Ano de Escolaridade - 601"], "2023")

    def test_create_schema(self):
        # Executa o método create_schema
        result, shifts_dict = self.students.create_schema()

        # Verifica se o resultado é uma lista
        self.assertIsInstance(result, list)

        # Verifica se o tamanho da lista corresponde ao número de alunos
        self.assertEqual(len(result), len(self.df.index), "O número de estudantes retornado está incorreto.")

        # Verifica se cada item contém as chaves esperadas
        expected_keys = ["aluno_id", "aluno", "total_faltas", "matricula", "resonsavel_id", "data_nascimento", "endereco", "sexo", "status"]
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys))

if __name__ == "__main__":
    unittest.main()