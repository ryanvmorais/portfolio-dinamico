# Interface e acessibilidade (spec 004): regras que não podem regredir

Mapa: vai mexer no hero, nos chips, no menu do celular, em cores, avisos, movimento, fontes, imagens ou nas páginas de erro? Leia antes.

A home foi auditada em Chrome real (10 tamanhos de celular, 768 e 1280 px,
axe-core, Tab, formulário) e corrigida na spec `004-correcoes-de-interface`; a
spec `008-redesenho-da-home` trocou o hero, as habilidades e o rodapé. As regras
que ficaram, e que um ajuste "inofensivo" desfaria:

- **Ordem das seções:** Hero, Projetos, Sobre, Habilidades, Contato, a mesma no
  menu e nos "Links rápidos" do rodapé; as âncoras (`#projects`, `#about`,
  `#skills`, `#contact`) não mudam.
- **Hero:** tem a altura do conteúdo, sem `min-height` de tela inteira (o topo de
  Projetos aparece na primeira tela a 1280 x 800). Todo texto vem do `Perfil` ou é
  contado dos dados, e cada número tem o seu `{% if %}`. Duas ações só: "Ver
  projetos" (`btn--primary`) e "Entre em contato" (`btn--secondary`), da mesma
  altura; GitHub, LinkedIn e currículo ficam no Contato, no rodapé e em Sobre
  (adendo da spec 008). Até 768 px vira uma coluna centralizada, com a foto redonda
  de 160 px acima do selo (`order: -1`) e os dois botões em largura total, na
  primeira tela de 390 x 844. A foto é recortada pelo alto (`object-position:
  center top`), para o círculo não cortar a cabeça, e é a maior imagem da primeira
  tela: `fetchpriority="high"`, medidas declaradas e **sem** `loading="lazy"`.
- **Chips e filtro:** só a habilidade com projeto é `<button class="chip">`
  (`aria-pressed`, `data-tecnologia`, `data-nome`); sem projeto, é `<span>`. Um
  filtro por vez: o chip volta a categoria para "Todos", e a categoria desmarca o
  chip. Ao filtrar por chip, a página rola até Projetos por
  `comportamentoDeRolagem()` e o foco vai para a linha de estado
  (`#projects-estado`, `tabindex="-1"`), que anuncia o resultado; a região
  `#projects-status` fica vazia para não repetir a frase. "Limpar filtro" devolve
  o foco ao filtro "Todos". Sem JavaScript, todos os projetos aparecem.
- **Estudo de caso:** `<details>` nativo, fechado, só com os campos preenchidos.
- **Cards do mesmo tamanho** (adendo da spec 008, ADR-15): os de habilidade esticam
  até a altura da fileira (`align-items: stretch`); o de projeto é uma coluna
  flexível, com as ações no pé (`margin-top: auto`) e o bloco de tags com a altura de
  duas linhas. Voltar o `align-items: start` ou tirar o `min-height` das tags
  desalinha as fileiras. O `.project-card[hidden] { display: none; }` é o que faz
  os filtros esconderem o card: sem ele, o `display: flex` vence o `hidden`.
- **Alto contraste:** chips, selo, filtros e monograma têm
  borda, reforçada no bloco `forced-colors: active`; o que está marcado usa
  `Highlight`.
- **Rodapé:** frase da `bio_curta` e só GitHub e LinkedIn do perfil; sem os dois,
  o bloco de redes some. No celular as colunas empilham à esquerda, e a linha de
  direitos autorais segue centralizada.
- **Menu do celular:** o painel `#nav-menu` é `inert` enquanto fechado (só no
  celular, por `matchMedia` no `main.js`); ao abrir, o foco vai ao primeiro link e
  o resto da página fica inerte; Esc e o X devolvem o foco ao botão. **O corte de
  768 px é o mesmo no JS e no CSS.** Adendo da spec 004:
  - O painel começa **abaixo da barra**, que fica à vista e clicável, e um véu
    (`.nav__veu`) escurece a página; tocar no véu ou num link fecha sem mover o foco.
  - **Um botão só** (`#nav-toggle`) abre e fecha: o CSS mostra o hambúrguer ou o X
    pelo `aria-expanded`, e o `main.js` troca o nome ("Abrir menu", "Fechar menu").
    Não há botão de fechar dentro do painel.
  - A barra tem `backdrop-filter`, então o `position: fixed` do painel e do véu se
    mede por ela: os dois **declaram `top` e altura** (`calc(100dvh -
    var(--header-height))`), nunca `bottom: 0`. O painel desliza por `transform`,
    nunca por `right`, e rola por dentro em celular baixo.
  - No pé do painel, dois grupos lidos do `Perfil`: "Redes Sociais" (GitHub e
    LinkedIn) e "Currículo" ("Download CV"). Os rótulos são `<p class="nav__grupo">`
    que dão nome às listas (`aria-labelledby`), não títulos: o painel vem antes do
    `<h1>`. Cada link tem o seu `{% if %}`, grupo vazio some, e o bloco não existe
    acima de 768 px.
- **Contraste:** o texto de apoio usa `--color-gray-400` (#8393aa, 4,67:1 no pior
  fundo). `--color-gray-500` é só cor de borda, nunca de texto.
- **Avisos:** um componente só, `.notification`, para o `main.js` (AJAX) e para as
  `messages` do `base.html` (sem JavaScript). O de erro leva `role="alert"` e fica
  até ser fechado; o de link (modo demonstração, spec 005) também. A região
  `.notifications` (`role="status"`) sai **sempre** no `base.html`, vazia sem
  mensagem: criada junto com o aviso, o NVDA não a anunciava. O "×" do botão de
  fechar é `aria-hidden` e fica no canto superior direito.
- **Movimento reduzido:** o bloco `prefers-reduced-motion` é o **último** do
  `styles.css` (depois do `forced-colors`) e a rolagem do JS passa por
  `comportamentoDeRolagem()`. Nada de
  `behavior: 'smooth'` solto nem de `transition: all`.
- **Fontes:** Inter e JetBrains Mono em `static/fonts/` (`fontes.css`); o Google
  Fonts não está mais na CSP nem nos templates.
- **Imagens:** capas de projeto em 1280 x 800 (16:10), foto de perfil em 960 x 1200
  (4:5), WebP q80, nome de arquivo com palavras-chave. As imagens de reserva
  (`default_perfil.webp`, `default_projeto.webp`), o `favicon.webp` e o
  `apple-touch-icon.png` ficam em `static/icons/` e não têm a marca d'água do
  Gemini; os dois ícones são a reserva da marca gerada das iniciais
  (`marca.py`), usada sempre que há `Perfil`.
- **Páginas de erro:** `400.html`, `403.html`, `403_csrf.html`, `404.html` e `500.html`
  estendem o `erro.html`, independente do `base.html` (sem banco, sem JavaScript). A
  falha de CSRF procura o `403_csrf.html`, não o `403.html`: sem ele, o Django mostra a
  página embutida em inglês. O `403.html` e o `403_csrf.html` aparecem com qualquer
  `DEBUG`; o 400, o 404 e o 500, só com `DEBUG=False` (com `DEBUG=True` o Django mostra a
  página técnica).
