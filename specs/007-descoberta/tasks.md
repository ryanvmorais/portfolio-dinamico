---
feature: Descoberta da demo pelos buscadores e pelas redes sociais
status: concluído
date: 2026-11-16
related:
  - 004-correcoes-de-interface
  - 005-modo-demonstracao
  - 006-hospedagem
origin: nova feature
---

# Tarefas — Descoberta da demo pelos buscadores e pelas redes sociais

As etapas 1 a 5 vão num PR. Definir `URL_PUBLICA` na plataforma da demo e
enviar o sitemap aos buscadores acontecem depois do deploy, fora do repositório.

## Etapa 1 — `URL_PUBLICA` no `settings.py`

- [x] `portfolio/settings.py`: `_ler_url_publica(valor: str) -> str` com
  `urlsplit` (esquema `http`/`https`, `netloc` não vazio, caminho vazio ou `/`,
  sem query nem fragmento; sem a barra final; `ValueError` com a chave e um
  exemplo), docstring e o porquê de falhar na subida. — RF-01, ADR-04
- [x] `portfolio/settings.py`: `URL_PUBLICA = _ler_url_publica(...)` depois de
  `URL_REPOSITORIO`; a docstring do módulo cita `URL_PUBLICA` entre as variáveis
  do `.env`, e o comentário do `MODO_DEMONSTRACAO` cita o sentido novo. — RF-01,
  RNF-04
- [x] `app_portfolio/tests.py`: `_carregar_settings` passa a limpar
  `URL_PUBLICA`. — RF-10
- [x] `app_portfolio/test_descoberta.py` (novo, com docstring de módulo):
  `URL_PUBLICA` sem barra, com barra, vazia e os quatro inválidos (sem esquema,
  `ftp://`, com caminho, com query). — RF-01, RF-10
- [x] `pyproject.toml`: `app_portfolio.test_descoberta` no override de mypy da
  suíte. — RF-10
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 204 passed; ruff, black e mypy verdes.

## Etapa 2 — Imagens

- [x] `git mv assets/django-fullstack-portfolio-social-preview.png
  static/img/portfolio-django-divulgacao.png`. — RF-04, ADR-05
- [x] `static/icons/apple-touch-icon.png`: 180 × 180, RGB, reduzido do
  `favicon.webp` com Pillow (`Image.LANCZOS`), por comando avulso, sem script
  versionado. — RF-05, ADR-06
- [x] `app_portfolio/test_descoberta.py`: a imagem de divulgação tem 1280 × 640 e
  o ícone 180 × 180 sem canal alfa. — RF-04, RF-05, RF-10
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 206 passed; ruff, black e mypy verdes.

## Etapa 3 — Metadados do `<head>`

- [x] `app_portfolio/descoberta.py` (novo): docstring de módulo, constantes
  `TITULO_DEMONSTRACAO`, `DESCRICAO_DEMONSTRACAO`, `IMAGEM_DEMONSTRACAO`,
  `LARGURA_IMAGEM_DEMONSTRACAO`, `ALTURA_IMAGEM_DEMONSTRACAO` e
  `ALT_IMAGEM_DEMONSTRACAO`. — RF-03, RF-04
- [x] `app_portfolio/descoberta.py`: `montar_metadados(request, perfil)` com os
  casos demo, perfil com foto e perfil sem foto; endereço da imagem por
  `URL_PUBLICA` ou `build_absolute_uri`; `url_canonica` só de `URL_PUBLICA`. —
  RF-02, RF-03, RF-04, RF-09, RNF-03, ADR-03
- [x] `app_portfolio/views.py`: a `home` põe `metadados` no contexto. — RF-02,
  RF-03, RF-04
- [x] `templates/base.html`: `<head>` com `metadados` (título, description,
  canonical e `og:url` sob `{% if %}`, `og:*`, `og:image` com dimensões e alt
  quando houver, `twitter:card`) e o `apple-touch-icon`; comentários em `{# #}`.
  — RF-02, RF-03, RF-04, RF-05
- [x] `app_portfolio/test_descoberta.py`: `montar_metadados` direto
  (`RequestFactory`, `Perfil` em memória) nos três casos, com e sem
  `URL_PUBLICA`, e `Host` forjado fora da `url_canonica`. — RF-02, RF-03, RF-04,
  RF-09, RNF-03, RF-10
- [x] `app_portfolio/test_descoberta.py`: GET na home (canonical sem a query
  string, `og:url`, `twitter:card`, `apple-touch-icon`, textos da demo) e uma 404
  sem canonical. — RF-02, RF-03, RF-05, RF-10
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 219 passed; ruff, black e mypy verdes.

## Etapa 4 — `robots.txt`, `sitemap.xml` e `security.txt`

- [x] `app_portfolio/descoberta.py`: `robots_txt`, `sitemap_xml` (`escape` na
  `<loc>`; `Http404` sem `URL_PUBLICA`) e `security_txt` (`Http404` sem o modo;
  `Contact:` e `Policy:` de `URL_REPOSITORIO`; `Canonical:` só com
  `URL_PUBLICA`), com `require_safe` e `cache_control(public=True,
  max_age=86400)`, e a constante `EXPIRES_SECURITY_TXT`. — RF-06, RF-07, RF-08,
  ADR-01, ADR-02, ADR-07
- [x] `app_portfolio/urls.py`: rotas `robots.txt`, `sitemap.xml` e
  `.well-known/security.txt`; docstring do módulo atualizada. — RF-06, RF-07,
  RF-08
- [x] `app_portfolio/test_descoberta.py`: cada rota com e sem a configuração
  (status, `Content-Type`, corpo); `ADMIN_URL` trocada fora do `robots.txt`;
  sitemap analisado com `ElementTree`, uma `<loc>` igual ao canonical da home;
  `security.txt` com os campos, `Contact:` em `https://` e um único `Expires`. —
  RF-06, RF-07, RF-08, RNF-03, RF-10
- [x] `app_portfolio/test_descoberta.py`: `EXPIRES_SECURITY_TXT` entre 30 e 366
  dias à frente da data do teste. — RF-08, ADR-07, RF-10
- [x] `DEBUG=False uv run python manage.py check --deploy` sem aviso novo. —
  RNF-02 — "System check identified no issues", com `URL_PUBLICA` definida.
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 230 passed; ruff, black e mypy verdes.

## Etapa 5 — Documentação

- [x] `.env.example`: `URL_PUBLICA` com placeholder e comentário; o comentário do
  `MODO_DEMONSTRACAO` cita os metadados e o `security.txt`. — RNF-04
- [x] `CLAUDE.md`: `URL_PUBLICA` na tabela de variáveis, o sentido novo do
  `MODO_DEMONSTRACAO`, e na árvore `descoberta.py`, `test_descoberta.py`,
  `static/img/` e o `assets/` sem a prévia social. — RNF-04
- [x] `README.md` e `README.en.md`: `URL_PUBLICA` e o sentido novo do
  `MODO_DEMONSTRACAO` na mesma seção, nos dois idiomas; `uv run pytest
  app_portfolio/test_readme_en.py` verde. — RNF-04
- [x] `docs/referencia/configuracoes.md`: `URL_PUBLICA`, a validação na subida e
  os arquivos de descoberta. — RNF-04
- [x] `specs/README.md`: linha da 007 no índice; os três arquivos da spec com
  `status: concluído`. —
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 230 passed (193 antes da spec); ruff, black e mypy verdes.
