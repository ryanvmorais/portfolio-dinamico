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

# Design — Correções da auditoria de interface

## 1. Visão geral

Quase tudo é CSS, marcação e JavaScript puro, no estilo que o projeto já tem
(tokens no `:root`, BEM, uma folha `styles.css`). Duas folhas e um punhado de
templates nascem: `fontes.css` (as fontes hospedadas) e as páginas de erro. O
`main.js` foi reescrito por funções com nome em português e um ponto de entrada
único; o comportamento antigo (rolagem, filtros,
revelação ao rolar, envio por `fetch`) foi mantido, e o que mudou é o menu, os
avisos e o tratamento da resposta do servidor.

Dois pontos tocam o servidor: as mensagens da view de contato (a mesma frase em
JSON e em `django.contrib.messages`) e o modelo `Perfil`, que ganha quatro campos
opcionais de rede social.

## 2. Componentes

```
static/css/fontes.css        # novo: @font-face de Inter e JetBrains Mono (latin, variáveis)
static/css/styles.css        # tokens, hero, menu, avisos, erro, toque, movimento reduzido
static/fonts/                # novo: 2 woff2 + licenças OFL
static/js/main.js            # reescrito: menu com inert, filtros com aria-pressed, avisos, formulário
static/icons/                # favicon.webp (do emblema), default_perfil/projeto.webp, postgresql.svg
templates/base.html          # fontes locais, og:image absoluta, nomes acessíveis, títulos do rodapé em h2, avisos
templates/home.html          # currículo, link e capa opcionais; nomes; filtros; contato do perfil
templates/erro.html          # novo: base independente das páginas de erro
templates/{404,403,500}.html # novos: estendem o erro.html
app_portfolio/views.py       # MENSAGEM_* e messages nos fluxos HTML
app_portfolio/test_interface.py   # novo: um grupo de testes por requisito
portfolio/settings.py        # CSP sem Google Fonts
portfolio/urls.py            # /favicon.ico para um arquivo que existe
pyproject.toml               # override do mypy para o novo módulo de teste
```

## 3. Modelo de dados

Sem mudança. O `Perfil` e as migrações ficam como estavam (a última continua
sendo a `0022`).

## 4. Interfaces

Respostas JSON da view `home` (cabeçalho `X-Requested-With: XMLHttpRequest`):

| Situação | Status | `message` |
|---|---|---|
| Enviado | 200 | `MENSAGEM_ENVIADO` ("Mensagem enviada!") |
| Limite de 10 minutos | 429 | `MENSAGEM_LIMITE_ENVIO` |
| Formulário inválido | 400 | `MENSAGEM_DADOS_INVALIDOS` |
| Falha de e-mail | 500 | `MENSAGEM_FALHA_ENVIO` |

O fluxo HTML usa as mesmas constantes em `messages.success` e `messages.error`.
O `main.js` mostra `message` de toda resposta que não seja `ok` com
`status === 'success'`.

## 5. Decisões técnicas (ADRs)

### ADR-01 — Hero: texto primeiro e bloco decorativo fora do celular

- **Decisão:** abaixo de 1024 px o bloco de código passa a vir depois do texto
  (some o `order: -1`); some de vez abaixo de 640 px e em celular deitado; os
  espaços encolhem e as três estatísticas ficam numa linha (grade de 3 colunas);
  `min-height: 100svh`.
- **Alternativas:** (a) só esconder o bloco no celular; (c) manter o bloco no
  celular, depois das estatísticas.
- **Porquê:** a opção (a) ainda deixava as estatísticas fora da tela; a (c) deixava
  o hero com ~960 px, rolagem a mais para um enfeite. A escolhida (b) foi medida em
  10 tamanhos: título e botões cabem em todo celular em pé, e o hero inteiro cabe
  de 390 x 844 para cima.
- **Trade-off:** no celular o visitante não vê o bloco de código; em 360 x 640 as
  estatísticas ficam ~60 px abaixo da tela.

### ADR-02 — Menu do celular: `inert` e altura dinâmica

- **Decisão:** o painel é `inert` enquanto fechado, só no celular (por
  `matchMedia`, mesmo ponto de corte do CSS); ao abrir, o resto da página fica
  inerte, o foco vai ao primeiro link, `aria-expanded` acompanha, e o Esc (ou o
  botão de fechar) devolve o foco ao hambúrguer antes de o painel voltar a ser
  `inert`. O painel usa `100dvh`.
- **Alternativas:** `visibility: hidden` no painel (exigiria acompanhar a
  transição); `display: none` (perde a animação de entrada).
- **Porquê:** `right: -100%` só tira o painel da tela, não do Tab nem do leitor de
  tela. O `inert` resolve os dois e não interfere na transição.
- **Trade-off:** sem JavaScript o painel não abre de qualquer jeito, então o
  `inert` (feito por JavaScript) não muda nada para quem não tem JS.

### ADR-03 — Contraste por token

- **Decisão:** `--color-gray-400` sobe de #64748b para #8393aa (4,67:1 sobre o
  cartão, o pior fundo); `--color-gray-500` fica só como cor de borda.
- **Alternativas:** corrigir cada componente; usar o `--color-gray-300`.
- **Porquê:** 20 dos 22 textos reprovados usavam o mesmo token; um valor novo
  corrige todos e mantém a hierarquia (cinza de apoio abaixo do cinza do texto).
- **Trade-off:** o texto de apoio fica um pouco mais claro e perto do corpo.

### ADR-04 — Redes do rodapé fixas

- **Decisão:** o rodapé continua com as seis redes escritas no `base.html`, iguais
  para todo perfil. Só os títulos viram `h2` (RF-12).
- **Alternativas:** (a) quatro campos opcionais no `Perfil`, com migração, para
  mostrar só as redes preenchidas (foi a primeira versão desta spec); (b) tirar
  as redes que o perfil não tem.
- **Porquê:** o projeto é educativo e o rodapé é um exemplo de layout: quem usa o
  template troca os endereços no HTML. Quatro campos e uma migração por causa de
  links de exemplo pesam mais que o ganho. Decisão do mantenedor (2026-10), depois de ver a
  alternativa (a) pronta.
- **Trade-off:** os links levam à página inicial de cada rede, não a um perfil
  real. O `base.html` avisa isso num comentário.

### ADR-05 — Fontes hospedadas, só latin e variáveis

- **Decisão:** Inter (400 a 700) e JetBrains Mono (400 a 500) em `static/fonts/`,
  um arquivo variável de cada, subconjunto latin, `font-display: swap`; preload
  só da Inter; a CSP perde `fonts.googleapis.com` e `fonts.gstatic.com`.
- **Alternativas:** manter o Google Fonts; pacote npm (exigiria build).
- **Porquê:** sem requisição de terceiros (LGPD), sem CSS externo bloqueando a
  primeira pintura e uma superfície de CSP menor. É o caminho que o blog culinário
  já seguiu.
- **Trade-off:** 80 KB de fontes no repositório e atualização manual.

### ADR-06 — Um componente de aviso para os dois fluxos

- **Decisão:** `.notification` (com `.notifications` como região `role="status"`)
  serve ao aviso criado pelo `main.js` e às mensagens do Django no `base.html`;
  o aviso de erro leva `role="alert"` e fica até ser fechado; o de sucesso some
  em 6 s.
- **Alternativas:** manter o aviso inline do JavaScript e deixar o `.toast` do
  `base.html` sem estilo.
- **Porquê:** o `.toast` nunca teve CSS: no fluxo sem JavaScript o aviso saía como
  texto solto depois do rodapé. Um componente só evita dois visuais para a mesma
  coisa.
- **Trade-off:** o aviso de erro não some sozinho.

### ADR-07 — Alvos de toque só em tela de toque

- **Decisão:** os controles pequenos (filtros, links do rodapé e do contato, ícones
  sociais) chegam a 44 px dentro de `@media (pointer: coarse)`; o menu do celular
  tem 44 px por ser uma tela estreita.
- **Alternativas:** 44 px sempre.
- **Porquê:** com mouse, 44 px em links de rodapé alonga a página sem ganho.
- **Trade-off:** quem usa o computador com tela de toque e `pointer: fine` mantém o
  tamanho compacto (ainda acima dos 24 px da WCAG 2.2).

### ADR-08 — Capas de projeto decorativas

- **Decisão:** `alt=""` na capa do projeto.
- **Alternativas:** um campo `imagem_alt` no modelo.
- **Porquê:** as capas são ilustrações abstratas e o título está ao lado.
- **Trade-off:** se uma capa passar a trazer informação, o campo precisa nascer.

### ADR-09 — Filtros e botão do GitHub continuam em 14 px

- **Decisão:** os chips de filtro e o botão "Ver no GitHub" ficam em `--fs-sm`
  (14 px), mesma família do corpo (16 px).
- **Alternativas:** subir todos a 16 px.
- **Porquê:** são controles secundários e compactos; a medição de proporções só
  os marca pelo tamanho (`fonte_do_corpo`), com a fonte, o centro do rótulo e a
  altura corretos.
- **Trade-off:** a ferramenta continua apontando 11 ocorrências, aceitas.

### ADR-10 — Páginas de erro independentes

- **Decisão:** `erro.html` é um documento completo que não herda o `base.html`;
  `404.html`, `403.html` e `500.html` só preenchem blocos. Sem JavaScript e sem
  contexto.
- **Alternativas:** estender o `base.html`.
- **Porquê:** o `base.html` lê o perfil e tem âncoras `#seção` que, numa página de
  erro, apontam para o lugar errado; o 500 acontece justamente quando algo falhou.
- **Trade-off:** o erro não tem o menu da home.

### ADR-11 — Imagens: nomes de SEO e recortes fixos

- **Decisão:** capas de projeto em 1280 x 800 (16:10, o `aspect-ratio` do cartão),
  foto de perfil em 960 x 1200 (4:5), emblema de reserva em 1280 x 800, favicon
  quadrado de 256 px tirado do emblema (`</>`); todos em WebP qualidade 80 (88 no
  favicon), com nomes como `plataforma-de-ecommerce-loja-virtual-holografica-com-fones-neon.webp`.
  `default_perfil.webp` e `default_projeto.webp` seguem com esse nome, que o
  template referencia.
- **Alternativas:** manter os nomes antigos (`plataforma_de_ecommerce.webp`).
- **Porquê:** o nome do arquivo entra no SEO de imagem; recortar na proporção da
  tela evita que o `object-fit: cover` corte o assunto.
- **Trade-off:** trocar uma imagem pelo admin deixa o arquivo antigo na pasta
  `media/` (o projeto não usa `django-cleanup`).

## 6. Impacto e dependências

- Nenhuma migração: o deploy não precisa de `migrate` por causa desta spec.
- A CSP fica mais estreita; nenhuma outra página carregava fonte externa.
- Sem dependência nova.

## 7. Estratégia de testes

pytest com o cliente do Django. O HTML da home é renderizado com perfis que
variam um campo opcional por vez; o CSS e o JavaScript são lidos como texto e
conferidos por regra (contraste calculado dos tokens, blocos `@media`, marcadores
de comportamento); o e-mail e a mídia seguem isolados como nas specs 001 e 002.
Cada teste foi provado desfazendo a correção (43 mutações, todas pegas). A
verificação em navegador real não entra no pytest.

## Adendo (2026-11-17): menu do celular com redes e currículo

> Status do adendo: concluído (2026-11-17). Desenha os RF-25 a RF-28 do adendo do `requirements.md`.
> O texto acima fica como está; os ADRs continuam a numeração.

### Visão geral da abordagem do adendo

O painel continua dentro do `<nav>` da barra fixa, mas passa a começar abaixo dela
(`top: var(--header-height)`) e a deslizar por `transform`. Um véu, irmão do painel na
mesma barra, escurece a página abaixo da barra só no celular. O botão da barra passa a
abrir e fechar: o ícone segue o `aria-expanded` pelo CSS, e o JavaScript troca o nome.
O pé do painel ganha dois grupos lidos do `Perfil`, como o rodapé: "Redes Sociais"
(GitHub e LinkedIn) e "Currículo" ("Download CV").

```text
390 px, menu aberto
┌──────────────────────────────────────┐
│ [SN] Seu Nome                    [X] │  barra do site (visível e clicável)
├────────┬─────────────────────────────┤
│ véu    │ Início                      │
│ sobre  │ Projetos                    │
│ a      │ Sobre                       │
│ página │ Habilidades                 │
│        │ Contato                     │
│        │                             │
│        │ ─────────────────────────── │
│        │ REDES SOCIAIS               │
│        │ (gh) GitHub                 │
│        │ (in) LinkedIn               │
│        │ CURRÍCULO                   │
│        │ (↓) Download CV             │
└────────┴─────────────────────────────┘
```

### Componentes do adendo

#### `templates/base.html`

- Sai o `<button class="nav__close">` de dentro do painel.
- O `nav__toggle` leva as duas imagens (`menu.svg` com a classe `nav__icone-abrir` e
  `close.svg` com `nav__icone-fechar`), ambas `aria-hidden`; continua com
  `aria-controls="nav-menu"`.
- Depois da lista de links, dentro do painel, o bloco `nav__extras`, só se algum dos três
  campos estiver preenchido. Cada grupo é um `<p class="nav__grupo" id="…">` seguido de
  `<ul aria-labelledby="…">`, e só existe se tiver link:
  - "Redes Sociais": `link_github` e `link_linkedin`, cada um com o seu `{% if %}`,
    `target="_blank"` e `rel="noopener noreferrer"`;
  - "Currículo": `curriculo`, com `download` e o texto "Download CV".

  Cada link (`nav__extra`) tem a imagem do ícone (`icons/social/github.svg`,
  `icons/social/linkedin.svg`, `icons/download.svg`, `alt=""`) e o nome visível.
- Depois do painel, `<div class="nav__veu" aria-hidden="true">`.

#### `static/css/styles.css`

- `.nav__veu` e `.nav__extras` com `display: none` fora do celular.
- No `@media (max-width: 768px)`:
  - `.nav__menu`: `top: var(--header-height)`, `right: 0`, altura
    `calc(100vh - var(--header-height))` com a versão em `dvh` depois, `display: flex`
    em coluna, `overflow-y: auto`, `transform: translateX(100%)` e
    `transition: transform`; o padding de cima cai de `--spacing-4xl` para
    `--spacing-xl`, porque o botão de fechar saiu do painel. A sombra só existe em
    `.show`, para não aparecer na borda da tela com o painel fechado.
  - `.nav__menu.show`: `transform: none`.
  - `.nav__veu`: `position: fixed`, `top: var(--header-height)`, `left: 0`,
    `width: 100%` e a mesma altura do painel, fundo `rgba(4, 10, 20, 0.7)`,
    `opacity: 0` e `visibility: hidden`, com transição de `opacity` e `visibility`;
    `.nav__menu.show ~ .nav__veu` mostra o véu.
  - `.nav__extras`: `margin-top: auto`, borda e respiro em cima; `.nav__grupo` com um
    tamanho, peso, caixa e cor só (`--fs-xs`, 600, caixa alta, `--color-gray-400`), e o
    segundo grupo com espaço acima; `.nav__extra` com `min-height: 2.75rem`,
    `--color-gray-400` e o ícone pelo mesmo filtro dos ícones sociais.
  - O ícone do botão segue o estado: com `aria-expanded` verdadeiro some o
    `.nav__icone-abrir`, e com falso some o `.nav__icone-fechar`.
- Saem as regras do `.nav__close`, e o seletor `.nav__toggle, .nav__close` fica só
  `.nav__toggle`.

#### `static/js/main.js`

- `abrirMenu()` troca o `aria-label` do botão para "Fechar menu"; `fecharMenu()`, para
  "Abrir menu".
- O clique no botão alterna: com o menu aberto, `fecharMenu({ devolverFoco: true })`;
  fechado, `abrirMenu()`.
- Saem a constante e o ouvinte do `navClose`. O véu fica fora do painel e do botão,
  então o ouvinte de "clique fora" já o cobre.

### Interfaces do adendo

Sem rota, contexto ou campo novo: o bloco lê `perfil.link_github`, `perfil.link_linkedin`
e `perfil.curriculo`, que o `base.html` já recebe para o rodapé. Some o `id="nav-close"`.

### ADR-12 — O botão da barra abre e fecha

**Supersedes** o botão de fechar do RF-04 (seção 2).

- **Decisão:** um botão só, na barra, com os dois ícones; o CSS mostra um ou outro pelo
  `aria-expanded`, e o JavaScript troca o nome.
- **Alternativas:** manter o botão de fechar dentro do painel, alinhado ao hambúrguer;
  trocar o `src` da imagem pelo JavaScript.
- **Porquê:** com o painel abaixo da barra, o hambúrguer continua à vista e é o lugar
  natural para fechar; o ícone guiado pelo atributo não fica fora de sincronia com o
  estado lido pelo leitor de tela.
- **Trade-off:** o foco, ao abrir, vai para o primeiro link do painel; para fechar pelo
  teclado sem o Esc, o Tab passa pelos links até o botão.

### ADR-13 — Rótulos dos grupos sem nível de título

- **Decisão:** "Redes Sociais" e "Currículo" são `<p>` que dão nome às listas por
  `aria-labelledby`.
- **Alternativas:** `<h2>`, como no rodapé.
- **Porquê:** o painel vem antes do `<h1>` no HTML; títulos ali abririam a hierarquia
  da página antes do nome (RF-12), e um painel fechado e inerte não deve contar como
  seção.
- **Trade-off:** quem navega por títulos no leitor de tela não pula para os grupos; a
  lista anuncia o nome do grupo ao entrar nela.

### ADR-14 — Véu com altura declarada

- **Decisão:** o véu tem `top` e altura declarados (`calc(100dvh -
  var(--header-height))`), não `bottom: 0`.
- **Alternativas:** `inset: var(--header-height) 0 0`.
- **Porquê:** a barra tem `backdrop-filter`, e um elemento `position: fixed` dentro dela
  se posiciona pela barra, não pela tela: com `bottom: 0`, o véu terminaria no fim da
  barra. O painel já declara a altura pelo mesmo motivo.
- **Trade-off:** o véu e o painel repetem a mesma conta de altura.

### Impacto no código existente do adendo

- RF-04 (botão de fechar e área do painel) passa a valer com o RF-25; o foco ao abrir, o
  Esc, o `inert` e o anel de foco não mudam.
- `docs/referencia/interface-e-acessibilidade.md`: o menu inerte ganha o painel abaixo
  da barra, o botão único, o véu e o bloco de redes e currículo.
- O README não descreve o menu; não muda.

### Estratégia de testes do adendo

- **Suíte (RF-28)**, no `app_portfolio/test_interface.py`:
  - HTML: o bloco com os três campos, cada campo vazio, nenhum campo; os rótulos com a
    mesma classe e as listas com `aria-labelledby`; sem `nav-close`; o botão com os dois
    ícones e `aria-controls`.
  - CSS lido como texto: o painel abaixo da barra, `overflow-y: auto`, `transform` sem
    `transition` de `right`, o véu só no celular e com altura declarada, o bloco
    escondido no desktop, `.nav__grupo` com um tamanho só, alvos de 44 px e o contraste
    de `--color-gray-400` sobre `--color-bg-secondary` acima de 4,5:1.
  - JavaScript lido como texto: os dois nomes do botão e o alternar no clique.
  - Os testes do menu que citam o `.nav__close` passam a citar só o `.nav__toggle`.
- **Navegador:** a 390 x 844 e a 360 x 640, menu aberto e fechado: a barra visível e
  clicável, o véu, o X no lugar do hambúrguer, o bloco no pé do painel, a rolagem no
  celular baixo, Tab e Esc, o leitor de tela anunciando "Abrir menu" e "Fechar menu"
  pela árvore de acessibilidade, nenhuma violação de CSP e nenhum achado do axe-core.

### Desvios do adendo

1. **Cor dos ícones do bloco (RF-26).** O componente pedia "o mesmo filtro dos ícones
   sociais", mas os ícones do rodapé não têm filtro (o traço já é ciano), e o
   `download.svg` usa `currentColor`, que dentro de `<img>` vira preto. Os três ícones
   do bloco levam `filter: brightness(0) invert(1)` e `opacity: 0.7`, a mesma receita
   do botão do GitHub nos cartões: claros e iguais entre si.
2. **Ordem de pintura do painel e do véu (ADR-14).** O véu vem depois do painel no HTML
   e, com os dois em `position: fixed`, ficaria por cima dele; o painel ganhou
   `z-index: 1` dentro do celular.
3. **Classe das listas e espaço entre os grupos (RF-26).** As listas dos grupos levam a
   classe `nav__extras-lista`, e o espaço acima do segundo rótulo vem de
   `.nav__extras-lista + .nav__grupo`; o link do bloco ganha a cor de destaque ao passar
   o mouse, como os links de navegação.

### Notas de implementação do adendo

- **Suíte:** 333 testes antes, 348 depois. A classe `TestMenuComRedesECurriculo` do
  `test_interface.py` traz 15 testes (HTML com cada campo vazio e preenchido, CSS do
  painel, do véu e do bloco, contraste e JavaScript), e dois testes antigos passaram a
  ler o `calc()` da altura e o seletor só do `.nav__toggle`.
- **Navegador** (Chrome do sistema pelo Playwright, `semear_dados_demo` com currículo,
  banco temporário), a 390 x 844, 360 x 640 e 667 x 375 deitado:
  - O painel começa a 64 px do topo (abaixo da barra) e vai até o fim da tela (780 px
    de altura a 390 x 844); o véu cobre a mesma faixa. Com o menu aberto, o ponto
    central do logo e o do botão continuam sendo o próprio logo e o botão.
  - Fechado, o painel fica em `translateX(100%)`, sem rolagem horizontal; aberto,
    `transform: none`. A única transição do painel é `transform`.
  - Os dois rótulos medem 12 px, peso 600, caixa alta e `rgb(131, 147, 170)`; os três
    links do bloco têm 44 px de altura.
  - A 390 x 844 o bloco termina 32 px acima do fim do painel; a 360 x 640 cabe sem
    rolar; a 667 x 375 o painel rola por dentro e o "Download CV" fica alcançável.
  - Teclado: ao abrir, o foco vai ao "Início"; o Tab passa pelos cinco links, GitHub,
    LinkedIn, "Download CV" e chega ao botão, sem entrar na página inerte. Esc e o X
    fecham com o foco no botão; o toque no véu e o clique num link fecham sem mover o
    foco para o botão. A árvore de acessibilidade tem um botão "Fechar menu" com o
    menu aberto e um "Abrir menu" depois de fechar.
  - Nenhuma violação de CSP nem erro no console. Acima de 768 px, o véu, o bloco e o
    botão ficam com `display: none` e o painel nunca fica inerte.
  - axe-core 4.14.0: sem achado no menu fechado. Com o menu aberto, a 667 x 375,
    acusa `landmark-one-main` e `page-has-heading-one` (boas práticas, não critérios
    WCAG): o `<main>` fica `inert` de propósito enquanto o painel está aberto (RF-04).
    A branch principal, sem o adendo, acusa os mesmos dois a 390 x 844 e a
    667 x 375; não é efeito do adendo.
