---
feature: Redesenho da home para quem avalia o portfólio
status: concluído
date: 2026-11-17
related:
  - 001-vitrine-portfolio
  - 004-correcoes-de-interface
  - 007-descoberta
origin: nova feature
---

# Tarefas — Redesenho da home para quem avalia o portfólio

As etapas 1 a 7 vão num PR. A ordem mantém a suíte verde a cada etapa: os
campos novos entram primeiro, a página deixa de usar os antigos, e só então eles
saem. Preencher os campos novos nos dados de um deploy existente acontece no
Admin, depois do deploy.

## Etapa 1 — Campos novos e conversão dos dados

- [x] `app_portfolio/models.py`: `NivelHabilidade` (`TextChoices`, três valores
  na ordem de exibição) e, em `Habilidade`, `nivel` e `tecnologia`
  (`ForeignKey` opcional, `SET_NULL`, `related_name="habilidades"`), com
  `help_text`. — RF-11, RF-12, ADR-01, ADR-02
- [x] `app_portfolio/models.py`: em `Projeto`, `link_online` e `problema`,
  `papel`, `decisao_tecnica`, `resultado` (`TextField(blank=True,
  max_length=600)`, com `help_text`), e a propriedade `tem_estudo_de_caso`. — 248 passed; ruff/black/mypy verdes; `makemigrations --check` sem mudança
  RF-09, RF-10, ADR-05
- [x] `app_portfolio/migrations/0024_*.py`: gerada pelo `makemigrations`, só com
  os campos novos. — RF-20, ADR-03
- [x] `app_portfolio/migrations/0025_converter_habilidades.py`: `RunPython` com
  `nivel_pelo_progresso(progresso: int) -> str` (80+, 50 a 79, abaixo de 50) e
  a ligação pela tecnologia de mesmo nome (`nome__iexact`, a primeira por
  `ordem`); o caminho de volta grava 90, 65 e 30; docstrings. — RF-20, ADR-03
- [x] `app_portfolio/admin.py`: `ProjetoAdmin` com `link_online` no grupo de
  links e o grupo recolhível "Estudo de caso"; `HabilidadeInline` com `nivel` e
  `tecnologia` (`autocomplete_fields`). — RF-19
- [x] `app_portfolio/test_redesenho.py` (novo, com docstring de módulo):
  `nivel_pelo_progresso` nas bordas (0, 49, 50, 79, 80, 100);
  `tem_estudo_de_caso` com nenhum, um e quatro campos. — RF-10, RF-20, RF-23
- [x] `pyproject.toml`: `app_portfolio.test_redesenho` no override de mypy da
  suíte. — RF-23
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 248 passed; ruff/black/mypy verdes; `makemigrations --check` sem mudança

## Etapa 2 — Marca gerada das iniciais

- [x] `app_portfolio/marca.py` (novo): `calcular_iniciais`,
  `montar_favicon_svg` (iniciais escapadas), `gerar_icone_png` (Pillow, Inter
  ExtraBold, 180 × 180 RGB, `lru_cache`) e as views `favicon_svg` e
  `icone_tela_inicial` (200 com tipo e `Cache-Control: public, max-age=86400`;
  sem perfil, 302 para os arquivos de `static/icons/`), com docstrings. — RF-16,
  RF-17, RF-18, ADR-09
- [x] `app_portfolio/urls.py`: rotas `favicon.svg` e `apple-touch-icon.png`. —
  RF-17, RF-18
- [x] `app_portfolio/views.py`: `iniciais` no contexto da `home`. — RF-16
- [x] `templates/base.html`: `<link rel="icon" type="image/svg+xml">` com
  `?v={{ iniciais }}` só com perfil, antes do `favicon.webp`, que fica; o
  `apple-touch-icon` aponta para a rota nova com `?v=`; comentários `{# #}`
  com o porquê. — RF-17, RF-18
- [x] `app_portfolio/test_redesenho.py`: iniciais (acento, uma palavra, palavra
  que não começa por letra, vazio, `None`); SVG com menos de 2 KiB e texto
  escapado; PNG 180 × 180 RGB; rotas com e sem perfil; o `?v=` muda com o
  nome. — RF-16, RF-17, RF-18, RF-23
- [x] `app_portfolio/test_descoberta.py`: o teste do `apple-touch-icon`
  declarado passa a esperar a rota nova. — RF-18
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 267 passed; ruff/black/mypy verdes

## Etapa 3 — View e templates

- [x] `app_portfolio/views.py`: `agrupar_habilidades(categorias)` com docstring
  e tipos; `Prefetch` com `select_related("tecnologia")` e
  `annotate(qtd_projetos=Count("tecnologia__projeto", distinct=True))`;
  `total_projetos`; saem `estatisticas` e `tech_icons` do contexto e da
  docstring. — RF-05, RF-11, RF-12, RF-14
- [x] `templates/home.html`, hero: selo, `<h1>` só com o nome, cargo e
  `bio_curta`, "Ver projetos", ícones com `{% if %}` por campo, "ou entre em
  contato", números com `pluralize` e `{% if %}`, foto com `fetchpriority` e
  reserva; saem saudação, bloco de código, estatísticas e "Explorar". — RF-01 a
  RF-05, RNF-04
- [x] `templates/home.html`: seções na ordem Hero, Projetos, Sobre, Habilidades,
  Contato, com os rótulos novos; selo do Sobre por `anos_experiencia`. — RF-05,
  RF-07, RF-08
- [x] `templates/home.html`, projetos: `data-tecnologias`, `<details>` "Como foi
  feito" com os campos preenchidos, "Ver online" e "Código" com `{% if %}` e
  nome acessível; a linha de estado do filtro (`hidden`, `tabindex="-1"`, botão
  "Limpar filtro"). — RF-09, RF-10, RF-13
- [x] `templates/home.html`, habilidades: blocos por categoria, `<h4>` por
  nível, `<button class="chip">` com `data-tecnologia`, `data-nome` e
  `aria-pressed` quando há projeto, `<span class="chip">` sem; sai a faixa de
  ícones. — RF-11, RF-12, RF-14
- [x] `templates/base.html`: logo com monograma no menu e no rodapé
  (`aria-hidden` no monograma, `aria-label` começando pelo nome); menu e "Links
  rápidos" na ordem nova; rodapé com `bio_curta` e só GitHub e LinkedIn do
  perfil, com `{% if %}`; a linha de direitos autorais segue na largura toda. — 298 passed; ruff/black/mypy verdes
  RF-07, RF-15, RF-16
- [x] `app_portfolio/test_redesenho.py`: hero, ordem, rótulos, cartão, chips,
  rodapé e logo com o cliente do Django, com cada campo vazio e preenchido; a
  home 200 com todo opcional vazio. — RF-01 a RF-16, RF-22, RF-23
- [x] `app_portfolio/test_interface.py`: saem os testes do bloco de código, das
  estatísticas, das barras de progresso, das seis redes fixas e do perfil sem
  campos de rede; os que liam o hero e o rodapé passam a ler a marcação
  nova. — RF-22
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 298 passed; ruff/black/mypy verdes

## Etapa 4 — CSS e JavaScript

- [x] `static/css/styles.css` (edição por trecho, 4 espaços e aspas simples):
  saem o bloco de código, as estatísticas, o "Explorar", as barras, a faixa de
  ícones, os colchetes do logo e a altura de tela do hero. — RF-01, RF-14,
  ADR-10
- [x] `static/css/styles.css`: hero em duas colunas e em uma até 768 px, selo,
  botões de ícone de 48 px, números, foto (4:5 e redonda), monograma, chips com
  estado `[aria-pressed="true"]`, blocos de área, `<details>` do cartão, linha
  de estado e ações do cartão empilhadas no celular; bordas para alto contraste;
  o bloco `prefers-reduced-motion` segue o último e cobre as transições
  novas. — RF-04, RF-06, RF-11, RNF-02
- [x] `static/js/main.js` (edição por trecho): `filtrarProjetos({ categoria,
  tecnologia })`, `iniciarChips()` com `aria-pressed`, linha de estado, rolagem
  por `comportamentoDeRolagem()` e foco na linha; um filtro por vez; "Limpar
  filtro"; a região `#projects-status` só para a categoria. — RF-13, ADR-06,
  ADR-07, ADR-08
- [x] `app_portfolio/test_interface.py`: saem os testes de altura do hero com
  `svh` e do ícone do PostgreSQL; entram, lidos como texto, o filtro por chip
  (atributos, foco, rolagem), as bordas em `forced-colors` e o movimento
  reduzido ainda por último; o teste de unidades dinâmicas fica só com o
  menu. — RF-13, RF-22, RNF-02, ADR-10
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 304 passed; ruff/black/mypy verdes; `node --check` no main.js

## Etapa 5 — Remoção do que ficou sem uso

- [x] `app_portfolio/models.py`: saem `Habilidade.progresso`,
  `Perfil.mostrar_progresso`, `Tecnologia.icone`, `Tecnologia.mostrar_no_home`,
  `CategoriaHabilidade.icone` e o modelo `Estatistica`. — RF-05, RF-11, ADR-04
- [x] `app_portfolio/migrations/0026_*.py`: gerada pelo `makemigrations`. —
  RF-20, ADR-03
- [x] `app_portfolio/admin.py`: sai o `EstatisticaAdmin`; `TecnologiaAdmin` sem
  `mostrar_no_home`; `PerfilAdmin` sem `mostrar_progresso` e com o texto de
  ajuda de `anos_experiencia`. — RF-05, RF-19
- [x] `app_portfolio/management/commands/semear_dados_demo.py`: habilidades com
  nível e tecnologia, projetos com `link_online` em `https://example.com/…` e
  estudo de caso, `anos_experiencia`, sem estatísticas nem ícones. — RF-21
- [x] Arquivos: saem `static/icons/tech/`, `static/icons/social/` menos
  `github.svg` e `linkedin.svg`, e `static/icons/code.svg`, `server.svg` e
  `cloud.svg`, depois de um `grep` que confirme que nada os usa. — ADR-04
- [x] `app_portfolio/test_redesenho.py`: migração com `MigrationExecutor`
  (`django_db(transaction=True)`) de `0023` até `0026` e de volta, conferindo
  nível, ligação e a ausência de `Estatistica`. — RF-20, RF-23
- [x] `app_portfolio/test_semear_dados_demo.py`: níveis, ligação, `link_online`
  e estudo de caso; nenhuma estatística. — RF-21
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`,
  `uv run python manage.py makemigrations --check --dry-run`. — 309 passed; ruff/black/mypy verdes; `makemigrations --check` sem mudança

## Etapa 6 — Documentação e specs anteriores

- [x] `README.md` e `README.en.md`: funcionalidades e Admin (níveis, estudo de
  caso, versão no ar, marca gerada das iniciais; sem barras nem estatísticas),
  as mesmas seções nos dois. — RNF-05
- [x] `CLAUDE.md`: árvore de arquivos (`marca.py`, `test_redesenho.py`, ícones
  removidos) e a lista de modelos. — RNF-05
- [x] `docs/referencia/arquitetura.md` e
  `docs/referencia/interface-e-acessibilidade.md`: modelos, ordem das seções,
  filtro por chip, marca e as regras da spec 004 que mudaram (hero no celular,
  rodapé). — RNF-05
- [x] `specs/README.md`: notas de manutenção (marca gerada das iniciais; o hero
  sem altura de tela). — RNF-05
- [x] Specs anteriores: `**Superseded by** 008-redesenho-da-home, RF-N.` abaixo
  de 001 RF-06 e RF-07; 004 RF-02, RF-07, RF-14, RF-15 (hero), RF-20 (ícone da
  aba) e RF-11 ("Explorar"); 007 RF-05. — RF-05, RF-11, RF-15, RF-17, RF-18,
  ADR-10
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`. — 309 passed; ruff/black/mypy verdes

## Etapa 7 — Conferência no navegador e fechamento

- [x] Ambiente local com `semear_dados_demo`: capturas a 360, 390, 430 e 1280 px
  comparadas ao protótipo (seção 2.1 do design); axe-core sem violação; Tab
  pelos filtros, chips, "Como foi feito" e "Limpar filtro"; leitor de tela no
  filtro por chip; alto contraste do Windows; resultados em "Notas de
  implementação". — RF-06, RF-13, RNF-02, RNF-03
- [x] Lighthouse local nos limites do `.github/lighthouse/`. — RNF-04
- [x] `design.md`: "Desvios" e "Notas de implementação", se houver. — RF-23
- [x] Status `concluído` nos três arquivos e no índice do `specs/README.md`. —
  RF-23
- [x] Portão de qualidade completo: `uv run ruff check --fix .`,
  `uv run black .`, `uv run mypy app_portfolio portfolio`, `uv run pytest`,
  `uv run pip-audit`, `DEBUG=False uv run python manage.py check --deploy`. —
  309 passed; ruff/black/mypy verdes; pip-audit sem vulnerabilidade conhecida;
  `check --deploy` sem problema; `makemigrations --check` sem mudança

## Adendo (2026-11-17): hero com duas ações e foto maior no celular

> Status do adendo: concluído (2026-11-17). Quebra os RF-24 a RF-27 e os ADR-11 e ADR-12 do adendo.
> O texto acima fica como está; as etapas continuam a numeração.

## Etapa 8 — Hero com duas ações, foto de 160 px e recorte pelo alto

- [x] `templates/home.html`: o `hero__acoes` com "Ver projetos" (`btn--primary`, para
  `#projects`) e "Entre em contato" (`btn--secondary`, para `#contact`); saem a lista
  `hero__links` e o `hero__contato`, e o comentário diz onde os links ficam. — RF-24,
  ADR-11
- [x] `static/css/styles.css`: `object-position: center top` na `.hero__foto`; no
  celular, `.hero__foto-moldura` com `width: 160px` e largura total para os dois
  botões; saem `.hero__links`, `.icone-link`, `.hero__contato` e o `.icone-link` do
  `forced-colors`; comentários com 160 px e as duas ações. — RF-24, RF-25, RF-26,
  ADR-12
- [x] `app_portfolio/models.py`: `help_text` do `Perfil.foto` com o retrato 4:5 e o
  espaço acima da cabeça; `uv run python manage.py makemigrations` gera a `0026`. —
  RF-26
- [x] `app_portfolio/test_redesenho.py` e `app_portfolio/test_interface.py`: as ações e
  a ausência dos links de ícone com os campos preenchidos, os links ainda no Contato e
  no rodapé, a foto de 160 px com recorte pelo alto, o `forced-colors` sem
  `.icone-link` e o `help_text` da foto. — RF-27
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`,
  `uv run python manage.py makemigrations --check`. — 333 passed; ruff/black/mypy
  verdes; `makemigrations --check` sem mudança.

## Etapa 9 — Conferência no navegador

- [x] Ambiente local com `semear_dados_demo` e uma foto 4:5 no perfil, a 390 x 844 e a
  1280 x 800: nome, selo e os dois botões na primeira tela do celular; topo de Projetos
  na primeira tela do desktop; botões com a mesma altura e o rótulo centrado; foto
  redonda sem corte no alto da cabeça. — RF-24, RF-25, RF-26 — 390 x 844: botões até
  640 px, foto de 160 px com `object-position: 50% 0%`; 1280 x 800: Projetos a 617 px;
  botões de 58 px, rótulo centrado, Inter.
- [x] axe-core sem violação e nenhuma violação de CSP na home, nas duas larguras. —
  RF-24, RF-25 — nenhuma violação nas duas larguras.
- [x] Portão da etapa: servidor, navegador e banco temporário encerrados; resultados em
  "Notas de implementação do adendo". — encerrados e apagados.

## Etapa 10 — Documentação e fechamento

- [x] `docs/referencia/interface-e-acessibilidade.md`: hero com duas ações e foto de
  160 px recortada pelo alto. — RF-24, RF-25, RF-26
- [x] `design.md`: "Desvios do adendo" e "Notas de implementação do adendo", se houver.
  — RF-27
- [x] Status do adendo `concluído` nos três arquivos, frontmatter de volta a
  `concluído` e a linha do índice do `specs/README.md`. — RF-27
- [x] Portão de qualidade: `uv run ruff check .`, `uv run black --check .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`,
  `uv run python manage.py makemigrations --check`. — 333 passed;
  ruff/black/mypy verdes; `makemigrations --check` sem mudança.

## Adendo (2026-11-17): telefone do perfil sem uso

> Status do adendo: concluído (2026-11-17). Quebra os RF-28 e RF-29 e o ADR-13 do
> adendo. O texto acima fica como está; as etapas continuam a numeração.

## Etapa 11 — Remoção do telefone

- [x] `app_portfolio/models.py`, `app_portfolio/admin.py` e
  `app_portfolio/management/commands/semear_dados_demo.py`: sai o `telefone`. — RF-28,
  ADR-13
- [x] `uv run python manage.py makemigrations app_portfolio --name remove_perfil_telefone`:
  a migração `0028` com o `RemoveField`. — RF-28, ADR-13
- [x] `app_portfolio/test_redesenho.py`: o `telefone` no teste dos campos antigos e a
  migração de ida e volta da `0027` à `0028`; o `test_semear_dados_demo.py` segue
  verde com o comando sem o campo. — RF-29
- [x] Portão de qualidade: `uv run ruff check --fix .`, `uv run black .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`,
  `uv run python manage.py makemigrations --check`. — 334 passed; ruff/black/mypy
  verdes; `makemigrations --check` sem mudança.

## Etapa 12 — Fechamento

- [x] `design.md`: "Desvios do adendo" e "Notas de implementação do adendo", se houver.
  — RF-29
- [x] Status do adendo `concluído` nos três arquivos, frontmatter de volta a
  `concluído` e a linha do índice do `specs/README.md`. — RF-29
- [x] Portão de qualidade: `uv run ruff check .`, `uv run black --check .`,
  `uv run mypy app_portfolio portfolio`, `uv run pytest`,
  `uv run python manage.py makemigrations --check`. — 334 passed; ruff/black/mypy
  verdes; `makemigrations --check` sem mudança.
