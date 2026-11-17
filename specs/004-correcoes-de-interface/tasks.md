---
feature: Correções da auditoria de interface
status: concluído
date: 2026-10-18
related:
  - 001-vitrine-portfolio
  - 002-formulario-contato
  - 003-configuracao-seguranca
origin: nova feature (auditoria de interface em navegador real)
---

# Tasks — Correções da auditoria de interface

## Etapa 1 — Dados e servidor

- [x] `app_portfolio/views.py`: constantes `MENSAGEM_*`, mesma frase em JSON e em
      `messages`, e avisos nos fluxos HTML (sucesso, limite, inválido, falha). — RF-03, ADR-06
- [x] `portfolio/settings.py`: CSP sem `fonts.googleapis.com` e `fonts.gstatic.com`. — RF-17, ADR-05
- [x] `portfolio/urls.py`: `/favicon.ico` redireciona para o `favicon.webp`, com
      caminho absoluto. — RF-20
- [x] Portão de qualidade. — 13 testes originais verdes, `manage.py check` sem problemas

## Etapa 2 — Folhas de estilo e fontes

- [x] `static/fonts/` e `static/css/fontes.css`: Inter e JetBrains Mono
      hospedadas (variáveis, latin), com as licenças OFL. — RF-17, ADR-05
- [x] `static/css/styles.css` (tokens): `--color-gray-400` em #8393aa; cores dos
      avisos; copyright e texto de exemplo dos campos no token legível. — RF-05, RF-06, ADR-03
- [x] `static/css/styles.css` (hero e menu): texto primeiro, bloco de código fora
      do celular, estatísticas em grade, `svh` e `dvh`. — RF-02, RF-15, ADR-01, ADR-02
- [x] `static/css/styles.css` (componentes): avisos, páginas de erro, botões de
      mesma altura, rodapé alinhado, alvos de toque, `text-wrap`, `:focus-visible`,
      `transition` listada e CSS sem uso removido. — RF-04, RF-06, RF-15, RF-16, RF-18, RF-19, RF-22, RF-23, RF-24, ADR-06, ADR-07
- [x] `static/css/styles.css` (fim do arquivo): bloco de movimento reduzido. — RF-08
- [x] Portão de qualidade. — o diff do `styles.css` ficou em +313 / −69 linhas,
      sem reformatar o resto do arquivo

## Etapa 3 — JavaScript

- [x] `static/js/main.js`: reescrito por funções, com ponto de entrada único; menu
      com `inert`, foco e Esc; filtros com `aria-pressed` e região viva; avisos
      criados com `role`; erro do servidor mostrado; rolagem por
      `comportamentoDeRolagem()`; código sem uso removido. — RF-03, RF-04, RF-06, RF-08, RF-13, RF-22, ADR-02, ADR-06
- [x] Portão de qualidade. — `main.js` sem erro de sintaxe; verificado no Chrome
      (menu, Esc, formulário com 200 e 429)

## Etapa 4 — Templates

- [x] `templates/base.html`: fontes locais e preload, `og:image` absoluta, tipo do
      favicon, `aria-label` do logo, estado do hambúrguer, rodapé com `h2` (redes
      fixas, como antes) e avisos no componente novo. — RF-03, RF-04, RF-11, RF-12, RF-14, RF-17, RF-20
- [x] `templates/home.html`: currículo, foto e link opcionais; nome do link do
      GitHub; capa decorativa; barras com nome; filtros com estado; `autocomplete`;
      contato vindo do perfil. — RF-01, RF-07, RF-09, RF-10, RF-11, RF-13, RF-14, RF-21
- [x] `templates/erro.html`, `404.html`, `403.html` e `500.html`. — RF-19, ADR-10
- [x] Portão de qualidade. — axe-core 4.14.0: 0 violações em 390 e 1280 px; Tab sem
      parada invisível; 0 palavras órfãs

## Etapa 5 — Imagens

- [x] Seis capas de projeto (1280 x 800, WebP q80, 43 a 81 KiB) com nomes de SEO,
      em `media/projetos/`, e o banco local de demonstração criado com elas. — RNF-03, ADR-11
- [x] Retrato do perfil (960 x 1200, 102 KiB) em `media/perfil/` e em
      `static/icons/default_perfil.webp`. — RF-09, ADR-11
- [x] `static/icons/default_projeto.webp` (emblema `</>`, sem texto, 30 KiB; antes
      622 KiB) e `favicon.webp` (do emblema, 256 px, 10 KiB; antes 516 KiB, com a
      marca do Gemini). — RF-20, ADR-11
- [x] `static/icons/tech/postgresql.svg` em azul claro (6,0:1 sobre o chip). — RF-24
- [x] Portão de qualidade. — nenhuma imagem do repositório tem mais a marca do Gemini

## Etapa 6 — Testes e verificação

- [x] `app_portfolio/test_interface.py`: um grupo de testes por requisito (HTML
      renderizado, view, páginas de erro, CSS e JS como texto, arquivos estáticos);
      `pyproject.toml` com o override do mypy para o módulo. — RF-01 a RF-24
- [x] Prova por mutação: 43 correções desfeitas, uma por vez. — 43 de 43 pegas
      (duas sobreviveram na primeira rodada e os testes foram reforçados)
- [x] Verificação no Chrome: hero em 10 tamanhos, contraste, Tab, menu, formulário,
      proporções e as páginas de erro com `DEBUG=False`. — RF-02, RF-03, RF-04, RF-05
- [x] Portão de qualidade completo. — 89 passed (13 originais + 76 novos);
      `ruff`, `black --check` e `mypy` verdes; `manage.py check` sem problemas

## Etapa 7 — Documentação

- [x] Esta spec (`004-correcoes-de-interface/`) e o índice em `specs/README.md`. — origem
- [x] `CLAUDE.md`, `README.md` e `docs/stack.md`: fontes locais, avisos, páginas
      de erro, testes de interface e as regras que não podem
      regredir. — RNF-01
- [x] Portão de qualidade. — todo `RF-NN` e `ADR-NN` citado existe nos
      requisitos e no design

### Medida do hero (Chrome real, altura visível estimada)

| Tela | Visível | Antes (botões / estatísticas) | Depois (botões / estatísticas) |
|---|---|---|---|
| 360 x 640 | 560 | 901 / 1101 | 512 / 626 |
| 390 x 844 | 664 | 901 / 1101 | 492 / 605 |
| 412 x 915 | 760 | 901 / 1101 | 540 / 653 |
| 430 x 932 | 760 | 901 / 1101 | 553 / 641 |
| 480 x 1000 | 840 | 901 / 1101 | 593 / 681 |
| 844 x 390 (deitado) | 340 | 820 / 940 | 400 / 488 |

## Adendo (2026-11-17): menu do celular com redes e currículo

> Status do adendo: concluído (2026-11-17). Quebra os RF-25 a RF-28 e os ADR-12 a
> ADR-14 do adendo. O texto acima fica como está; as etapas continuam a numeração.

## Etapa 8 — Painel abaixo da barra, botão único, véu e redes

- [x] `templates/base.html`: sai o `nav__close`; o `nav__toggle` com os dois ícones
      (`nav__icone-abrir` e `nav__icone-fechar`); o bloco `nav__extras` com os grupos
      "Redes Sociais" e "Currículo" (`<p class="nav__grupo">` e `<ul
      aria-labelledby>`), cada link com o seu `{% if %}`; o `nav__veu` depois do painel.
      — RF-25, RF-26, ADR-12, ADR-13
- [x] `static/css/styles.css`: painel abaixo da barra, em coluna, com `overflow-y: auto`,
      `transform` e sombra só aberto; véu com altura declarada e transição de `opacity` e
      `visibility`; bloco e véu escondidos fora do celular; `.nav__grupo` e `.nav__extra`;
      ícone do botão pelo `aria-expanded`; saem as regras do `.nav__close`. — RF-25,
      RF-26, RF-27, ADR-12, ADR-14
- [x] `static/js/main.js`: o botão alterna abrir e fechar e troca o `aria-label`; saem o
      `navClose` e o ouvinte dele. — RF-25, ADR-12
- [x] `app_portfolio/test_interface.py`: o bloco com cada campo vazio e preenchido, os
      rótulos com a mesma classe, o botão com os dois ícones, sem `nav-close`; o CSS do
      painel, do véu e do bloco; o contraste do bloco; o JavaScript do botão; os testes
      que citavam o `.nav__close`. — RF-28
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
      `uv run mypy app_portfolio portfolio`, `uv run pytest` — 348 passed (eram 333);
      ruff, black e mypy verdes.

## Etapa 9 — Conferência no navegador

- [x] Ambiente local com `semear_dados_demo` e os três campos preenchidos, a 390 x 844 e a
      360 x 640, menu fechado e aberto: barra visível e clicável, véu, X no lugar do
      hambúrguer, bloco no pé do painel, rolagem no celular baixo e nenhum link fora de
      alcance. — RF-25, RF-26
- [x] Teclado e leitor de tela: o foco vai ao primeiro link ao abrir; Esc e X fecham com
      o foco no botão; o botão anuncia "Abrir menu" e "Fechar menu" pela árvore de
      acessibilidade; o toque no véu fecha. — RF-25
- [x] axe-core sem achado e nenhuma violação de CSP, com o menu aberto e fechado; o
      painel desliza por `transform`. — RF-26, RF-27
- [x] Portão da etapa: servidor, navegador e banco temporário encerrados; resultados em
      "Notas de implementação do adendo" — encerrados; axe-core sem achado novo (os dois
      de boas práticas com o menu aberto vêm de antes do adendo), CSP sem violação.

## Etapa 10 — Documentação e fechamento

- [x] `docs/referencia/interface-e-acessibilidade.md`: o menu do celular com o painel
      abaixo da barra, o botão único, o véu e o bloco de redes e currículo. — RF-25,
      RF-26
- [x] `design.md`: "Desvios do adendo" e "Notas de implementação do adendo", se houver.
      — RF-28
- [x] Status do adendo `concluído` nos três arquivos, frontmatter de volta a `concluído`
      e a linha do índice do `specs/README.md`. — RF-28
- [x] Portão de qualidade: `uv run ruff check .`, `uv run black --check .`,
      `uv run mypy app_portfolio portfolio`, `uv run pytest` — 348 passed; ruff, black
      e mypy verdes.
