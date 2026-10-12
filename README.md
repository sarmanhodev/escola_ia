# 🎓 EscolaIA — Gestão Escolar com Inteligência Artificial Local

**Sistema de gestão escolar desenvolvido com Python e Flask, integrado ao modelo de linguagem Qwen3 por meio do Ollama, para consultas inteligentes, análise de indicadores educacionais e geração de diagnósticos pedagógicos.**

O **EscolaIA** é um projeto de portfólio Full Stack que explora a integração entre aplicações web, bancos de dados relacionais e Inteligência Artificial generativa.

Seu principal objetivo é demonstrar como modelos de linguagem podem complementar sistemas tradicionais, permitindo que informações estruturadas sejam consultadas em linguagem natural, sem abrir mão da precisão dos dados e do controle sobre as respostas.

---

## 🚀 Funcionalidades

### 📚 Gestão Escolar
- Cadastro, edição e exclusão de alunos.
- Gerenciamento de turmas e anos letivos.
- Registro e atualização de notas por disciplina e bimestre.
- Controle de frequência escolar.
- Dashboard com indicadores acadêmicos.

### 🤖 Assistente de Inteligência Artificial
- Interface de chat integrada à aplicação Flask.
- Consultas escolares realizadas em linguagem natural.
- Histórico de conversas persistido no banco de dados.
- Interpretação contextual de perguntas.
- Identificação de alunos pelo nome, com tratamento de ambiguidades.
- Restrição das respostas ao domínio escolar suportado pelo sistema.

### 📊 Análises e Diagnósticos Pedagógicos
- Identificação de alunos com médias abaixo do valor de referência.
- Análise de frequência e identificação de possíveis situações de atenção.
- Comparação de indicadores entre turmas.
- Consultas por disciplinas e desempenho acadêmico.
- Diagnósticos individuais baseados em notas e frequência.
- Interpretação pedagógica complementar com auxílio da IA.

---

## 🧠 Arquitetura de Inteligência Artificial

O EscolaIA utiliza uma **arquitetura híbrida**, combinando processamento determinístico em Python com interpretação assistida por um modelo de linguagem local.

A aplicação não depende exclusivamente da IA para realizar cálculos ou consultar informações acadêmicas.

O fluxo de processamento é organizado em etapas:

**1. Entrada em linguagem natural**

O usuário realiza uma pergunta por meio da interface de chat.

**2. Interpretação da consulta**

O sistema identifica a intenção da pergunta, os parâmetros necessários e o contexto da conversa.

**3. Consulta estruturada**

O Python, utilizando SQLAlchemy, consulta os registros escolares armazenados no SQLite.

**4. Processamento e validação**

Os indicadores são calculados pela aplicação, respeitando as regras estabelecidas para médias, notas e frequência.

**5. Interpretação assistida por IA**

Quando aplicável, o Qwen3 recebe informações previamente estruturadas e verificadas para produzir uma análise pedagógica complementar.

**6. Resposta ao usuário**

O resultado é apresentado no chat, com histórico persistido para consultas posteriores.

### 🛡️ Controle de respostas e redução de alucinações

Um dos principais desafios técnicos do projeto foi reduzir respostas inconsistentes produzidas pelo modelo de linguagem.

Para isso, foram adotadas estratégias como:

- Separação entre cálculos acadêmicos e interpretação textual.
- Utilização de dados estruturados como referência factual.
- Restrição das consultas ao domínio escolar.
- Tratamento de informações insuficientes e nomes ambíguos.
- Preservação dos indicadores calculados pelo Python quando a IA local está indisponível.

**A proposta é utilizar a IA como uma camada de interpretação, mantendo a aplicação responsável pela integridade dos dados e pelas regras de negócio.**

---

## 💻 Tecnologias Utilizadas

| Tecnologia | Aplicação |
|---|---|
| Python | Linguagem principal e regras de negócio |
| Flask | Aplicação web e endpoints REST |
| SQLAlchemy | ORM e consultas ao banco de dados |
| SQLite | Persistência de dados escolares e conversas |
| Qwen3 1.7B | Modelo de linguagem para interpretação pedagógica |
| Ollama | Execução local do modelo de IA |
| HTML, CSS e JavaScript | Interface web |
| Faker | Geração de dados sintéticos para demonstração |

---

## 💬 Exemplos de Consultas

O assistente permite realizar perguntas como:

- Quantos alunos estão cadastrados?
- Qual turma possui a maior média em Matemática?
- Quais alunos apresentam frequência inferior a 75%?
- Quais alunos possuem média abaixo de 6?
- Faça uma análise pedagógica de um aluno.
- Quais alunos apresentam simultaneamente baixo desempenho e baixa frequência?

As consultas são processadas de acordo com as intenções e os parâmetros reconhecidos pela aplicação.

---

## ⚙️ Instalação e Execução

### Pré-requisitos

- Python 3.10 ou superior.
- Ollama instalado.
- Git.

### 1. Clonar o repositório

```bash
git clone https://github.com/sarmanhodev/escola_ia.git
cd escola_ia
```

### 2. Criar o ambiente virtual

```bash
python -m venv env
```

No Windows:

```bash
env\Scripts\activate
```

No Linux/macOS:

```bash
source env/bin/activate
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar o ambiente

Crie um arquivo `.env` a partir do `.env.example` e configure a variável `SECRET_KEY`.

### 5. Preparar o modelo de IA

```bash
ollama pull qwen3:1.7b
```

Certifique-se de que o serviço do Ollama esteja em execução.

### 6. Inicializar o banco de dados

```bash
flask --app app init-db
```

### 7. Gerar dados fictícios

```bash
python popular_banco.py
```

### 8. Executar a aplicação

```bash
python app.py
```

Acesse:

**http://127.0.0.1:5000**

---

## 🗃️ Dados de Demonstração

O projeto utiliza o SQLite como banco de dados local.

O script `popular_banco.py` permite gerar registros sintéticos de alunos, turmas, notas e frequência, com diferentes perfis de desempenho acadêmico.

Esses dados são destinados exclusivamente à demonstração das funcionalidades, sem necessidade de utilizar informações reais de estudantes.

---

## 🎯 Objetivo do Projeto

O EscolaIA foi desenvolvido como um projeto prático de estudo e portfólio, com foco em:

- Desenvolvimento Full Stack com Python e Flask.
- Integração de modelos de linguagem locais em aplicações web.
- Consultas contextuais sobre dados relacionais.
- Aplicação de regras de negócio e validação determinística.
- Redução de respostas incorretas em sistemas assistidos por IA.
- Organização de código, APIs e persistência de informações.

O projeto demonstra que integrar Inteligência Artificial a um sistema envolve mais do que conectar uma API ou executar um modelo: exige **arquitetura, tratamento de dados, definição de limites e confiabilidade das respostas**.

---

## 👨‍💻 Autor

Desenvolvido por **Diego Sarmanho**.

Desenvolvedor Full Stack com atuação em Python, PHP, APIs REST, automação, análise de dados e Inteligência Artificial aplicada a sistemas.

**Portfólio:** https://portifolio-sarmanho.onrender.com/home

---

⭐ **EscolaIA — Transformando dados escolares em informações acessíveis por meio da Inteligência Artificial.**
