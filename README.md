# Sistema de Gestão Escolar com ETL

## 📖 Sobre o Projeto

Este é um sistema de gestão escolar desenvolvido em Python com o framework Flask. A aplicação web permite o gerenciamento de dados acadêmicos, como alunos, turmas, notas e materiais de aula, através de painéis dedicados para três perfis de usuário: **Administrador**, **Professor** e **Aluno**.

Um dos principais diferenciais do projeto é seu robusto processo de **ETL (Extração, Transformação e Carga)**, que permite a migração de dados a partir de múltiplos arquivos de boletins em formato Excel (`.xls`, `.xlsx`), populando o banco de dados de forma automatizada e consistente.

O sistema utiliza SQLAlchemy para a interação com o banco de dados MySQL e Flask-SocketIO para notificações em tempo real.

## ✨ Funcionalidades Principais

### Painel do Administrador
* **Dashboard Central:** Visualização de estatísticas vitais e um gráfico de distribuição de alunos por turma.
* **Processo de ETL:** Interface para upload de boletins em Excel, que limpa e insere os dados acadêmicos no banco de dados.
* **Gerenciamento de Usuários:** CRUD completo para usuários dos perfis `admin`, `professor` e `aluno`.
* **Gerenciamento de Matrículas e Disciplinas:** Ferramentas para matricular alunos em turmas e gerenciar as disciplinas do sistema.
* **Visualizador de Logs:** Acesso direto aos logs da aplicação para facilitar a depuração.

### Painel do Professor
* **Gestão de Notas:** Lançamento de notas bimestrais e faltas para alunos em suas turmas.
* **Diário de Classe:** Registro de conteúdo ministrado e controle de presença por aula.
* **Publicação de Conteúdo:** Ferramentas para criar e gerenciar anúncios e materiais de aula.
* **Edição de Conteúdo:** Possibilidade de editar anúncios e materiais já publicados.
* **Análise de Desempenho:** Gráfico de desempenho individual do aluno na tela de lançamento de notas.

### Painel do Aluno
* **Dashboard Pessoal:** Visualização de anúncios, materiais de aula e um gráfico de desempenho pessoal.
* **Consulta de Notas:** Acesso ao boletim com notas bimestrais, média final e total de faltas.
* **Exportação de Boletim:** Funcionalidade para baixar o boletim em formato PDF.
* **Interatividade:** Possibilidade de deixar comentários nos anúncios publicados pelos professores.

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python 3, Flask
* **Banco de Dados:** MySQL
* **ORM:** SQLAlchemy Core
* **Comunicação em Tempo Real:** Flask-SocketIO
* **Frontend:** HTML, Bootstrap 5, JavaScript, Chart.js
* **Geração de PDF:** FPDF2

## 🚀 Como Executar o Projeto

### Pré-requisitos
* Python 3.10 ou superior
* MySQL Server
* Git

### 1. Clone o Repositório
```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd ETL_Excel
```

### 2. Crie e Ative um Ambiente Virtual
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as Dependências
O arquivo `requirements.txt` não foi fornecido, mas você pode gerá-lo com o comando abaixo no seu ambiente local:
```bash
pip freeze > requirements.txt
```
E então, para instalar:
```bash
pip install -r requirements.txt
```

### 4. Configure o Banco de Dados
O sistema utiliza dois bancos de dados: `audit_database` e `bancotest`. Crie-os no seu servidor MySQL.

### 5. Configure as Variáveis de Ambiente
No arquivo `config.py`, ajuste as strings de conexão (`SQLALCHEMY_DATABASE_URI` e `SQLALCHEMY_BINDS`) com suas credenciais do MySQL.

### 6. Crie as Tabelas e o Superusuário
O sistema cria as tabelas automaticamente na primeira execução. Para criar o primeiro usuário administrador, utilize o script fornecido:
```bash
python tools/create_super_user.py
```

### 7. Execute a Aplicação
```bash
flask run
```
Acesse `http://127.0.0.1:5000/login` no seu navegador.


## 🤝 Como Contribuir

1.  Faça um *fork* do projeto.
2.  Crie uma nova *branch* (`git checkout -b feature/nova-feature`).
3.  Faça o *commit* das suas alterações (`git commit -m 'Adiciona nova feature'`).
4.  Faça o *push* para a *branch* (`git push origin feature/nova-feature`).
5.  Abra um *Pull Request*.

---