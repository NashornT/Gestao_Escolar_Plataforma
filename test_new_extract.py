import pandas as pd
import xlrd
import os
from sqlalchemy import create_engine


class ExtractData:

    def __init__(self, folder_path, db_path):
        self.folder_path = folder_path
        self.db_path = db_path
        self.file = None
        self.studant_dict = dict()
        self.disciplines_columns = ['Língua Portuguesa', 'Artes', 'Ciências', 'Matemática', 'Geografia', 'História',
                                    'Cidadania/Ética', 'Inglês'
                                    'PORTUGUÊS', 'MATEMÁTICA', 'HIST. e GEOGR.', 'CIÊNCIAS', 'Educação Física']

    def open_file(self):
        """Open the .xls file."""
        self.workbook = xlrd.open_workbook(self.file)
        self.sheet = self.workbook.sheet_by_index(0)


    def adjustment_keys(self, key ,studant_key, studant_data):
        """Adjust the keys for the dictionary."""

        if studant_key == 'Aluno(a):':
            del self.studant_dict[studant_key]
            studant_key = studant_data[0]
            self.studant_dict.update({studant_key: {}})

        if key == "CÓDIGOS E":
            key = studant_data[2]
            studant_data.remove("CÓDIGOS E")
        elif key not in self.disciplines_columns:
            key = studant_data[0]

        if key == 'BASE NACIONAL COMUM':
            key = studant_data[2]
            studant_data.remove(studant_data[0])
            studant_data.remove(studant_data[1])

        if key in self.disciplines_columns:
            for data in studant_data:
                if type(data) == str:
                    studant_data.remove(data)

        if key in studant_data:
            studant_data.remove(key)

        return key, studant_key

    def get_data(self):
        """Extract data from the .xls file."""
        self.open_file()

        studant_key = str
        for row_idx in range(self.sheet.nrows):
            studant_data = list()
            for data in self.sheet.row_values(row_idx):
                if "Aluno" in str(data):
                    studant_key = data
                    self.studant_dict.update({studant_key: {}})
                elif data != "":
                    studant_data.append(data)

            if len(studant_data) > 1:
                key = studant_data[1]

                key, studant_key = self.adjustment_keys(key,studant_key, studant_data)

                if key != studant_key:
                    self.studant_dict.get(studant_key).update({key: studant_data})

    def normalize_data(self, df):
        """Normaliza os dados do DataFrame para um formato relacional."""

        # Garantir que os nomes das colunas estejam corretos
        df.columns = [col.strip() for col in df.columns]  # Remove espaços extras

        # Identificar colunas de escolaridade dinamicamente
        escolaridade_colunas = [col for col in df.columns if "Ano de Escolaridade" in col or "PRÉ" in col or 'Pré' in  col]


        if not escolaridade_colunas:
            raise KeyError("Nenhuma coluna de escolaridade encontrada no DataFrame.")

        # Tabela de alunos
        alunos = []
        for aluno in df.index:
            for col in escolaridade_colunas:
                if col in df.columns:
                    value = df.loc[aluno, col]
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        grade_level, shift = value
                    else:
                        grade_level, shift = value, None  # Caso não seja iterável, atribua `None` ao turno
                    alunos.append({
                        "aluno_id": hash(aluno),  # Gerar um ID único
                        "nome": aluno,
                        "nivel_escolar": grade_level,
                        "turno": shift
                    })

        # Tabela de disciplinas
        disciplinas = [{"disciplina_id": hash(d), "nome": d} for d in self.disciplines_columns]

        # Tabela de notas
        notas = []
        for aluno in df.index:
            aluno_id = hash(aluno)
            for disciplina in self.disciplines_columns:
                if disciplina in df.columns:
                    notas.append({
                        "aluno_id": aluno_id,
                        "disciplina_id": hash(disciplina),
                        "notas": df.loc[aluno, disciplina]
                    })

        return pd.DataFrame(alunos), pd.DataFrame(disciplinas), pd.DataFrame(notas)


    def save_to_database(self, alunos_df, disciplinas_df, notas_df):
        """Salva os dados normalizados em um banco de dados PostgreSQL."""
        try:
            # Criar a engine do SQLAlchemy
            engine = create_engine("postgresql+psycopg2://gustavoadm:senha123@localhost:5432/bancotest")

            # Salvar tabelas no banco
            alunos_df.to_sql("alunos", engine, if_exists="replace", index=False)
            disciplinas_df.to_sql("disciplinas", engine, if_exists="replace", index=False)
            notas_df.to_sql("notas", engine, if_exists="replace", index=False)

            print("Dados salvos no banco de dados PostgreSQL com sucesso!")
        except Exception as e:
            print(f"Erro ao salvar no banco de dados: {e}")

    def manipulate_data(self):
        """Manipula os dados extraídos e os salva no banco relacional."""
        self.get_data()

        # Converter o dicionário para um DataFrame
        df = pd.DataFrame.from_dict(self.studant_dict, orient='index')

        # Remover colunas indesejadas
        colunas_para_remover = ['ÁREAS DE', 'RB', 'LEGENDA', 'CONHECIMENTO', 'N', 'Disciplinas']
        for column in colunas_para_remover:
            if column in df.columns:
                df = df.drop(columns=column)

        # Normalizar os dados
        alunos_df, disciplinas_df, notas_df = self.normalize_data(df)


        # Criar pasta para salvar os arquivos CSV
        output_folder = os.path.join(self.folder_path, "outputs")
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # # Salvar os DataFrames em arquivos CSV
        # alunos_df.to_csv(os.path.join(output_folder, "alunos.csv"), index=False, encoding="utf-8-sig")
        # disciplinas_df.to_csv(os.path.join(output_folder, "disciplinas.csv"), index=False, encoding="utf-8-sig")
        # notas_df.to_csv(os.path.join(output_folder, "notas.csv"), index=False, encoding="utf-8-sig")


        print(f"Arquivos CSV salvos na pasta: {output_folder}")

        # Salvar no banco de dados
        # self.save_to_database(alunos_df, disciplinas_df, notas_df)

    def run(self):
        """Executa o processo de extração e manipulação."""
        for file in os.listdir(self.folder_path):
            if file.endswith('.xls'):
                self.file = os.path.join(self.folder_path, file)
                self.studant_dict = {}
                self.manipulate_data()