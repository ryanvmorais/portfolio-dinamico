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

# Design — Redesenho da home para quem avalia o portfólio

## 1. Visão geral

O redesenho mexe em quatro camadas, nesta ordem de dependência:

1. **Dados.** `Habilidade` troca o `progresso` por um `nivel` de três valores e
   ganha uma ligação opcional com `Tecnologia`; `Projeto` ganha o endereço da
   versão no ar e quatro campos de estudo de caso. Saem o modelo `Estatistica`
   e os campos que só serviam à página antiga. Uma migração de dados converte o
   que existe (RF-20).
2. **View.** A `home` deixa de montar `tech_icons` e `estatisticas` e passa a
   entregar as habilidades já agrupadas por nível, com a contagem de projetos de
   cada uma, o total de projetos e as iniciais do perfil.
3. **Templates e estáticos.** `home.html`, `base.html`, `styles.css` e
   `main.js` seguem o protótipo validado a 390 e a 1280 px (seção 2.1); o filtro
   de projetos passa a aceitar categoria **ou** tecnologia.
4. **Marca.** Um módulo novo, `marca.py`, calcula as iniciais e serve o favicon
   SVG e o ícone de tela inicial PNG gerados delas, com os arquivos atuais de
   reserva.

Tema escuro, tokens de cor, fontes, menu do celular, seções Sobre e Contato
(exceto rótulo, posição e o selo da foto) e as regras da spec 004 não mudam.

## 2. Componentes

### 2.1 Protótipo validado

O desenho foi validado num protótipo navegável a 390 e a 1280 px, com os dados
da demonstração, antes desta spec. Disposição de cada parte:

```text
1280 px
┌──────────────────────────────────────────────────────────────────────┐
│ [SN] Seu Nome            Início  Projetos  Sobre  Habilidades  Contato │
├──────────────────────────────────────────────────────────────────────┤
│ (● Disponível para Projetos · Estado, UF)              ┌───────────┐ │
│ Seu Nome                                               │           │ │
│ Desenvolvedor Full-Stack                               │  foto 4:5 │ │
│ bio_curta…                                             │  340 px   │ │
│ [Ver projetos →] [gh] [in] [cv]  ou entre em contato   │           │ │
│ 5+ anos de experiência   6 projetos publicados         └───────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ ESTUDOS DE CASO / Projetos em Destaque                                 │
│ (Todos) (Web App) (API)                                                │
│ Mostrando 1 projeto com Django  Limpar filtro      ← só com chip ativo │
│ ┌ capa ┐ ┌ capa ┐ ┌ capa ┐                                            │
│ │ cat. título descrição tags            │  ▸ Como foi feito (fechado) │
│ │ [Ver online] [Código]                 │                             │
├──────────────────────────────────────────────────────────────────────┤
│ QUEM SOU / Sobre Mim (conteúdo atual; selo "5+ anos de experiência")   │
├──────────────────────────────────────────────────────────────────────┤
│ COM O QUE TRABALHO / Habilidades Técnicas                              │
│ ┌ Back-end ──────────┐ ┌ Front-end ─────────┐ ┌ Infraestrutura ────┐  │
│ │ Uso no dia a dia    │ │ …                  │ │ …                  │  │
│ │ (Python · 1 projeto)│ │                    │ │                    │  │
│ │ Já usei em projeto  │ │                    │ │                    │  │
│ │ Estudando (GraphQL) │ │                    │ │                    │  │
├──────────────────────────────────────────────────────────────────────┤
│ PRÓXIMO PASSO / Entre em Contato (conteúdo atual)                      │
├──────────────────────────────────────────────────────────────────────┤
│ [SN] Seu Nome · bio_curta  │ Links rápidos │ Redes: [gh] [in]          │
│ ──────────────────────────────────────────────────────────────────── │
│               © 2026 Seu Nome. Todos os direitos reservados.           │
└──────────────────────────────────────────────────────────────────────┘

390 px: hero centralizado, foto redonda de 112 px acima do selo, "Ver projetos"
na largura toda, ícones numa linha abaixo; cartões, blocos de habilidade e
colunas do rodapé empilhados; "Ver online" e "Código" empilhados, da mesma
largura.
```

O protótipo tinha o primeiro "Como foi feito" aberto só para mostrar o conteúdo;
na página, todos começam fechados (RF-10).

### 2.2 `models.py`

- `NivelHabilidade(models.TextChoices)`: `DIA_A_DIA = "dia_a_dia", "Uso no dia a
  dia"`, `JA_USEI = "ja_usei", "Já usei em projeto"`, `ESTUDANDO = "estudando",
  "Estudando"`. A ordem da classe é a ordem de exibição (RF-11).
- `Habilidade`: sai `progresso`; entram `nivel` e `tecnologia` (seção 3).
- `Projeto`: entram `link_online`, `problema`, `papel`, `decisao_tecnica` e
  `resultado`; uma propriedade `tem_estudo_de_caso` diz se algum dos quatro tem
  texto (RF-10).
- `Perfil`: sai `mostrar_progresso`.
- `Tecnologia`: saem `icone` e `mostrar_no_home` (ADR-04).
- `CategoriaHabilidade`: sai `icone` (o bloco de área não tem ícone no
  protótipo; ADR-04).
- `Estatistica`: o modelo sai (RF-05, decisão resolvida 4).

### 2.3 `marca.py` (novo)

- `calcular_iniciais(nome: str | None) -> str`: separa o nome em palavras,
  ignora as que não começam por letra, e junta a primeira letra da primeira e
  da última palavra, em maiúsculas (`str.upper`, que mantém o acento). Nome
  vazio ou sem letra cai em `"Seu Nome"`, o padrão do template, e dá `"SN"`
  (RF-16).
- `montar_favicon_svg(iniciais: str) -> str`: o SVG do favicon, um quadrado de
  32 x 32 com cantos arredondados no fundo `#0a1628`, borda e letras em
  `#00d4ff`. As iniciais passam por `xml.sax.saxutils.escape` antes de entrar no
  texto, embora só contenham letras (defesa em profundidade).
- `gerar_icone_png(iniciais: str) -> bytes`: o PNG de 180 x 180, opaco, com o
  monograma desenhado pelo Pillow na `static/fonts/inter-latin-variavel.woff2`,
  peso ExtraBold. Memoizado com `functools.lru_cache(maxsize=8)`: o desenho só
  roda quando as iniciais mudam.
- Views `favicon_svg` e `icone_tela_inicial`: com `Perfil`, respondem o SVG
  (`image/svg+xml`) ou o PNG (`image/png`) com `Cache-Control: public,
  max-age=86400`; sem `Perfil`, redirecionam (302) para o `favicon.webp` e o
  `apple-touch-icon.png` de `static/icons/` (RF-17, RF-18).

### 2.4 `views.py`

- Sai a montagem de `tech_icons` e `estatisticas`.
- As categorias de habilidade vêm com `Prefetch("habilidades")` sobre
  `Habilidade.objects.select_related("tecnologia").annotate(qtd_projetos=Count("tecnologia__projeto",
  distinct=True))`; uma função `agrupar_habilidades(categorias)` devolve, por
  categoria, a lista de níveis não vazios na ordem do `NivelHabilidade`, cada um
  com as suas habilidades na ordem de cadastro (RF-11, RF-12).
- O contexto ganha `habilidades_por_categoria`, `total_projetos`
  (`len(projetos)`, que avalia a consulta uma vez e o template reaproveita) e
  `iniciais` (`calcular_iniciais(perfil.nome)` ou o padrão).

### 2.5 `home.html`

- **Ordem:** hero, projetos, sobre, habilidades, contato (RF-07), com as
  âncoras atuais.
- **Hero:** selo com `{% if perfil.status_trabalho %}`; `<h1>` só com o nome;
  cargo e `bio_curta` em parágrafos; "Ver projetos" (`btn btn--primary`); um
  `<a>` de ícone por campo preenchido (`link_github`, `link_linkedin`,
  `curriculo` com `download`), cada um com `aria-label`; "ou entre em contato";
  a lista de números com `{% if %}` por item e `pluralize`; a foto com
  `width`/`height`, `fetchpriority="high"` e sem `loading="lazy"` (RNF-04).
  Saem o bloco de código, as estatísticas e o indicador "Explorar".
- **Cartão de projeto:** `data-tecnologias` com os ids das tecnologias,
  separados por espaço; `<details class="project-card__caso">` com
  `{% if projeto.tem_estudo_de_caso %}` e um `<dt>/<dd>` por campo preenchido;
  linha de ações com `{% if %}` por link e o título do projeto em `sr-only` no
  nome de cada um (RF-09, RF-10).
- **Linha de estado do filtro:** `<p class="projects__estado" tabindex="-1"
  hidden>` com o texto e o botão "Limpar filtro", logo abaixo dos filtros de
  categoria; o `main.js` a mostra e esconde.
- **Habilidades:** um bloco por categoria (`<h3>`), um `<h4>` por nível e os
  chips; com `qtd_projetos > 0` o chip é `<button type="button" class="chip"
  data-tecnologia="<id>" data-nome="<nome da tecnologia>"
  aria-pressed="false">`, senão `<span class="chip">` (RF-12). Sai a faixa de
  ícones (RF-14).
- **Sobre:** o selo da foto lê `perfil.anos_experiencia`, com `{% if %}`.
- **Rótulos:** "Quem sou", "Estudos de caso", "Com o que trabalho", "Próximo
  passo" (RF-08); a caixa alta continua vindo do CSS.

### 2.6 `base.html`

- **Ícones:** `<link rel="icon" type="image/webp" href="favicon.webp">` fica, e
  com perfil entra antes dele `<link rel="icon" type="image/svg+xml"
  href="/favicon.svg?v=<iniciais>">`; o `apple-touch-icon` aponta para
  `/apple-touch-icon.png?v=<iniciais>`. O `?v=` muda quando as iniciais mudam e
  fura o cache do navegador (RF-18).
- **Logo (menu e rodapé):** `<span class="logo__monograma"
  aria-hidden="true">{{ iniciais }}</span>` seguido do nome; o `aria-label` do
  link segue começando pelo nome (RF-16).
- **Menu:** Início, Projetos, Sobre, Habilidades, Contato (RF-07); a mesma ordem
  nos "Links rápidos" do rodapé.
- **Rodapé:** a frase é `perfil.bio_curta` com `{% if %}`; o bloco "Redes" só
  existe com `link_github` ou `link_linkedin`, e só com eles (RF-15).
- **Fecho da página:** a linha de direitos autorais segue como hoje, na largura
  toda do rodapé, abaixo de um divisor e centralizada em qualquer largura de
  tela: ela marca o fim da página, por isso não acompanha o alinhamento à
  esquerda das colunas de cima.

### 2.7 `styles.css`

Edição por trecho (sem formatador; notas de manutenção do `specs/README.md`):

- **Sai:** o bloco de código do hero, as estatísticas, o indicador "Explorar",
  as barras de habilidade, a faixa de ícones, os colchetes do logo e as regras
  de altura de tela do hero (`100vh`/`100svh`).
- **Entra:** o hero em duas colunas (`minmax(0, 1fr) 340px`) que vira uma
  coluna centralizada até 768 px, com a foto redonda de 112 px por `order: -1`;
  o selo; os botões de ícone de 48 px; a linha de números; o monograma; os
  chips (40 px de altura, borda `--color-gray-500`, estado `[aria-pressed="true"]`
  com borda e fundo ciano); os blocos de área; o `<details>` do cartão; a linha
  de estado do filtro.
- **Alto contraste:** chips, selo, filtros e botões de ícone têm borda, que o
  `forced-colors: active` mantém (RNF-02).
- **Movimento reduzido:** o bloco `prefers-reduced-motion` segue o último do
  arquivo e passa a cobrir as transições novas.

### 2.8 `main.js`

- `filtrarProjetos({ categoria, tecnologia })`: um cartão aparece quando a
  categoria é `all` ou a do cartão e, havendo tecnologia, quando o id está no
  `data-tecnologias` dele. Um filtro por vez (ADR-07): o chip zera a categoria
  para "Todos", e a categoria tira a tecnologia.
- `iniciarChips()`: o clique num chip marca só ele (`aria-pressed`), chama o
  filtro, mostra a linha de estado ("Mostrando N projetos com <nome>"), rola até
  `#projects` com `comportamentoDeRolagem()` e põe o foco na linha de estado
  (ADR-08). O mesmo chip de novo, "Limpar filtro" ou uma categoria desfazem o
  filtro e escondem a linha.
- A região `#projects-status` continua anunciando o filtro de categoria; no
  filtro por chip quem anuncia é a linha de estado ao receber o foco, para o
  leitor de tela não ouvir a frase duas vezes.

### 2.9 `admin.py`

- `ProjetoAdmin`: grupo "Links" com `link_github` e `link_online`; grupo novo
  "Estudo de caso" (recolhível) com os quatro campos.
- `HabilidadeInline`: colunas `nome`, `nivel` e `tecnologia`
  (`autocomplete_fields`, que o `TecnologiaAdmin` já habilita pelo
  `search_fields`).
- `TecnologiaAdmin`: `list_display = ("nome", "ordem")`, sem o filtro de
  `mostrar_no_home`.
- `PerfilAdmin`: sem `mostrar_progresso`; o texto de ajuda de
  `anos_experiencia` diz que zero esconde o número.
- `EstatisticaAdmin`: sai.

### 2.10 `semear_dados_demo.py`

Habilidades com nível e tecnologia ligada (pelo nome), projetos com
`link_online` em `https://example.com/…` (domínio reservado para exemplos, RFC
2606) e os quatro campos de estudo de caso, sem estatísticas (RF-21). As
tecnologias perdem `icone` e `mostrar_no_home`.

### 2.11 Arquivos removidos

`static/icons/tech/` (os dez SVGs da faixa), `static/icons/social/` menos
`github.svg` e `linkedin.svg`, e `code.svg`, `server.svg` e `cloud.svg` de
`static/icons/`, depois de conferir que nada mais os usa.

## 3. Modelo de dados

| Modelo | Campo | Tipo | Observação |
|---|---|---|---|
| `Habilidade` | `nivel` | `CharField(max_length=10, choices=NivelHabilidade, default=DIA_A_DIA)` | novo |
| `Habilidade` | `tecnologia` | `ForeignKey(Tecnologia, null=True, blank=True, on_delete=SET_NULL, related_name="habilidades")` | novo |
| `Habilidade` | `progresso` | — | removido |
| `Projeto` | `link_online` | `URLField(blank=True, null=True)` | novo, como `link_github` |
| `Projeto` | `problema`, `papel`, `decisao_tecnica`, `resultado` | `TextField(blank=True, max_length=600)` | novos; o limite de caracteres aparece no Admin |
| `Perfil` | `mostrar_progresso` | — | removido |
| `Tecnologia` | `icone`, `mostrar_no_home` | — | removidos |
| `CategoriaHabilidade` | `icone` | — | removido |
| `Estatistica` | — | — | modelo removido |

Migrações, em três arquivos (ADR-03):

1. `0024`: adiciona `nivel`, `tecnologia` e os campos de `Projeto`.
2. `0025`: `RunPython` que preenche `nivel` pelo `progresso` (80 ou mais,
   `dia_a_dia`; de 50 a 79, `ja_usei`; abaixo de 50, `estudando`) e liga
   `tecnologia` à de mesmo nome (`nome__iexact`, a primeira por `ordem`); o
   caminho de volta devolve `progresso` 90, 65 e 30.
3. `0026`: remove `progresso`, `mostrar_progresso`, `icone` e `mostrar_no_home`
   de `Tecnologia`, `icone` de `CategoriaHabilidade` e o modelo `Estatistica`.

## 4. Interfaces

### Rotas novas

| Rota | Resposta |
|---|---|
| `/favicon.svg` | SVG das iniciais; sem perfil, 302 para `static/icons/favicon.webp` |
| `/apple-touch-icon.png` | PNG 180 x 180 do monograma; sem perfil, 302 para `static/icons/apple-touch-icon.png` |

`/favicon.ico` segue redirecionando para o `favicon.webp`. O `/apple-touch-icon.png`
na raiz também atende o celular que pede o ícone sem ler o `<link>`.

### Contexto da `home`

Saem `estatisticas` e `tech_icons`; `categorias_habilidades` vira
`habilidades_por_categoria` (`list[dict]`: `categoria`, `niveis` →
`[{rotulo, habilidades}]`); entram `total_projetos: int` e `iniciais: str`.

### Atributos lidos pelo `main.js`

| Elemento | Atributo | Conteúdo |
|---|---|---|
| `.project-card` | `data-category` | slug da categoria (como hoje) |
| `.project-card` | `data-tecnologias` | ids das tecnologias, separados por espaço |
| `button.chip` | `data-tecnologia` | id da tecnologia ligada |
| `button.chip` | `data-nome` | nome da tecnologia, para a linha de estado |

## 5. Decisões técnicas (ADRs)

### ADR-01 — Habilidade ligada a uma tecnologia por chave estrangeira opcional

**Decisão.** `Habilidade.tecnologia` aponta para uma `Tecnologia`, opcional; a
contagem de projetos sai dessa ligação.
**Alternativas.** (a) Casar habilidade e tecnologia pelo nome a cada página;
(b) `ManyToMany` entre as duas; (c) um modelo só (decisão resolvida 2).
**Porquê.** O nome casa mal ("React / Vue.js", "Django REST"); a ligação
explícita é editável no Admin. Uma habilidade é uma tecnologia; muitas para
muitas não tem caso real e complicaria a contagem.
**Trade-off.** Quem cadastra liga cada habilidade à tecnologia; a migração faz
isso pelo nome para os dados existentes, e o que não casar fica sem contagem até
ser ligado.

### ADR-02 — Nível como escolha fixa no código

**Decisão.** `NivelHabilidade` é um `TextChoices` de três valores.
**Alternativas.** (a) Modelo `Nivel` editável no Admin; (b) número de 1 a 3.
**Porquê.** Os três degraus são a decisão de produto (decisão resolvida 3); um
cadastro editável permitiria voltar à escala fina que a spec remove. O rótulo
legível fica junto do valor.
**Trade-off.** Mudar os degraus exige migração.

### ADR-03 — Migração em três passos, reversível

**Decisão.** Adicionar, converter e só então remover, em três migrações; a de
dados tem caminho de volta.
**Alternativas.** (a) Uma migração só; (b) remover sem converter.
**Porquê.** O `progresso` precisa existir quando o `RunPython` lê; separar deixa
cada passo testável e permite voltar à versão anterior sem perder habilidades
(RF-20).
**Trade-off.** Três arquivos em vez de um, e a volta aproxima o progresso (90,
65 ou 30), sem recuperar o valor exato.

### ADR-04 — Campos e arquivos sem uso saem junto

**Decisão.** Saem `Estatistica`, `progresso`, `mostrar_progresso`,
`Tecnologia.icone`, `Tecnologia.mostrar_no_home`, `CategoriaHabilidade.icone`,
os SVGs de tecnologia e das redes que deixaram o rodapé.
**Alternativas.** Manter os campos e arquivos sem uso, para uma volta futura.
**Porquê.** Campo que não aparece em lugar nenhum engana quem preenche o Admin;
a spec 004 (RF-22) já fixou a regra de não deixar código nem CSS sobrando.
**Trade-off.** Quem quiser a faixa de ícones de volta reescreve campo e
template; o histórico do Git guarda os SVGs.

### ADR-05 — Estudo de caso em quatro campos de texto

**Decisão.** `problema`, `papel`, `decisao_tecnica` e `resultado` no `Projeto`,
texto simples de até 600 caracteres cada.
**Alternativas.** (a) Um campo só em Markdown; (b) modelo `EstudoDeCaso`
separado.
**Porquê.** Os quatro títulos fixos guiam quem escreve e mantêm os cartões
comparáveis; texto simples dispensa biblioteca de Markdown e sanitização de
HTML (RNF-01). Um modelo à parte só acrescentaria uma junção para uma relação
um para um.
**Trade-off.** Sem formatação (lista, negrito, link) dentro do estudo de caso.

### ADR-06 — Filtro no navegador, com todos os projetos no HTML

**Decisão.** A home sempre entrega todos os projetos; o `main.js` esconde os que
não casam com o chip, como já faz com a categoria.
**Alternativas.** Filtro no servidor por parâmetro na URL (`?tecnologia=3`).
**Porquê.** Sem JavaScript nada se perde (RNF-03); não há recarga nem rota nova,
e o filtro de categoria já funciona assim (spec 004, RF-13).
**Trade-off.** O filtro não fica na URL: não dá para compartilhar o link já
filtrado.

### ADR-07 — Um filtro por vez

**Decisão.** Chip e categoria não se combinam: ativar um desfaz o outro.
**Alternativas.** Combinar os dois (categoria E tecnologia).
**Porquê.** A combinação esvazia a grade com facilidade (poucos projetos por
categoria) e exige explicar dois estados ao mesmo tempo; o protótipo validado
já zerava a categoria ao ativar o chip.
**Trade-off.** Não dá para pedir "APIs com Django" de uma vez.

### ADR-08 — O foco segue o filtro até os projetos

**Decisão.** Ao ativar um chip, a página rola até Projetos e o foco vai para a
linha de estado (`tabindex="-1"`), que tem o "Limpar filtro" logo ao lado.
**Alternativas.** Deixar o foco no chip e só anunciar pela região viva.
**Porquê.** Com o foco no chip, quem usa teclado fica numa seção que já saiu da
tela e precisa voltar a Projetos com dezenas de Tab; o foco na linha mostra e
lê o resultado de uma vez.
**Trade-off.** O teclado sai da seção Habilidades a cada filtro; para trocar de
chip, a pessoa volta até ela.

### ADR-09 — Marca gerada do nome no servidor

**Decisão.** As iniciais saem do `Perfil.nome` em Python; o favicon é um SVG
com `<text>` e o ícone de tela inicial é um PNG desenhado pelo Pillow com a
Inter do projeto; os arquivos atuais ficam de reserva sem perfil.
**Alternativas.** (a) Imagens fixas em `static/`, trocadas à mão por quem
clona; (b) campo de upload de favicon no `Perfil`; (c) letras do SVG
convertidas em traços com `fontTools`.
**Porquê.** Quem clona ganha a própria marca sem editar imagem (objetivo 5); o
Pillow já é dependência e lê o woff2 variável, inclusive o peso ExtraBold
(conferido com o Pillow 13). Converter as letras em traços exigiria um pacote
novo (RNF-01).
**Trade-off.** O favicon SVG não carrega fonte externa: o navegador desenha as
iniciais na fonte do sistema (Segoe UI, San Francisco, Roboto), parecida mas
não idêntica à Inter do logo e do PNG.

### ADR-10 — Hero da altura do conteúdo

**Decisão.** O hero perde o `min-height` de tela inteira (`100vh` com `100svh`
e `100dvh`) e passa a ter a altura do conteúdo, com respiro vertical.
**Alternativas.** Manter a tela inteira e só trocar o conteúdo.
**Porquê.** O topo de Projetos tem de aparecer na primeira tela (RF-06); a tela
inteira deixava a primeira rolagem vazia no desktop.
**Trade-off.** Em telas muito altas, o hero fica proporcionalmente mais baixo.
A spec 004, RF-15, passa a valer só para o painel do menu.

## 6. Impacto e dependências

- **Dependências:** nenhuma nova (RNF-01).
- **Migrações:** `0024` a `0026`; a `0025` precisa rodar antes de remover o
  `progresso`. Um deploy com dados aplica as três em sequência, sem passo
  manual; os campos novos do estudo de caso e da versão no ar ficam vazios até
  serem preenchidos no Admin.
- **CSP:** sem `<script>` nem estilo inline novo; os ícones gerados são
  servidos pela própria origem (`img-src 'self'`).
- **Specs anteriores**, marcadas com `**Superseded by** 008-redesenho-da-home`
  ao fim da implementação: 001, RF-06 e RF-07; 004, RF-02, RF-07, RF-14, RF-15
  (a parte do hero) e RF-20 (a parte do ícone da aba), e o indicador
  "Explorar" do RF-11; 007, RF-05.
- **Documentação:** README e `README.en.md` (funcionalidades e Admin),
  `CLAUDE.md` (árvore de arquivos, modelos), `docs/referencia/arquitetura.md`,
  `docs/referencia/interface-e-acessibilidade.md` e as notas de manutenção do
  `specs/README.md` (RNF-05).
- **Lighthouse CI:** usa o `semear_dados_demo`; a foto do hero passa a ser o
  maior elemento da primeira tela e precisa caber nos limites atuais.

## 7. Estratégia de testes

- **`test_redesenho.py` (novo), com o cliente do Django:** hero (RF-01 a RF-05
  com cada campo vazio e preenchido, singular e plural), ordem das seções e do
  menu e rótulos (RF-07, RF-08), cartão com e sem links e estudo de caso
  (RF-09, RF-10), agrupamento por nível, contagem e chip não interativo (RF-11,
  RF-12), ausência da faixa de ícones (RF-14), rodapé (RF-15), logo com
  monograma (RF-16) e a home 200 com todo opcional vazio (RF-22).
- **`marca.py`:** `calcular_iniciais` com acento, nome de uma palavra, palavras
  que não começam por letra e vazio; o SVG com as iniciais escapadas e menos de
  2 KiB; o PNG de 180 x 180, opaco (modo `RGB`), e a memoização; as rotas com e
  sem perfil (200 com tipo e cache, ou 302 para a reserva) e o `?v=` no
  `base.html` mudando com o nome (RF-17, RF-18).
- **Migração (RF-20):** `MigrationExecutor` do Django volta à `0023`, cria
  habilidades e tecnologias pelos modelos históricos, avança até a `0026` e
  confere nível, ligação e a ausência de `Estatistica`; o caminho de volta
  também é exercido. Marcado `django_db(transaction=True)`.
- **`test_interface.py`:** saem os testes do bloco de código, das estatísticas,
  da altura do hero, das barras, das seis redes fixas e do ícone do PostgreSQL;
  entram, lidos como texto, o filtro por chip no `main.js` (atributos, foco na
  linha de estado, `comportamentoDeRolagem()`), as bordas dos chips em alto
  contraste e o bloco de movimento reduzido ainda por último.
- **`test_semear_dados_demo.py`:** níveis, ligação, `link_online` e estudo de
  caso criados; nenhuma estatística (RF-21).
- **Conferência no navegador**, fora da suíte: axe-core e capturas a 360, 390,
  430 e 1280 px, Tab pelos chips e filtros, NVDA no filtro por chip; os
  resultados entram nas notas de implementação.

## Desvios

1. **Monograma desenhado pelo CSS** (RF-16, seção 2.6). As iniciais vão no
   atributo `data-iniciais` do `<span class="logo__monograma">` e aparecem pelo
   `::before` (`content: attr(data-iniciais)`), em vez de texto dentro do
   `<span>`. Com as letras no texto do link, o axe-core acusava
   `label-content-name-mismatch` no logo do menu: o texto visível passava a ser
   "MS Maria Souza", e o `aria-label` começa só pelo nome. O que se vê e o que o
   leitor de tela anuncia não mudam.
2. **Fundos das seções trocados** (RF-07). Com Projetos logo depois do hero,
   `.projects` passa ao fundo secundário e `.about` ao primário, para as seções
   seguirem alternando; nenhum token mudou.
3. **Hero sem animação de entrada** (RNF-04, ADR-10). O nome, o cargo, a bio e
   as ações nasciam com `opacity: 0` e o `fadeInUp`; o hero novo aparece direto,
   para a foto e o nome não esperarem a animação. Saíram também os `@keyframes`
   `floatAnimation` e `bounce` e o bloco `.btn-github`, que só o hero e o cartão
   antigos usavam (ADR-04); o `fadeInUp` fica, porque o filtro o usa.
4. **Ponto do selo na cor de destaque** (RF-02). O ponto de disponibilidade usa
   `--color-accent`: um verde exigiria token novo, fora do escopo (não-objetivos).
5. **Comentário da CSP corrigido.** O `style-src 'unsafe-inline'` existia pelo
   `style=""` da barra de progresso, que saiu; o único `style=""` que sobra é o
   do honeypot do formulário de contato. O comentário do `settings.py` e o
   `docs/referencia/configuracoes.md` passam a dizer isso; a política não mudou.
6. **Nome do link "Código" e texto do chip** (RF-09, RF-12). O NVDA colava o
   texto do `.sr-only` no anterior ("Códigodo projeto…") e o nome do chip na
   contagem ("Python· 3 projetos"). O link passa a "Código: <título>", no padrão
   de "Ver online: <título>", e o chip ganha um `<span>` interno com o nome e a
   contagem, um item só do `inline-flex`. A árvore de acessibilidade do Chrome já
   trazia os espaços; o ajuste é para o leitor de tela.

## Notas de implementação

- **Migrações:** `0024_campos_do_redesenho`, `0025_converter_habilidades` e
  `0026_remove_campos_sem_uso`. O `test_redesenho.py` vai da `0023` à `0026` e
  volta, com o `MigrationExecutor`, e devolve o banco à última migração no fim.
- **Suíte:** 239 testes antes, 309 depois (`test_redesenho.py` novo; saíram do
  `test_interface.py` os testes do bloco de código, das estatísticas, das barras,
  das seis redes fixas, do perfil sem campos de rede e do ícone do PostgreSQL).
- **Navegador** (Chrome sem interface, dados do `semear_dados_demo`):
  - axe-core 4.14 sem violação a 360, 390, 430 e 1280 px; nenhuma rolagem
    horizontal.
  - 1280 x 800: o rótulo de Projetos começa a 713 px e o título termina a 787 px,
    na primeira tela (RF-06).
  - 390 x 844: selo de 232 a 264 px, nome de 288 a 328 px, "Ver projetos" de 469
    a 527 px (RF-06).
  - Teclado: 23 Tabs do topo ao primeiro chip; Enter filtra, marca o chip, volta
    "Todos" a pressionado, deixa a `#projects-status` vazia e põe o foco na
    `#projects-estado` ("Mostrando 3 projetos com Python"); o Tab seguinte chega
    ao "Limpar filtro", e Enter devolve o foco ao "Todos" com o anúncio "Mostrando
    todos os 3 projetos."; o "Como foi feito" abre com Enter.
  - Sem JavaScript: os 3 cartões e os 6 chips aparecem.
  - Alto contraste (`forced-colors: active` emulado): chips, selo, filtros e
    botões de ícone mantêm a borda; o filtro e o chip marcados usam `Highlight`.
- **NVDA 2026.3** com o Chrome, voz ligada, conferido pelo log de fala: no chip,
  "Python · 3 projetos, botão de alternância, não pressionado"; Enter leva o foco
  à linha, que lê "Mostrando 3 projetos com Python, Limpar filtro"; Tab chega a
  "Limpar filtro, botão"; Enter anuncia "Mostrando todos os 3 projetos." e o foco
  cai em "Filtros de projeto, grupo, Todos, botão de alternância, pressionado".
  Os links do cartão leem "Ver online: Painel de métricas" e "Código: Painel de
  métricas"; o "Como foi feito", "botão, recolhido".
- **Capa dos READMEs** (`assets/portfolio-django-home-desktop.png`) refeita: a
  home a 1280 px numa moldura de navegador e, por cima, o celular a 390 px
  aberto num cartão com o "Como foi feito" expandido, com os dados de
  demonstração e o nome padrão "Seu Nome"; 2400 x 1440, 256 cores, 421 KB (a
  anterior tinha 742 KB).
- **Lighthouse** local (`@lhci/cli` 0.15.1, os limites de `.github/lighthouse/`,
  uma rodada): celular 99 de desempenho e 100 nas outras três categorias, LCP de
  2,2 s, CLS 0 e 180 KiB; desktop 100 nas quatro, LCP de 0,5 s. Todas as
  asserções passam.

## Adendo (2026-11-17): hero com duas ações e foto maior no celular

> Status do adendo: concluído (2026-11-17). Desenha os RF-24 a RF-27 do adendo do `requirements.md`.
> O texto acima fica como está; os ADRs continuam a numeração.

### Visão geral da abordagem do adendo

O hero troca a fileira de ações (botão, três ícones e um link de texto) por dois botões
que já existem no sistema: `btn--primary` para "Ver projetos" e `btn--secondary` para
"Entre em contato". Sem os ícones, o celular ganha espaço, e a foto redonda passa de
112 px para 160 px. A foto é recortada a partir do alto (`object-position: center
top`), no desktop e no celular, e o texto de ajuda do campo de foto orienta o formato.

O hero do adendo, a 1280 px e a 390 px:

```text
1280 px                                               390 px
┌──────────────────────────────────────────┬───────┐  ┌──────────────────────┐
│ (•) Disponível para Projetos · Estado, UF│       │  │      ╭────────╮      │
│ Seu Nome                                 │ foto  │  │      │  foto  │      │
│ Desenvolvedor Full-Stack                 │ 4:5   │  │      │ 160 px │      │
│ Bio curta                                │ 340px │  │      ╰────────╯      │
│ [Ver projetos →] [Entre em contato]      │       │  │       (•) selo       │
│ 5+ anos de experiência  6 projetos       │       │  │       Seu Nome       │
└──────────────────────────────────────────┴───────┘  │     cargo · bio      │
                                                      │  [ Ver projetos → ]  │
                                                      │ [Entre em contato ]  │
                                                      └──────────────────────┘
```

### Componentes do adendo

#### `templates/home.html`

- O bloco `hero__acoes` fica com dois links: `<a href="#projects" class="btn
  btn--primary">` ("Ver projetos" e a seta) e `<a href="#contact" class="btn
  btn--secondary">Entre em contato</a>`.
- Saem a lista `hero__links` (os três `icone-link` e o `if` dos campos) e o link
  `hero__contato`. O comentário do bloco diz por que os links ficam só no Contato, no
  rodapé e em Sobre.

#### `static/css/styles.css`

- `.hero__foto` ganha `object-position: center top`.
- No `@media (max-width: 768px)`: `.hero__foto-moldura` passa a `width: 160px`, e a regra
  de largura total vale para os dois botões (`.hero__acoes .btn`), não só para o
  primário.
- Saem as regras sem uso: `.hero__links`, `.icone-link` (com o `img` e o `:hover`),
  `.hero__contato` (com o `:hover`) e o `.icone-link` da lista do `forced-colors`.
- O comentário do bloco responsivo passa a citar 160 px e as duas ações na primeira
  tela.

#### `app_portfolio/models.py` e a migração `0026`

- O `help_text` do `Perfil.foto` pede um retrato vertical 4:5 (por exemplo, 960 x 1200)
  com espaço acima da cabeça e avisa que o celular mostra a foto num círculo. A
  migração `0026` é o `AlterField` que o Django gera para o texto novo, sem mudança no
  banco.

#### Testes

- `app_portfolio/test_redesenho.py`: o teste das ações passa a esperar "Ver projetos"
  para `#projects` e "Entre em contato" (`btn--secondary`) para `#contact`; o dos links
  de ícone passa a conferir que, com os três campos preenchidos, o hero não tem
  `icone-link` nem os endereços, e que GitHub e LinkedIn seguem no Contato e no rodapé;
  um teste novo confere o `help_text` da foto.
- `app_portfolio/test_interface.py`: o teste da foto do celular espera `width: 160px` e
  o `object-position: center top` na `.hero__foto`; a lista do `forced-colors` perde o
  `.icone-link`.

### Interfaces do adendo

Sem rota, contexto de view ou variável nova. O HTML do hero perde `hero__links`,
`icone-link` e `hero__contato`; os campos `link_github`, `link_linkedin` e `curriculo`
continuam lidos pelo Contato, pelo rodapé e por Sobre.

### ADR-11 — Contato como segunda ação

**Supersedes** a ação de ícones do RF-03 (seção 2 acima).

**Decisão.** A segunda ação do hero é "Entre em contato", um `btn--secondary` para a
seção de contato.
**Alternativas.** "Baixar currículo" como segundo botão; GitHub, LinkedIn e currículo
como links com rótulo ao lado do botão.
**Porquê.** O selo do hero anuncia a disponibilidade, e a ação que responde a ela é o
contato; o currículo já tem botão em Sobre, e os links com rótulo mantinham quatro
ações e não liberavam espaço para a foto.
**Trade-off.** O GitHub, que quem avalia código costuma abrir, fica a um clique a mais
(no Contato e no rodapé).

### ADR-12 — Recorte da foto pelo alto, sem ponto focal

**Decisão.** `object-position: center top` na `.hero__foto`, para a moldura 4:5 do
desktop e o círculo do celular.
**Alternativas.** Um campo de ponto focal no `Perfil`; uma posição intermediária
(`center 20%`).
**Porquê.** Num retrato, a cabeça fica na parte de cima; recortar pelo alto nunca corta
a cabeça, qualquer que seja a foto, e não pede campo nem migração de dados. Com a
posição intermediária, a foto da demonstração, cujo cabelo encosta na borda de cima do
arquivo, ainda perderia o alto da cabeça no círculo.
**Trade-off.** Uma foto com muito espaço acima da cabeça mostra esse espaço no círculo e
perde o queixo mais cedo; o texto de ajuda orienta o enquadramento.

### Impacto no código existente do adendo

- RF-03 e o desenho da seção 2 (ações do hero) deixam de valer, e o RF-04 e o RF-06
  ganham a foto de 160 px e as duas ações na primeira tela do celular.
- `docs/referencia/interface-e-acessibilidade.md`: a foto do celular passa a 160 px,
  recortada pelo alto, e o hero tem duas ações.
- O README não descreve as ações do hero; não muda.

### Estratégia de testes do adendo

- **Suíte (RF-27):** os testes alterados e o novo listados em "Testes", acima.
- **Navegador:** a home a 390 x 844 e a 1280 x 800 com os dados do `semear_dados_demo`
  e uma foto 4:5: o nome, o selo e os dois botões na primeira tela do celular, o topo
  de Projetos na primeira tela do desktop (RF-06), os botões com a mesma altura, o
  rótulo centrado, e nenhuma violação de CSP nem achado do axe-core.

### Desvios do adendo

1. A migração do `help_text` é a `0027`, não a `0026`: a `0026` já existia, da própria
   spec (remoção dos campos sem uso). — RF-26
2. O teste das ações também conta os links do hero (exatamente dois), para acusar um
   link que volte; o do celular confere a largura total dos dois botões. — RF-27

### Notas de implementação do adendo

- Suíte: 333 testes; `makemigrations --check` sem mudança.
- Navegador (Chrome sem interface, servidor de desenvolvimento, dados do
  `semear_dados_demo`, foto 4:5 de 960 x 1200 e GitHub e LinkedIn preenchidos):
  - 390 x 844: foto de 160 px com `object-position: 50% 0%`, selo a 280 px, nome a
    336 px, "Ver projetos" até 575 px e "Entre em contato" até 640 px, abaixo dos
    ~704 px que um celular comum mostra sob a barra do navegador; sem rolagem
    horizontal.
  - 1280 x 800: Projetos começa a 617 px; os dois botões lado a lado, com 58 px.
  - Nas duas larguras: dois links no hero, botões da mesma altura, rótulo centrado
    (desvio de 0 px), fonte Inter, nenhuma violação de CSP e nenhum achado do
    axe-core. O axe-core entrou pelo protocolo de depuração do navegador: a CSP do
    site bloqueia um `<script>` injetado na página.
  - Com uma foto cujo cabelo encosta na borda de cima do arquivo, o círculo mostra a
    cabeça inteira, e o cabelo encosta no alto do círculo (decisão resolvida 3).

## Adendo (2026-11-17): telefone do perfil sem uso

> Status do adendo: concluído (2026-11-17). Desenha os RF-28 e RF-29 do adendo do `requirements.md`.
> O texto acima fica como está; os ADRs continuam a numeração.

### Visão geral da abordagem do adendo

Uma migração `0028` com um `RemoveField` do `telefone` do `Perfil`. O campo sai do
`models.py`, do grupo "Detalhes de Contato e Formação" do `PerfilAdmin` e do perfil do
`semear_dados_demo`. Nenhum template, view ou contexto muda, porque nenhum lê o campo.

### Componentes do adendo

- `app_portfolio/models.py`: sai a linha do `telefone`.
- `app_portfolio/migrations/0028_remove_perfil_telefone.py`: o `RemoveField` gerado pelo
  `makemigrations`.
- `app_portfolio/admin.py`: sai o `"telefone"` dos campos do grupo de contato.
- `app_portfolio/management/commands/semear_dados_demo.py`: sai o telefone fictício.
- `app_portfolio/test_redesenho.py`: o teste dos campos antigos ganha o `telefone`, e um
  teste novo leva a migração da `0027` à `0028` e de volta.

### Interfaces do adendo

Sem rota nem contexto novo. O formulário do Admin do perfil perde um campo.

### ADR-13 — Telefone sai sem conversão

- **Decisão:** um `RemoveField` direto; a volta recria a coluna vazia.
- **Alternativas:** manter o campo para um uso futuro; levar o número para outro campo.
- **Porquê:** nada no site lê o telefone, e nenhum outro campo serve para guardá-lo; é o
  mesmo critério do ADR-04.
- **Trade-off:** o número gravado se perde na migração; quem quiser mostrar um telefone
  recria o campo e o template.

### Impacto no código existente do adendo

- A spec 001 cita o `telefone` entre os campos do `Perfil`; o texto dela fica como está,
  como registro.
- `docs/referencia/arquitetura.md` não lista o campo; não muda.

### Estratégia de testes do adendo

- No `test_redesenho.py`: o `telefone` entra no teste dos campos antigos; a migração de ida
  e volta segue o padrão do teste da `0023` à `0026`, com o esquema atual restaurado no fim.
- O `test_semear_dados_demo.py` roda o comando de verdade: um `telefone` que sobrasse nele
  quebraria a criação do perfil.

### Notas de implementação do adendo

- Sem desvios: a implementação seguiu o texto aprovado.
- A migração `0028_remove_perfil_telefone` é o `RemoveField` que o `makemigrations` gerou.
- Suíte: 333 testes antes, 334 depois. O `test_migracao_tira_o_telefone_e_volta` grava
  um perfil com telefone na `0027`, confere na `0028` que a coluna saiu e o perfil ficou,
  e na volta que a coluna existe de novo, vazia; o esquema atual é restaurado no fim. O
  teste dos campos antigos ganhou o `telefone`, e os testes do `semear_dados_demo` seguem
  verdes sem o campo.
