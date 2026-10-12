# EscolaIA — Etapa 1

Protótipo local em Flask + SQLite. **Usa somente dados fictícios.** Ainda não contém LLM, RAG nem MCP.

## Windows / PowerShell

```powershell
cd escola_ia
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Acesse http://127.0.0.1:5000

Se o PowerShell bloquear a ativação, execute diretamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

O arquivo `escola.db` é criado automaticamente e recebe dados fictícios na primeira execução. Para reiniciar os dados, pare o servidor e apague `escola.db`.

**Observações:** O Bootstrap e jQuery usam CDN (necessitam internet para carregar o visual). A aplicação e o banco rodam localmente. O servidor de desenvolvimento não tem autenticação, proteção CSRF ou configuração para produção; não cadastre dados reais de crianças. O cadastro de turma é básico; edição/exclusão de turmas e autenticação ficam para evolução posterior.


## Interface
Bootstrap 5.3.8 via CDN (CSS e bundle JS), com jQuery 3.6.4 mantido para a busca de alunos e confirmação de exclusão. Para trabalhar sem internet, baixe os arquivos de Bootstrap e jQuery e ajuste os caminhos em `templates/base.html`.


## Organização do JavaScript

- `static/js/mfunctions.js`: funções reutilizáveis.
- `static/js/mscripts.js`: eventos jQuery delegados em `body`.
- IDs específicos em formulários e botões; classes compartilhadas para ações repetidas.
- Mensagens flash do Flask desaparecem após 4 segundos via Bootstrap Alert.

**Importante:** esta distribuição mantém a referência às bibliotecas locais que você já instalou no projeto (`static/css/bootstrap.min.css`, `static/js/bootstrap.bundle.min.js` e `static/js/jquery-3.6.4.min.js`). Esses três arquivos de terceiros não estão incluídos neste ZIP. Copie-os do seu projeto atual, assim como seu `escola.db` com dados existentes. Não substitua seu banco por um arquivo de exemplo.
