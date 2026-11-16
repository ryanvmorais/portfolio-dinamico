# CLAUDE.md

Este arquivo fornece orientações ao Claude Code (claude.ai/code) ao trabalhar com o código neste repositório.

## Visão Geral do Projeto

Portfólio profissional pessoal do mantenedor do repositório, construído com Django 6.1.
Projeto educacional de app único (`app_portfolio`) que serve uma página única
(a home): perfil do desenvolvedor, projetos, habilidades técnicas,
estatísticas de destaque e um formulário de contato com camadas anti-spam.
Deploy: processo único (WSGI, gunicorn), SQLite em dev e em produção (num volume,
pelo `DIRETORIO_DADOS`); receita de build da plataforma no `railpack.json`
(spec 006).

> **Python 3.12 é o piso (`requires-python = ">=3.12"`):** é o mínimo do Django 6.1. O `.python-version` fixa o 3.12 no desenvolvimento, o CI testa do 3.12 ao 3.15 (matriz) e `ruff`, `black` e `mypy` apontam para o 3.12: não use sintaxe exclusiva de versão mais nova (ex.: `except A, B:` sem parênteses, do 3.14).

## Comandos Comuns

```bash
# Sincronizar o ambiente (.venv) a partir do uv.lock — dev: runtime + grupo dev (padrão)
uv sync

# Ambiente de produção: runtime + extras de prod (gunicorn, psycopg2-binary), sem ferramentas de dev
uv sync --no-dev --extra prod

# Gerenciar dependências (atualiza pyproject.toml + uv.lock automaticamente)
uv add <pacote>                       # dependência de runtime
uv add --dev <pacote>                 # ferramenta de desenvolvimento
uv remove <pacote>
uv lock --upgrade-package <pacote>    # atualiza só um pacote no lock

# Iniciar servidor de desenvolvimento (requer .env com SECRET_KEY)
uv run python manage.py runserver

# Migrações do banco de dados
uv run python manage.py makemigrations
uv run python manage.py migrate

# Criar superusuário para o Admin
uv run python manage.py createsuperuser

# Dados de demonstração (só com DEBUG=True)
uv run python manage.py semear_dados_demo

# Coletar arquivos estáticos (pré-deploy)
uv run python manage.py collectstatic --noinput

# Executar todos os testes
uv run pytest

# Executar um teste específico
uv run pytest app_portfolio/tests.py::TestSegurancaContato::test_rate_limit_blocking -v

# Executar testes com relatório de cobertura
uv run pytest --cov=app_portfolio --cov-report=term-missing

# Linting, formatação e type checking (config centralizada em pyproject.toml)
uv run ruff check .                        # Lint (substitui flake8 + isort)
uv run ruff check --fix .                  # Corrige automaticamente o que for seguro
uv run black .                             # Formatação
uv run mypy app_portfolio portfolio        # Verificação de tipos estáticos (mypy + django-stubs)

# Auditoria de dependências (CVEs conhecidas)
uv run pip-audit

# Checagem de postura de produção (SSL, HSTS, cookies, headers)
DEBUG=False uv run python manage.py check --deploy
```

## Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto. `SECRET_KEY` é a única variável
obrigatória (o servidor não sobe sem ela — `settings.py` levanta `ValueError`
com o caminho verificado). O arquivo `.env.example` (commitado no repositório)
serve de template documentado com todos os placeholders.

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SECRET_KEY` | **obrigatória** | Chave secreta do Django |
| `DEBUG` | `False` | Defina como `True` só em desenvolvimento local |
| `ADMIN_URL` | `admin/` | Caminho do painel Admin — troque em produção para dificultar brute-force automatizado |
| `ALLOWED_HOSTS` | `*` (dev) | Lista de hosts permitidos em produção, separados por vírgula; vazio em produção rejeita todo host (falha fechada) |
| `EMAIL_USER` | — | Conta Gmail que envia (e recebe) as notificações do formulário de contato; vazio com `DEBUG=True` imprime o e-mail no terminal (backend de console) |
| `EMAIL_PASS` | — | **Senha de app** do Gmail (não a senha normal da conta) |
| `MODO_DEMONSTRACAO` | `False` | `True` numa demo pública: o formulário valida, mas não grava nem envia, e avisa o visitante (spec 005) |
| `DIRETORIO_DADOS` | raiz do repositório | Pasta de `db.sqlite3`, `media/` e `django_cache/`; num contêiner, o caminho do volume persistente (ex.: `/data`). Relativo parte da raiz (spec 006) |

## Arquitetura

### Estrutura do projeto

```
portfolio/           # Configuração do projeto Django (settings, urls raiz, wsgi/asgi)
app_portfolio/        # A única aplicação
  models.py           # Todos os modelos de dados
  views.py             # home (GET da vitrine + POST do formulário de contato) e servir_midia (/media/ com e sem DEBUG)
  forms.py             # MensagemContatoForm (ModelForm)
  admin.py             # Admin customizado para cada modelo
  utils.py             # converter_para_webp() — conversor universal de imagem
  middleware.py        # PermissionsPolicyMiddleware: cabeçalho Permissions-Policy (o Django não tem configuração para ele)
  cache.py             # CacheArquivoAtomico: FileBasedCache com add() atômico (trava de arquivo), usado pelo rate limit
  urls.py              # URLs da aplicação (só a home)
  tests.py             # Suíte de testes (pytest): modelos, view e segurança do contato, ver "Qualidade" abaixo
  test_interface.py    # Testes das correções da auditoria de interface (spec 004): HTML, view, páginas de erro, CSS e JS lidos como texto
  test_semear_dados_demo.py # Testes do comando de demonstração e do Lighthouse CI
  test_readme_en.py    # Compara o README.en.md com o README.md (títulos, tabela, selos, blocos, links)
  test_comentarios_templates.py # Guarda a regra dos comentários dos templates ({# #}, nunca <!-- -->)
  test_impessoalidade.py # Falha se o nome do mantenedor aparecer em arquivo versionado ou se este arquivo citar skill pessoal
  management/commands/semear_dados_demo.py # Dados fictícios (Lighthouse CI e dev)
  migrations/
templates/            # Templates HTML na raiz do projeto (não dentro de app_portfolio)
  base.html
  home.html            # Única página: Hero, Sobre, Projetos, Habilidades, Contato
  erro.html            # Base independente das páginas de erro (não herda o base.html)
  400.html             # Pedido inválido, ex.: Host fora do ALLOWED_HOSTS (estende erro.html)
  403.html             # Ação não permitida (estende erro.html)
  403_csrf.html        # Falha de CSRF: o Django procura este nome, não o 403.html (estende erro.html)
  404.html             # Página não encontrada (estende erro.html)
  500.html             # Erro do servidor, sem banco e sem contexto (estende erro.html)
static/
  css/styles.css       # Folha única (4 espaços, aspas simples): tokens, seções, avisos, erro, toque, movimento reduzido
  css/fontes.css       # @font-face de Inter e JetBrains Mono (hospedadas em static/fonts/)
  fonts/               # woff2 variáveis (latin) + licenças OFL
  js/main.js           # JavaScript vanilla (menu mobile com inert, filtros, avisos, formulário AJAX)
  icons/                # SVGs de UI, tecnologias e redes sociais; default_perfil/default_projeto.webp (reserva) e favicon.webp
railpack.json          # Receita de build e start da Railway (uv sync --locked, collectstatic; migrate && gunicorn)
pyproject.toml         # Gerenciado com uv. [project]=runtime, [dependency-groups].dev, [project.optional-dependencies].prod + config das ferramentas (ruff, black, mypy, pytest)
uv.lock                # Lock único gerado por `uv lock` — todo o grafo pinado (NUNCA editar à mão)
.python-version        # Fixa o Python 3.12 (o piso) no desenvolvimento
.venv/                 # Ambiente virtual gerenciado pelo uv (gitignored; criado por `uv sync`)
.env.example           # Template documentado de variáveis de ambiente (commitado no repo)
django_cache/          # Cache em arquivo do rate limit (gitignored)
media/                 # Uploads do Admin (gitignored)
assets/                # Capa dos READMEs (portfolio-django-home-desktop.png) e imagem de social preview (1280×640; o envio é manual, em Settings)
README.en.md           # README em inglês (repo público é bilíngue): mesmas seções do README.md, na mesma ordem
CONTRIBUTING.md        # Guia de contribuição
SECURITY.md            # Política de segurança: relato privado pelos avisos do GitHub, prazos e escopo
LICENSE                # MIT
.github/                # Serviços do GitHub (commitado)
  workflows/ci.yml       # CI: job "qualidade" (ruff/black/mypy/pytest) + job "seguranca" (pip-audit + check --deploy); em push na main e em PR
  workflows/pip-audit.yml # pip-audit semanal sobre o uv.lock (segunda 09:00 de São Paulo e à mão)
  workflows/codeql.yml   # CodeQL (code scanning) de Python: PR, main e semanal
  workflows/lighthouse.yml # Lighthouse CI (config e resumo em .github/lighthouse/)
  dependabot.yml         # PRs de atualização de dependências aos domingos, agrupados por ecossistema (uv + github-actions)
  ISSUE_TEMPLATE/        # Formulário de dúvida, erro ou sugestão (+ config.yml sem issue em branco e com o atalho para o aviso privado de segurança)
  pull_request_template.md  # Corpo padrão do PR: o quê/por quê e "Closes #N"
specs/                  # Especificações (spec-driven development); ver specs/README.md
  README.md              # Metodologia, convenções e índice das specs
  NNN-feature/            # requirements.md + design.md + tasks.md por feature
docs/
  stack.md                # Mapa de cada tecnologia da stack: o que faz, por que foi escolhida, o que estudar
  referencia/             # Detalhes que não cabem aqui (arquitetura, configurações, quarentena do uv, cache, CI, interface)
```

### Modelos, imagens e formulário de contato

Os seis grupos de modelos (`models.py`), a conversão para WebP no `save()` (`utils.py`) e o fluxo
do POST do contato (`views.py`): `docs/referencia/arquitetura.md`: **leia antes de mexer em
`models.py`, `utils.py` ou na view `home`**. Requisitos e ADRs: `specs/001-vitrine-portfolio/` e
`specs/002-formulario-contato/`.

- ⚠️ `ImageField` novo: sobrescreva `save()`, chame `converter_para_webp()`, cheque `if novo_conteudo and novo_nome:` e grave com `save=False` (sem isso, recursão infinita).
- ⚠️ Ordem do POST: honeypot → validação → modo demonstração → rate limit (`cache.add`, atômico pela trava do `CacheArquivoAtomico`) → sanitização → gravação → e-mail.
- ⚠️ Falha do `send_mail()` é logada e nunca propaga: a mensagem já está no banco.
- ⚠️ AJAX e HTML dizem a mesma frase: use as constantes `MENSAGEM_*` do `views.py`, nunca texto solto.
- ⚠️ Os testes do contato dependem da fixture autouse `disable_real_email` (mailer `default` do `MAILERS` em `locmem`); sem ela, `send_mail()` usa o SMTP real do `.env`.
- ⚠️ E-mail só pelo `MAILERS` (Django 6.1), nunca `EMAIL_*`: com o `MAILERS` definido, ler `settings.EMAIL_*` dá `AttributeError`; o endereço da conta é o `ENDERECO_CONTATO`.
- ⚠️ `Perfil` não é singleton: um segundo registro faz `Perfil.objects.first()` devolver um qualquer.

### Interface e acessibilidade (spec 004)

As regras de interface (hero, menu inerte do celular, contraste, avisos, movimento
reduzido, fontes, imagens e páginas de erro; origem na spec `004-correcoes-de-interface`)
estão em `docs/referencia/interface-e-acessibilidade.md`: **leia antes de mexer na interface**.

> ⚠️ **Não regredir (dado opcional):** `foto`, `curriculo`, `link_github` do
> projeto e as redes do `Perfil` são opcionais. `{{ perfil.curriculo.url }}` sem
> `{% if perfil.curriculo %}` levanta `ValueError` e a home inteira dá erro 500;
> `{{ projeto.link_github }}` sem guarda vira `href="None"`. Campo com
> `blank=True` pede a guarda no template e um teste com o campo vazio.

> ⚠️ **Não regredir (formatador):** `styles.css` e `main.js` usam 4 espaços e
> aspas simples. Rodar o Prettier no arquivo inteiro reescreve tudo e apaga o diff
> real; edite só o trecho. Ver `specs/README.md`, notas de manutenção.

### Configurações notáveis (em `portfolio/settings.py`)

Um único `settings.py` para dev e produção, ramificado por `if not DEBUG:`
(ADR-01 da spec 003). Middleware, segurança em produção (com o proxy), CSP,
estáticos, mídia (`servir_midia`), dados graváveis, banco, log e e-mail:
`docs/referencia/configuracoes.md`: **leia antes de mexer em `settings.py`**.

- ⚠️ `<script>` inline num template exige revisar o `script-src` do `CONTENT_SECURITY_POLICY`: o navegador bloqueia em silêncio.
- ⚠️ CSP só no dicionário `CONTENT_SECURITY_POLICY`: o django-csp 4 ignora os `CSP_*` antigos, e o cabeçalho some.
- ⚠️ Rate limit no `CacheArquivoAtomico` (`app_portfolio/cache.py`), nunca `LocMemCache` nem o `FileBasedCache` puro, cujo `add()` não é atômico (`docs/referencia/dependencias-e-cache.md`).
- ⚠️ `STORAGES["staticfiles"]`, nunca `STATICFILES_STORAGE`: o Django 6.1 o ignora (issue #38).
- ⚠️ `SECURE_PROXY_SSL_HEADER` supõe um proxy na frente: com o Django direto na internet, remova a linha (o cliente forjaria o `X-Forwarded-Proto`).

## Convenções

- **Idioma do código**: português — projeto pessoal/educacional. Vale para nomes
  de classes, funções, variáveis, commits, branches, docstrings e comentários
  técnicos. Ficam como estão: keywords da linguagem, nomes impostos pelo Django
  (`save`, `clean`, `get_queryset`…) e pelo pytest (`test_`), termos técnicos
  universais (API, HTTP, URL, JSON, HTML, CSS…) e as seções PEP 257 das
  docstrings (`Args:`, `Returns:`, `Raises:`). Texto que o visitante vê segue o
  idioma do site (português).
- **Estilo dos arquivos Python**: docstring de módulo, de classe e de função
  pública (seções `Args:`, `Returns:`, `Raises:` com o tipo repetido em cada
  entrada), assinaturas totalmente anotadas (`X | None`, `-> None` explícito) e
  comentários que explicam o *porquê*, não o *o quê*. Os commits seguem
  Conventional Commits.
- **Comentários nos templates**: comentário do Django, `{# #}` numa linha e
  `{% comment %}…{% endcomment %}` em várias (marcador de seção inclusive). `<!-- -->`
  vai para o HTML de cada visitante e o Django executa as tags dentro dele; `{# #}`
  quebrado em linhas aparece como texto. O `app_portfolio/test_comentarios_templates.py`
  guarda a regra.

## Qualidade e Automação (`pyproject.toml`)

Toda a configuração das ferramentas de qualidade é centralizada no
`pyproject.toml` (PEP 518): `black`, `ruff` (lint + isort), `pytest`,
`coverage` e `mypy` (modo strict, com `django-stubs`). A suíte de testes
relaxa `disallow_untyped_defs`/`disallow_incomplete_defs` porque usa fixtures
do `pytest-django` (`client`, `settings`) injetadas por parâmetro, sem tipo
prático a anotar sem importar internals do pytest.

**Fluxo de qualidade (rodar a partir da raiz, antes de commitar):**
```bash
uv run ruff check --fix .                  # 1. lint + ordena imports (ALTERA arquivos)
uv run black .                             # 2. formata (ALTERA arquivos)
uv run mypy app_portfolio portfolio        # 3. checa tipos (NÃO altera, só reporta)
uv run pytest                              # 4. roda os testes
```

Os testes ficam em arquivos ao lado do código, não numa pasta `tests/` (uma
única view e um punhado de models não justificam a divisão por módulo); o que
cada arquivo cobre está na árvore de "Estrutura do projeto". O `test_interface.py`
tem fixtures de isolamento próprias e um override no mypy.

> ⚠️ **Não regredir (README bilíngue):** `README.md` (português) e `README.en.md`
> mudam no mesmo PR, com as mesmas seções na mesma ordem; o `test_readme_en.py`
> quebra se os títulos, a tabela de tecnologias, os selos, os blocos de código ou
> os links de troca divergirem. O que o produto mostra (o site é em português) não
> se traduz.

**CI e automação:** o `ci.yml` (jobs `qualidade` e `seguranca`) roda em todo push na `main` e em
todo PR; pip-audit semanal, CodeQL, Lighthouse CI e Dependabot completam. Gatilhos e detalhes em
`docs/referencia/ci-e-automacao.md`: **leia antes de mexer em `.github/`**.

## Spec-Driven Development (em `specs/`)

A pasta `specs/` documenta cada feature em três arquivos versionados —
`requirements.md` (o quê/porquê + critérios de aceite em **Given/When/Then**),
`design.md` (arquitetura + ADRs) e `tasks.md` (quebra rastreável `tarefa →
requisito`). A metodologia, o status e o índice completo estão em
`specs/README.md`.

## Gestão de Dependências (uv)

O projeto é gerenciado pelo **uv**; a "parte humana" fica no `pyproject.toml` (diretas de
runtime, grupo `dev`, extra `prod`, `package = false`) e o `uv.lock` trava o grafo completo.
Comandos em "Comandos Comuns". Como os dois se dividem, o que é direto e o que é transitivo:
`docs/referencia/dependencias-e-cache.md`.

> ⚠️ **Não regredir:** o `uv.lock` nunca é editado à mão, e o `pyproject.toml` e o `uv.lock`
> vão sempre no mesmo commit.

**Quarentena de 7 dias:** `[tool.uv] exclude-newer = "7 days"` (lock só com versões de 7+ dias).
Exceções e prazos: `docs/referencia/dependencias-e-cache.md`.
