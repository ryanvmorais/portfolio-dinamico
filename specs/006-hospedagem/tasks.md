---
feature: Hospedagem da demo na Railway
status: em andamento
date: 2026-11-16
related:
  - 002-formulario-contato
  - 003-configuracao-seguranca
  - 005-modo-demonstracao
origin: nova feature
---

# Tarefas — Hospedagem da demo na Railway

As etapas 1 a 4 vão num PR. A etapa 5 vai num PR próprio, depois de o deploy da
`main` responder pelo domínio próprio (RNF-05).

## Etapa 1 — Configuração de produção no `settings.py`

- [x] `portfolio/settings.py`: `DIRETORIO_DADOS` (vazio ou ausente = `BASE_DIR`;
  caminho relativo resolvido a partir do `BASE_DIR`), com comentário do porquê. —
  RF-05, ADR-05
- [x] `portfolio/settings.py`: `DATABASES`, `MEDIA_ROOT` e `CACHES` a partir de
  `DIRETORIO_DADOS`; os comentários de cada um citam a pasta nova. — RF-05, RNF-03
- [x] `portfolio/settings.py`: `ALLOWED_HOSTS` sem espaços e sem item vazio; o
  comentário diz que a lista vazia recusa todo host. — RF-04
- [x] `portfolio/settings.py`: `SECURE_PROXY_SSL_HEADER` no bloco `if not DEBUG:`,
  com o comentário do proxy e do caso sem proxy. — RF-02, ADR-03
- [x] `portfolio/settings.py`: `LOGGING` no bloco `if not DEBUG:` (raiz em WARNING
  no `StreamHandler`, `django.request` em ERROR). — RF-07, ADR-07
- [x] `portfolio/settings.py`: docstring do módulo cita `DIRETORIO_DADOS` entre as
  variáveis do `.env`. — RNF-05
- [x] `app_portfolio/tests.py`: `_carregar_settings` passa a limpar
  `ALLOWED_HOSTS` e `DIRETORIO_DADOS`. — RF-08
- [x] `app_portfolio/tests.py`: testes de leitura de `ALLOWED_HOSTS` (espaços,
  vírgula no fim, vazio) e de `DIRETORIO_DADOS` (ausente, absoluto, relativo: banco,
  mídia e cache). — RF-04, RF-05, RF-08
- [x] `app_portfolio/tests.py`: `SECURE_PROXY_SSL_HEADER` e `LOGGING` presentes
  com `DEBUG=False` e ausentes com `DEBUG=True`; nível do `django.request` e
  handler da raiz. — RF-02, RF-07, RF-08
- [x] `app_portfolio/tests.py`: GET com `X-Forwarded-Proto: https` (200, cookie
  `csrftoken` com `secure`) e sem ele (301), com a fixture `settings` ligando o
  redirect, os cookies seguros e o cabeçalho do proxy. — RF-02, RF-08
- [x] `app_portfolio/tests.py`: POST com `Client(enforce_csrf_checks=True)`, token
  do cookie e `Origin` do próprio host passa pelo CSRF (formulário inválido, 400);
  com `Origin` de outro site, 403. — RF-03, ADR-04, RF-08
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 178 passed;
  ruff, black e mypy verdes.

## Etapa 2 — Mídia servida em produção

- [x] `app_portfolio/views.py`: view `servir_midia` (`require_safe`,
  `cache_control(public=True, max_age=86400)`, `serve` com o `MEDIA_ROOT` lido a
  cada pedido), com docstring e o porquê do `serve`. — RF-06, ADR-06
- [x] `portfolio/urls.py`: rota `MEDIA_URL + <path:caminho>` para a `servir_midia`,
  no lugar do `static()` dentro do `if settings.DEBUG:`; docstring do módulo e
  comentário da seção atualizados. — RF-06
- [x] `app_portfolio/tests.py`: com `MEDIA_ROOT` no `tmp_path`, arquivo `.webp`
  (200, `Content-Type`, `nosniff`, `Cache-Control`), inexistente, pasta e `../`
  (404) e POST (405). — RF-06, RF-08
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 183 passed;
  ruff, black e mypy verdes.

## Etapa 3 — Receita de build

- [x] `railpack.json` (novo): build com `uv sync --locked --no-dev --extra prod` e
  `collectstatic --noinput`; start com `migrate --noinput && gunicorn
  portfolio.wsgi:application --bind 0.0.0.0:${PORT:-8000}`. — RF-01, ADR-01, ADR-02
- [x] `app_portfolio/tests.py`: o `railpack.json` existe, é JSON válido e traz
  `--locked`, `--extra prod`, `collectstatic`, `migrate` antes de `gunicorn` e
  `${PORT:-8000}`. — RF-01, RF-08
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`, `uv lock --check` e
  `DEBUG=False ALLOWED_HOSTS=exemplo.com uv run python manage.py check --deploy`
  sem aviso novo. — RNF-02. Resultado: 185 passed; ruff, black e mypy verdes; lock
  conferido; `check --deploy` sem aviso (o mesmo resultado da `main`).

## Etapa 4 — Documentação

- [x] `.env.example`: `DIRETORIO_DADOS` comentado, com o padrão e o uso com volume;
  a linha de `ALLOWED_HOSTS` diz que espaços são aceitos. — RNF-05
- [x] `docs/referencia/configuracoes.md`: `DIRETORIO_DADOS`, `SECURE_PROXY_SSL_HEADER`,
  `LOGGING`, mídia servida pelo Django; o parágrafo do banco deixa de falar em
  PostgreSQL em produção. — RNF-05, ADR-03, ADR-06, ADR-07
- [x] `docs/referencia/dependencias-e-cache.md`, "Cache do rate limit": atrás de
  proxy, `REMOTE_ADDR` é o IP do proxy e todo visitante divide a mesma chave; a
  demo usa o modo demonstração, que pula o rate limit. — RNF-05, decisão resolvida 3
- [x] `docs/stack.md`: gunicorn, Railway e Railpack (o que fazem, por que, o que
  estudar). — RNF-05, ADR-01
- [x] `README.md` e `README.en.md` (mesmo PR, mesmas seções): o item "Ambiente de
  Produção Real" cita o `railpack.json` e o `DIRETORIO_DADOS`. — RNF-05
- [x] `CLAUDE.md`: `DIRETORIO_DADOS` na tabela de variáveis, `railpack.json` na
  estrutura, mídia servida pela `servir_midia`. — RNF-05
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest` (inclui o
  `test_readme_en.py` e o `test_impessoalidade.py`). — 185 passed; ruff, black e mypy verdes.

## Etapa 5 — Link da demo (PR próprio, depois do deploy)

- [ ] Com a demo respondendo em `https://portfolio-dinamico.ryanmorais.com.br` com o
  conteúdo cadastrado e o modo demonstração ligado: link da demo no `README.md` e
  no `README.en.md`. — RNF-05
- [ ] `specs/README.md`: linha da 006 com `concluído`; os três arquivos da spec com
  `status: concluído`. —
- [ ] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. —
