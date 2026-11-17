---
feature: Configuração e postura de segurança (settings, CSP, admin, deploy)
status: concluído
date: 2026-09-11
related:
  - 002-formulario-contato
origin: engenharia reversa do código existente (portfolio/settings.py)
---

# Tasks — Configuração e Segurança

## Etapa 0 — Estado original (antes da modernização de 2026-09-11)

- [x] Validação de `SECRET_KEY` obrigatória (`ValueError` no import). — RF-01
- [x] `DEBUG` seguro por padrão (`False` se ausente). — RF-02
- [x] `ALLOWED_HOSTS` diferenciado por `DEBUG`. — RF-03
- [x] Hardening condicional (`SECURE_SSL_REDIRECT`, HSTS, cookies) só com
      `DEBUG=False`. — RF-04
- [x] CSP via `django-csp` (com `'unsafe-inline'` em `script-src`, corrigido
      na Etapa 1). — RF-05
- [x] URL do Admin ofuscada via `.env`. — RF-06

## Etapa 1 — Auditoria de segurança e correções (esta sessão)

- [x] Varredura completa em 5 camadas: dependências (`pip-audit`), SAST
      (`semgrep`, 459 regras/85 arquivos, 0 achados), segredos
      (`detect-secrets` + `git ls-files`, 0 achados versionados), configuração
      (`manage.py check --deploy` manual) e revisão OWASP manual.
- [x] `pip-audit` encontrou `PYSEC-2026-3717` em Django 6.0.7 (DoS em
      `django.contrib.gis`, não usado neste projeto). Django atualizado para
      6.0.8 em `pyproject.toml` mesmo assim, por higiene de versão. — RF-07
- [x] `CSP_SCRIPT_SRC` removeu `'unsafe-inline'` (nenhum script inline nos
      templates). — RF-05
- [x] Portão de qualidade após as correções. — `pytest` verde (6 testes
      originais, antes da expansão da suíte na spec 002)

## Etapa 2 — Modernização de infraestrutura (esta sessão)

- [x] Migração de `pip` + `requirements/*.txt` para `uv` (`pyproject.toml` +
      `uv.lock`). Não é um requisito funcional desta spec, mas sustenta o
      `pip-audit` reproduzível (`uv run pip-audit`) e o `mypy`/`ruff`/`black`.
- [x] `.github/dependabot.yml` criado (ecossistemas `uv` + `github-actions`,
      `weekly`/`monday`, `open-pull-requests-limit: 5`) — cobre a varredura
      contínua de dependências que o `pip-audit` manual não substitui.
- [x] `.github/workflows/ci.yml` criado com job `seguranca`
      (`pip-audit` + `manage.py check --deploy`), fecha a lacuna da versão
      inicial desta spec (o CI não automatizava a checagem de deploy). — RF-08
- [x] Portão de qualidade completo. — `uv run ruff check .`,
      `uv run black --check .`, `uv run mypy app_portfolio portfolio`,
      `uv run pytest` verdes.

## Etapa 3 — Documentação (esta sessão)

- [x] Esta spec (`003-configuracao-seguranca/`) escrita por engenharia
      reversa, documentando tanto o estado original quanto as correções da
      auditoria. — origem
- [x] `docs/stack.md` documenta `django-csp`, `whitenoise`,
      `python-dotenv`, `certifi` e as ferramentas de qualidade
      (`ruff`/`black`/`mypy`/`pytest`/`pip-audit`).

## Etapa 4 — Caminho do Admin normalizado (2026-11-16)

- [x] `portfolio/settings.py`: `ADMIN_URL_PATH` sem as barras sobrando, com
      uma barra no fim, e `admin/` quando a variável vem vazia. — RF-06, ADR-03
- [x] `app_portfolio/tests.py`: `TestCaminhoDoAdmin` (ausente, vazia, só
      barras, sem barra, com barra no início, com espaços) e a rota do painel
      no caminho configurado; `_carregar_settings` passa a limpar o
      `ADMIN_URL`. — RF-06
- [x] `.env.example`, `CLAUDE.md` e `docs/referencia/configuracoes.md`:
      vazio vale `admin/`, e as barras são opcionais. — RF-06
- [x] Portão de qualidade. — `uv run ruff check .`, `uv run black --check .`,
      `uv run mypy .`, `uv run pytest` verdes (239 testes).

## Adendo (2026-11-17): CSP sem estilo inline

> Status do adendo: concluído (2026-11-17). Quebra os RF-09 a RF-11 e os ADR-05 e ADR-06 do adendo. O
> texto acima fica como está; as etapas continuam a numeração.

## Etapa 5 — Honeypot pela folha de estilo e `style-src` fechado

- [x] `static/css/styles.css`: `.contact__honeypot { display: none; }` junto das regras
      do formulário de contato. — RF-10, ADR-05
- [x] `templates/home.html`: a `<div>` do honeypot troca o `style="display:none;"` pela
      classe `contact__honeypot`, e o comentário do bloco diz que a classe o esconde.
      — RF-10, ADR-05
- [x] `portfolio/settings.py`: `"style-src": [SELF]`, o comentário da CSP sem a
      exceção do honeypot e o `UNSAFE_INLINE` fora do import. — RF-09, ADR-05
- [x] `app_portfolio/tests.py`: o `test_home_envia_a_csp` espera `style-src` igual a
      `["'self'"]`. — RF-11
- [x] `app_portfolio/test_estilo_inline.py` (novo): nenhum template com `style=` nem
      `<style>` (um caso por template, com arquivo e linha na falha); a regra
      `.contact__honeypot` com `display: none` no `styles.css`; a home renderizada com
      o campo `honeypot` dentro do elemento com a classe e sem `style=` no HTML.
      — RF-11, ADR-06
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
      `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 331 passed;
      ruff/black/mypy verdes. Contra o código anterior, o `test_estilo_inline.py` falha
      em 6 casos.

## Etapa 6 — Conferência no navegador

- [x] Servidor de desenvolvimento com o `DIRETORIO_DADOS` numa pasta temporária,
      `migrate`, `semear_dados_demo` e um superusuário de teste. — RF-09
- [x] Home no Chrome, com e sem perfil e com o `MODO_DEMONSTRACAO` ligado e desligado:
      nenhum evento `securitypolicyviolation` nem erro de CSP no console, e a página
      igual à de antes. — RF-09 — 4 combinações sem violação e sem `[style]` no DOM; o
      controle (um `style=` injetado) gerou a violação `style-src-attr` esperada.
- [x] Admin no Chrome: login, lista de projetos, edição de um projeto com imagem e uma
      ação em lote, sem violação de CSP e com as telas iguais às de antes. — RF-09 —
      login, índice, listas, inclusão, edição (upload e seletor de tecnologias) e a
      confirmação da exclusão em lote sem violação nem erro no console.
- [x] Teclado e leitor de tela: o Tab passa do último campo visível do formulário ao
      botão de envio sem parar no honeypot, e a árvore de acessibilidade do Chrome não
      tem o campo. — RF-10 — Tab de `mensagem` para o botão de envio; o campo fora da
      árvore de acessibilidade.
- [x] Pasta temporária, servidor e navegador da conferência encerrados.

## Etapa 7 — Documentação e fechamento

- [x] `docs/referencia/configuracoes.md` e `docs/stack.md`: `style-src 'self'`, sem
      `'unsafe-inline'`, e o honeypot escondido pela classe. — RF-09, RF-10
- [x] `specs/README.md`: a nota "CSP e scripts/estilos inline" passa a valer para
      estilo, e a linha do índice da spec 003 volta a `concluído`. — RF-09
- [x] `CLAUDE.md`: o aviso da CSP cobre `style=` e `<style>` (`style-src`), e a árvore
      ganha o `test_estilo_inline.py`. — RF-09, RF-11
- [x] Spec 003: status do adendo `concluído` nos três arquivos, frontmatter de volta a
      `concluído`, `### Desvios do adendo` e `### Notas de implementação do adendo` no
      `design.md`, se houver.
- [x] Portão de qualidade: `uv run ruff check .`, `uv run black --check .`,
      `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 331 passed;
      ruff/black/mypy verdes.
