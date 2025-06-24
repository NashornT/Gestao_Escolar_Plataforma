# Sistema de Gerenciamento Escolar

Este é um sistema de gerenciamento escolar desenvolvido em Python, utilizando Flask como framework principal. Ele permite o gerenciamento de alunos, turmas, notas e relatórios.

## Funcionalidades

- **Processamento de Arquivos**: Upload de arquivos `.xls` ou `.xlsx` para processamento.
- **Geração de Relatórios**: Geração de relatórios detalhados.
- **Histórico Escolar**: Download de históricos escolares em formato Excel.
- **Gerenciamento de Dados**: Possibilidade de baixar dados do sistema.
- **Integração com WebSocket**: Comunicação em tempo real utilizando Socket.IO.

## Tecnologias Utilizadas

- **Back-end**: Python (Flask)
- **Front-end**: HTML, CSS (Bootstrap), JavaScript
- **Banco de Dados**: SQLite (com planos para migração para PostgreSQL ou MySQL)
- **Outras Bibliotecas**: 
  - Flask-SocketIO
  - Bootstrap 5
  - Fetch API para requisições assíncronas

## Requisitos

- Python 3.8 ou superior
- Pipenv ou outro gerenciador de dependências
- Banco de dados SQLite (ou outro configurado no futuro)

## Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/seu-repositorio.git
   cd seu-repositorio