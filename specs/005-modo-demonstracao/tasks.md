---
feature: Modo demonstração do formulário de contato
status: concluído
date: 2026-11-16
related:
  - 002-formulario-contato
  - 004-correcoes-de-interface
origin: nova feature
---

# Tasks — Modo demonstração do formulário de contato

O portão de qualidade de cada etapa é, a partir da raiz:

```bash
uv run ruff check --fix .
uv run black .
uv run mypy app_portfolio portfolio
uv run pytest
```

## Etapa 1 — Configuração

- [x] `portfolio/settings.py`: `MODO_DEMONSTRACAO` lido do `.env` como o
      `DEBUG`, com comentário do efeito e do padrão. — RF-01, ADR-01
- [x] `portfolio/settings.py`: constante `URL_REPOSITORIO`. — RF-04, RF-05, ADR-04
- [x] `portfolio/settings.py` (bloco de e-mail): com `DEBUG` e `EMAIL_USER`
      vazio, backend de console e `EMAIL_HOST_USER = "contato@example.com"`,
      antes do `DEFAULT_FROM_EMAIL`. — RF-07, ADR-06
- [x] `app_portfolio/tests.py`: testes da leitura da chave (ausente, `True`,
      `true`, outro valor) e do backend (console só com `DEBUG=True` e
      `EMAIL_USER` vazio), por `importlib.reload` com o ambiente e o
      `load_dotenv` controlados. — RF-01, RF-07, RF-08
- [x] Portão de qualidade. — 138 passed; ruff/black/mypy verdes

## Etapa 2 — View

- [x] `app_portfolio/views.py`: constantes `MENSAGEM_DEMONSTRACAO` e
      `TEXTO_LINK_DEMONSTRACAO`. — RF-05, ADR-03
- [x] `app_portfolio/views.py`: corte do modo depois de `form.is_valid()` e
      antes do `cache.add()`; AJAX responde 200 com `status`, `message` e
      `link`; POST comum usa `messages.info(..., extra_tags="demo")` e
      `redirect`. Comentário do porquê e docstrings da `home` e do módulo
      atualizadas. — RF-02, RF-03, ADR-02, ADR-03
- [x] `app_portfolio/views.py`: `modo_demonstracao` e `url_repositorio` no
      contexto. — RF-04
- [x] `app_portfolio/tests.py`: grupo `TestModoDemonstracao` (AJAX válido,
      POST comum válido, honeypot, inválido, dois envios seguidos, modo
      desligado sem mudança). — RF-02, RF-03, RF-06, RF-08
- [x] Portão de qualidade. — 144 passed; ruff/black/mypy verdes

## Etapa 3 — Interface

- [x] `templates/home.html`: `<p class="contact__aviso">` com o ícone SVG
      inline e o link, dentro de `{% if modo_demonstracao %}`, antes do
      primeiro `.form__group`. — RF-04, RNF-01
- [x] `templates/base.html`: classe por `message.level_tag` e link "Clone ou
      baixe o código no GitHub" quando `"demo"` está em `message.extra_tags`. — RF-05, ADR-03
- [x] `static/css/styles.css`: `.contact__aviso` (com o link e o ícone) e
      `.notification--info` (com o link sublinhado), editando só o trecho. — RF-04, RF-05, RNF-02
- [x] `static/js/main.js`: `mostrarNotificacao()` aceita `link` e não some
      sozinha com ele; ramo `status === 'demo'` que mostra o aviso informativo
      e limpa o formulário; link por `createElement`, sem `innerHTML`. — RF-05, RNF-01, ADR-03, ADR-05
- [x] `app_portfolio/test_interface.py`: aviso fixo presente e ausente, aviso
      `info` com link depois do POST comum, ramo `demo` do `main.js` e as
      regras novas do CSS. — RF-04, RF-05, RF-08
- [x] Conferência no Chrome a 390 e 1280 px com o modo ligado: contraste dos
      dois avisos (AA), Tab até o link e o botão de fechar, aviso anunciado pelo
      leitor de tela, CSP sem bloqueio no console. — RNF-01, RNF-02
- [x] `specs/005-modo-demonstracao/`: capturas em WebP da tela real (390 e
      1280 px, antes e depois do envio). — RF-04, RF-05
- [x] Portão de qualidade. — 157 passed; ruff/black/mypy verdes

## Etapa 4 — Documentação

- [x] `.env.example` (seção 3): `MODO_DEMONSTRACAO=False`, com o efeito de cada
      valor e a nota do console em desenvolvimento. — RNF-03, RF-07
- [x] `README.md` e `README.en.md`, no mesmo commit: a chave e o console em
      desenvolvimento, nas mesmas seções. — RNF-03
- [x] `CLAUDE.md`: linha da chave na tabela de variáveis e o passo do modo no
      fluxo do formulário de contato. — RNF-03
- [x] `docs/referencia/configuracoes.md`: o modo e o console no item de
      e-mail. — RNF-03
- [x] `specs/README.md`: linha 005 no índice. — RNF-03
- [x] Status `concluído` nos três arquivos da spec, com `## Desvios` e
      `## Notas de implementação` no `design.md` se houver o que registrar.
- [x] Portão de qualidade. — 158 passed; ruff/black/mypy verdes
