import unittest
import pandas as pd
from tables.address import Address

class TestAddress(unittest.TestCase):
    def setUp(self):
        # Configura um DataFrame de exemplo para os testes
        self.data = {
            "Nome": ["Aluno1", "Aluno2"],
            "ENDEREÇO": ["Rua A, 123", "Rua B, 456"]
        }
        self.df = pd.DataFrame(self.data)
        self.address = Address(self.df)

    def test_create_schema(self):
        # Executa o método create_schema
        result = self.address.create_schema()

        # Verifica se o resultado é uma lista
        self.assertIsInstance(result, list)

        # Verifica se o tamanho da lista corresponde ao número de alunos
        self.assertEqual(len(result), len(self.df.index))

        # Verifica se cada item da lista é um dicionário com as chaves esperadas
        expected_keys = ["aluno_id", "logradouro", "numero", "complemento", "bairro", "cidade", "cep", "endereco_id"]
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(all(key in item for key in expected_keys))

if __name__ == "__main__":
    unittest.main()