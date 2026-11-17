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

# Requisitos — Redesenho da home para quem avalia o portfólio

## 1. Contexto e problema

A home mostra o perfil, os projetos, as habilidades e o contato (spec 001), com
as correções de interface da spec 004. Quem avalia um portfólio de desenvolvedor
(recrutador ou líder técnico) passa cerca de um minuto na página e procura, sem
rolar, o nome, a função, a stack, o local e o que a pessoa busca; depois, um
projeto que prove o que ela diz saber. As fontes consultadas concordam em dois
pontos: barras de porcentagem não dizem nada a quem contrata, e a habilidade só
vale quando um projeto a demonstra
([weekday.works](https://www.weekday.works/post/developer-portfolio),
[hiration](https://www.hiration.com/blog/skill-bars-resume/),
[Josh Comeau](https://joshwcomeau.com/effective-portfolio/)).

A home de hoje não entrega isso:

- **Hero genérico e com dado fixo no template.** Abre com "Olá, eu sou" e um
  bloco de código decorativo (`const developer = {...}`) cujo cargo
  ("Full-Stack Developer") e lista de tecnologias estão escritos no `home.html`,
  em inglês, sem relação com o `Perfil`. A disponibilidade, a localização e o
  currículo só aparecem na seção Sobre; GitHub e LinkedIn, só no contato e no
  rodapé. O hero ocupa a altura toda da tela, e nada da página aparece antes da
  primeira rolagem.
- **Números que ninguém confere.** As estatísticas são texto livre do modelo
  `Estatistica` ("50+ Projetos Concluídos", "30+ Clientes Satisfeitos"); a
  página pode afirmar 50 projetos e listar três.
- **Habilidades em porcentagem.** Cada habilidade tem uma barra de 0 a 100
  (`Habilidade.progresso`), muitas vezes juntando duas tecnologias num item
  ("React / Vue.js 88%"). Nada liga a habilidade aos projetos, embora cada
  `Projeto` já declare as suas `tecnologias`. Abaixo, uma faixa de logos mostra
  as tecnologias sem o nome visível.
- **Projeto sem contexto.** O cartão tem descrição e o link do GitHub; não há
  endereço da versão no ar nem o problema, o papel e a decisão por trás do
  projeto.
- **Ordem.** A seção Sobre vem antes de Projetos, embora a ação principal do
  hero leve aos projetos.
- **Rodapé fixo.** Facebook, Instagram, X e TikTok apontam para a página
  inicial de cada rede, e a frase do rodapé está escrita no `base.html` (spec
  004, RF-14).
- **Marca que não identifica ninguém.** O logo `< Nome />` repete o tema do
  código decorativo, e o favicon e o ícone de tela inicial são a mesma imagem de
  um `</>` com circuitos, ilegível a 16 px e igual para todo deploy.

Esta spec substitui, quando concluída: spec 001, RF-06 (percentual e barra) e
RF-07 (estatísticas); spec 004, RF-02 (hero no celular), RF-07 (barras de
habilidade), RF-14 (rodapé fixo) e RF-20 (ícone da aba); spec 007, RF-05 (ícone
de tela inicial).

## 2. Objetivos

- Mostrar no primeiro olhar, sem rolar, quem é a pessoa, o que faz, onde está,
  se está disponível e o caminho para os projetos.
- Trocar a autoavaliação em porcentagem por habilidades provadas pelos projetos
  publicados.
- Dar a cada projeto o endereço no ar, o código e um estudo de caso curto.
- Tirar da página todo texto, número e link fixo no template: o que aparece vem
  do Admin ou é contado dos dados.
- Dar ao site uma marca própria (logo, favicon e ícone de tela inicial) que
  sai do nome cadastrado, para quem clona o template não editar imagem.

## 3. Não-objetivos

- **Tema claro** e troca de tokens de cor, fonte ou espaçamento.
- **Conteúdo das seções Sobre e Contato**: mudam só o rótulo e a posição de
  Sobre; o formulário de contato fica como está (specs 002 e 005).
- **Página de detalhe por projeto**: o estudo de caso fica no cartão.
- **Limite automático de projetos**: o Admin decide quais publica e em que
  ordem.
- **Manifesto de PWA** e ícones de Android: o portfólio não é um app
  instalável.
- **Versão em inglês** do site e dados estruturados (spec 007, não-objetivos).

## 4. Personas

- **Quem avalia:** As a recrutador ou líder técnico que abre o link pelo
  celular, I want ver em segundos a função, a disponibilidade e um projeto com
  o código e a versão no ar, so that eu decida se a pessoa segue no processo.
- **Quem clona o template:** As a quem publica o próprio portfólio, I want que
  o hero, as habilidades, o rodapé e os ícones saiam do que eu cadastro no
  Admin, so that eu não edite template nem imagem para ter um site meu.
- **Quem navega por teclado ou leitor de tela:** As a visitante sem mouse, I
  want os filtros, os estudos de caso e os links com nome e estado anunciados,
  so that eu use a página como qualquer outra pessoa.

## 5. Requisitos funcionais e critérios de aceite

### Hero

### RF-01 — Hero sem saudação, sem código decorativo e sem dado fixo

- **Given** um `Perfil` cadastrado
  **When** a home abre
  **Then** o `<h1>` traz o `nome`, seguido do `cargo` e da `bio_curta`; não há
  "Olá, eu sou", bloco de código decorativo nem indicador "Explorar".
- **Given** o `home.html`
  **When** se procura cargo, tecnologia ou frase de apresentação escritos no
  template
  **Then** nada é encontrado: todo texto do hero vem do `Perfil` ou dos dados.

### RF-02 — Selo de disponibilidade

- **Given** `status_trabalho` e `localizacao` preenchidos
  **When** a home abre
  **Then** acima do nome aparece um selo com os dois, separados por "·".
- **Given** só `status_trabalho` preenchido
  **When** a home abre
  **Then** o selo mostra só o status, sem separador.
- **Given** `status_trabalho` vazio
  **When** a home abre
  **Then** não há selo.

### RF-03 — Ações do hero

**Superseded by** adendo, RF-24.

- **Given** a home aberta
  **When** o visitante ativa "Ver projetos"
  **Then** a página vai à seção Projetos.
- **Given** `link_github`, `link_linkedin` e `curriculo` do `Perfil`
  **When** a home abre
  **Then** ao lado de "Ver projetos" aparece um link de ícone para cada campo
  preenchido (GitHub e LinkedIn em nova aba, currículo como download), com nome
  acessível ("GitHub", "LinkedIn", "Baixar currículo"); campo vazio não gera
  link, nunca `href="None"` nem erro 500.
- **Given** a home aberta
  **When** o visitante ativa "ou entre em contato"
  **Then** a página vai à seção de contato.

### RF-04 — Foto no hero

**Superseded by** adendo, RF-25, no tamanho da foto no celular, e RF-26, no recorte.

- **Given** a home em tela larga (acima de 768 px)
  **When** a página abre
  **Then** a foto do perfil fica à direita do texto, em proporção 4:5.
- **Given** a home no celular (até 768 px)
  **When** a página abre
  **Then** a foto aparece redonda, acima do selo, e o texto fica centralizado.
- **Given** o perfil sem foto
  **When** a home abre
  **Then** aparece a foto de reserva `default_perfil.webp` (spec 004, RF-09),
  com o mesmo texto alternativo.

### RF-05 — Só números que os dados comprovam

- **Given** `anos_experiencia` maior que zero e projetos cadastrados
  **When** a home abre
  **Then** o hero mostra "N+ anos de experiência" e "N projetos publicados",
  este contado dos registros de `Projeto`, com singular para 1 ("1 ano", "1
  projeto publicado").
- **Given** `anos_experiencia` igual a zero, ou nenhum projeto
  **When** a home abre
  **Then** o número correspondente some; sem nenhum dos dois, a linha de números
  não aparece.
- **Given** a seção Sobre
  **When** a home abre com `anos_experiencia` maior que zero
  **Then** o selo da foto mostra "N+ anos de experiência"; com zero, não há
  selo.
- **Given** o Admin
  **When** se procura o cadastro de estatísticas
  **Then** ele não existe mais: o modelo `Estatistica` sai do projeto.

### RF-06 — Hero da altura do conteúdo

**Superseded by** adendo, RF-25, na primeira tela do celular.

- **Given** a home a 1280 x 800 px
  **When** a página abre
  **Then** o topo da seção Projetos aparece na primeira tela.
- **Given** a home a 390 x 844 px
  **When** a página abre
  **Then** o nome, o selo e o botão "Ver projetos" ficam na primeira tela, sem
  rolagem horizontal.

### Ordem e rótulos

### RF-07 — Projetos logo depois do hero

- **Given** a home
  **When** a página abre
  **Then** as seções seguem a ordem Hero, Projetos, Sobre, Habilidades,
  Contato, e o menu (desktop e celular) segue a mesma ordem; as âncoras
  (`#projects`, `#about`, `#skills`, `#contact`) não mudam.

### RF-08 — Rótulos novos acima dos títulos

- **Given** as seções da home
  **When** a página abre
  **Then** o rótulo em caixa alta de cada uma é "Quem sou" (Sobre), "Estudos de
  caso" (Projetos), "Com o que trabalho" (Habilidades) e "Próximo passo"
  (Contato); os títulos das seções não mudam.

### Projetos

### RF-09 — Versão no ar e código

- **Given** um projeto com endereço da versão no ar e com `link_github`
  **When** a home abre
  **Then** o cartão mostra "Ver online" e "Código", cada um em nova aba, com
  `rel="noopener noreferrer"` e um nome acessível que inclui o título do
  projeto.
- **Given** um projeto com só um dos dois endereços
  **When** a home abre
  **Then** só o link correspondente aparece; sem nenhum, o cartão não tem linha
  de ações.

### RF-10 — Estudo de caso no cartão

- **Given** um projeto com algum dos campos "Problema", "Meu papel", "Decisão
  técnica" e "Resultado" preenchidos
  **When** a home abre
  **Then** o cartão traz um "Como foi feito" fechado, que ao ser aberto mostra
  só os campos preenchidos, cada um com o seu título.
- **Given** um projeto com os quatro campos vazios
  **When** a home abre
  **Then** o cartão não tem "Como foi feito".
- **Given** o "Como foi feito"
  **When** o visitante usa o teclado ou o leitor de tela
  **Then** ele abre e fecha com Enter ou Espaço e anuncia se está aberto
  (elemento nativo de abrir e fechar).

### Habilidades

### RF-11 — Uma tecnologia por chip, agrupada por nível

- **Given** categorias de habilidade com habilidades
  **When** a home abre
  **Then** cada categoria vira um bloco com o nome dela, e dentro dele as
  habilidades aparecem como chips agrupados por nível, nesta ordem: "Uso no dia
  a dia", "Já usei em projeto", "Estudando"; nível sem habilidade não aparece.
- **Given** qualquer habilidade
  **When** a home abre
  **Then** não há porcentagem, barra de progresso nem opção no `Perfil` para
  mostrá-las.

### RF-12 — Chip com a contagem de projetos

- **Given** uma habilidade ligada a uma tecnologia usada por N projetos (N
  maior que zero)
  **When** a home abre
  **Then** o chip mostra "· N projetos" ("· 1 projeto" no singular) e é um
  botão.
- **Given** uma habilidade sem tecnologia ligada, ou com tecnologia que nenhum
  projeto usa
  **When** a home abre
  **Then** o chip mostra só o nome e não é interativo.

### RF-13 — Clique no chip filtra os projetos

- **Given** um chip com projetos
  **When** o visitante o ativa
  **Then** a seção Projetos passa a mostrar só os projetos com aquela
  tecnologia, o filtro de categoria volta a "Todos", o chip fica marcado
  (`aria-pressed="true"`), a região de status anuncia "Mostrando N projetos com
  <tecnologia>" e a página rola até Projetos, sem animação quando o sistema pede
  movimento reduzido.
- **Given** o filtro por tecnologia ativo
  **When** o visitante ativa "Limpar filtro", o mesmo chip de novo ou um filtro
  de categoria
  **Then** o filtro por tecnologia sai, o chip desmarca e a lista volta a
  seguir só a categoria.

### RF-14 — Sem faixa de logos

- **Given** a seção Habilidades
  **When** a home abre
  **Then** não há a faixa de ícones de tecnologia sem nome visível.

### Rodapé

### RF-15 — Rodapé lido do perfil

- **Given** o `Perfil` com `bio_curta`, `link_github` e `link_linkedin`
  **When** a home abre
  **Then** o rodapé mostra a `bio_curta` como frase e só os links de GitHub e
  LinkedIn do perfil, em nova aba.
- **Given** a `bio_curta` vazia, ou os dois links vazios
  **When** a home abre
  **Then** some a frase, ou o bloco de redes inteiro, sem link quebrado.
- **Given** qualquer página que estende o `base.html`
  **When** ela abre
  **Then** não há link para Facebook, Instagram, X ou TikTok.

### Marca

### RF-16 — Logo com monograma

- **Given** o `Perfil` com `nome`
  **When** qualquer página que estende o `base.html` abre
  **Then** o logo do menu e o do rodapé mostram um monograma com as iniciais e,
  ao lado, o nome; o monograma é decorativo para o leitor de tela, e o nome
  acessível do link começa pelo nome visível (spec 004, RF-11).
- **Given** um nome
  **When** as iniciais são calculadas
  **Then** são a primeira letra da primeira e da última palavra, em maiúsculas
  e com acento ("Érica de Souza" vira "ÉS"); nome de uma palavra dá uma letra;
  sem nome, vale "Seu Nome" (o padrão atual do template).

### RF-17 — Favicon com as iniciais

- **Given** o `Perfil` com `nome`
  **When** o navegador pede o ícone da aba
  **Then** recebe um SVG com as iniciais do RF-16 em ciano sobre o fundo do
  site, legível a 16 px.
- **Given** nenhum `Perfil`
  **When** o navegador pede o ícone da aba
  **Then** recebe o `favicon.webp` atual, que segue declarado como reserva para
  navegador sem suporte a SVG.

### RF-18 — Ícone de tela inicial com as iniciais

- **Given** o `Perfil` com `nome`
  **When** o celular pede o ícone de tela inicial
  **Then** recebe um PNG opaco de 180 x 180 px com o monograma.
- **Given** o `nome` alterado no Admin
  **When** o ícone é pedido de novo
  **Then** ele reflete as novas iniciais.
- **Given** nenhum `Perfil`
  **When** o celular pede o ícone
  **Then** recebe o `apple-touch-icon.png` atual.

### Dados e Admin

### RF-19 — Campos novos no Admin

- **Given** o Admin de `Projeto`
  **When** se edita um projeto
  **Then** há o endereço da versão no ar e os quatro campos do estudo de caso,
  todos opcionais e com texto de ajuda.
- **Given** o Admin de `Habilidade`
  **When** se edita uma habilidade
  **Then** há o nível (as três opções do RF-11) e a tecnologia ligada
  (opcional), e não há mais o progresso de 0 a 100; o `Perfil` não tem mais a
  opção de mostrar o progresso.

### RF-20 — Dados existentes migram sem perda

- **Given** um banco com habilidades, perfil, projetos e estatísticas
  **When** as migrações rodam
  **Then** toda habilidade continua cadastrada, com o nível tirado do progresso
  antigo (80 ou mais: "Uso no dia a dia"; de 50 a 79: "Já usei em projeto";
  abaixo de 50: "Estudando") e ligada à tecnologia de mesmo nome, quando
  houver uma (sem diferença de maiúsculas); as estatísticas são removidas com o
  modelo.

### RF-21 — Dados de demonstração atualizados

- **Given** o comando `semear_dados_demo` (só com `DEBUG=True`)
  **When** ele roda num banco vazio
  **Then** cria habilidades com nível e tecnologia ligada, projetos com
  endereço da versão no ar e estudo de caso de exemplo, e nenhuma estatística.

### Sem regressão

### RF-22 — Regras da spec 004 mantidas

- **Given** o perfil e os projetos com todo campo opcional vazio
  **When** a home abre
  **Then** responde 200, sem `href="None"` e sem `ValueError` de arquivo
  ausente.
- **Given** a home
  **When** ela abre com o menu do celular, o modo demonstração (spec 005) e os
  metadados da spec 007
  **Then** o menu inerte, o contraste, o bloco de movimento reduzido no fim do
  `styles.css`, as fontes locais, as páginas de erro e os metadados seguem como
  descritos nas specs 004, 005 e 007.

## 6. Requisitos não-funcionais

### RNF-01 — Sem dependência nova

O redesenho usa o que o projeto já tem: Django, Pillow (o ícone PNG do RF-18) e
JavaScript sem biblioteca. Nenhum pacote novo no `pyproject.toml`.

### RNF-02 — Acessibilidade

A home passa sem violação no axe-core, a 390 e a 1280 px. Toda ação tem foco
visível e alvo de pelo menos 44 x 44 px (os chips, 40 px de altura com o
espaçamento completando 44); o texto usa os tokens de contraste da spec 004
(`--color-gray-400` ou mais claro); chips, selo e filtros têm borda, para
continuarem visíveis em alto contraste (`forced-colors: active`).

### RNF-03 — Sem JavaScript, nada se perde

Sem JavaScript, a home mostra todos os projetos, todos os chips e todo estudo
de caso (abre e fecha sem script); só o filtro deixa de agir.

### RNF-04 — CSP e desempenho mantidos

Nenhum `<script>` nem estilo inline novo que exija afrouxar o
`CONTENT_SECURITY_POLICY`. A foto do hero é a maior imagem da primeira tela:
carrega sem `loading="lazy"`, com largura e altura declaradas. O favicon SVG
tem menos de 2 KiB, e os dois ícones gerados respondem com cabeçalho de cache.
Os limites do Lighthouse CI seguem os atuais.

### RNF-05 — Documentado para quem clona

README (nos dois idiomas), `CLAUDE.md`, `docs/referencia/arquitetura.md` e
`docs/referencia/interface-e-acessibilidade.md` descrevem os campos novos, a
ordem das seções, a marca gerada do nome e a remoção de `Estatistica` e do
progresso.

## 7. Perguntas em aberto / decisões resolvidas

**Perguntas em aberto:** nenhuma.

**Decisões resolvidas:**

1. **Foto no hero, não cartão de stack** (decisão do mantenedor, 2026-11-17).
   Um cartão "Stack atual" ao lado do nome foi descartado porque repete a seção
   Habilidades; a foto dá rosto ao nome no primeiro olhar e já existe no
   `Perfil`. A foto também aparece na seção Sobre, que não muda nesta spec.
2. **Habilidades ligadas aos projetos, sem unificar modelos** (decisão do
   mantenedor, 2026-11-17). Chips sem ligação aos projetos foram descartados
   por não provarem nada; juntar `Habilidade` e `Tecnologia` num modelo só foi
   descartado por exigir uma migração maior sem ganho visível para quem
   avalia.
3. **Nível em palavras, em três degraus fixos** (decisão do mantenedor,
   2026-11-17). Porcentagem ("Python 90%") e nota de 1 a 5 foram descartadas:
   sugerem precisão que não existe. Os três degraus dizem o que quem avalia
   quer saber: o que a pessoa usa hoje, o que já usou e o que está aprendendo.
4. **Números só calculados; `Estatistica` removido** (decisão do mantenedor,
   2026-11-17). Manter o modelo só para o selo da seção Sobre foi descartado: o
   texto livre permite número que a página não sustenta, e os anos de
   experiência já são um campo do `Perfil`.
5. **Projetos logo depois do hero** (decisão do mantenedor, 2026-11-17). A ação
   principal do hero leva aos projetos, e quem avalia entra por eles; a seção
   Sobre desce uma posição sem mudar.
6. **Rótulos em caixa alta mantidos, com texto novo** (decisão do mantenedor,
   2026-11-17). O rótulo faz parte da identidade visual do site; o texto passa
   a dizer o que a seção oferece ("Estudos de caso") em vez de um convite
   genérico ("Meu trabalho").
7. **Marca do monograma** (decisão do mantenedor, 2026-11-17). O nome sozinho
   com um ponto ciano foi descartado por deixar o favicon sem ligação com o
   logo; uma inicial só no favicon foi descartada porque identifica menos a
   pessoa que as duas.

## 8. Testes

### RF-23 — A suíte cobre o redesenho

A suíte (pytest, sem rede) cobre: o hero sem saudação, sem código decorativo e
sem texto fixo (RF-01); o selo, os links e os números com cada campo vazio e
preenchido (RF-02, RF-03, RF-05); a ordem das seções e do menu e os rótulos
(RF-07, RF-08); os links e o estudo de caso do cartão (RF-09, RF-10); o
agrupamento por nível, a contagem e o chip não interativo (RF-11, RF-12); o
rodapé sem redes fixas (RF-15); o cálculo das iniciais, inclusive acento,
nome de uma palavra e nome vazio (RF-16); o favicon SVG e o ícone PNG, com e
sem perfil, e a troca de iniciais (RF-17, RF-18); a migração dos níveis e da
ligação com a tecnologia (RF-20); e o comando de demonstração (RF-21). O filtro
por chip (RF-13) é conferido no `main.js` lido como texto, como os demais
comportamentos do `test_interface.py`.

## Adendo (2026-11-17): hero com duas ações e foto maior no celular

> Status do adendo: concluído (2026-11-17). O texto acima é o aprovado em 2026-11-17 e fica como
> está; o adendo acrescenta requisitos, com a numeração continuando a dele.

**Contexto.** O hero do RF-03 tem cinco ações: "Ver projetos", três links de ícone
(GitHub, LinkedIn e currículo) e "ou entre em contato". Três delas repetem o que vem
mais abaixo: GitHub e LinkedIn estão nos cartões de Contato e no rodapé, o currículo
tem botão em Sobre, e Contato está no menu. O ícone de download, sem texto, não diz que
baixa o currículo. No celular as ações ocupam três linhas (botão, ícones e link), e a
foto ficou com 112 px para o nome, o selo e "Ver projetos" caberem na primeira tela
(RF-06). O círculo do celular recorta o centro da foto 4:5 e corta a parte de cima, onde
fica a cabeça. No desktop a foto 4:5 aparece inteira na moldura 4:5: o espaço acima da
cabeça é o da própria foto.

**Objetivos do adendo.**

- Uma escolha clara no hero: ver os projetos ou entrar em contato.
- Foto maior no celular, com o nome, o selo e as duas ações na primeira tela.
- Recorte da foto que preserve o alto da cabeça.
- Orientar no Admin o formato da foto que o hero espera.

**Não-objetivos do adendo.**

- Tirar GitHub, LinkedIn ou o currículo do site: eles seguem no Contato, no rodapé e
  em Sobre.
- Ponto focal por foto, recorte no servidor ou edição de imagem no Admin.
- Mudar o desktop além das ações: a foto segue com 340 px, em 4:5, à direita.

**Personas do adendo.**

- Como **quem avalia o portfólio**, quero ver os projetos ou falar com a pessoa sem
  escolher entre cinco ícones.
- Como **um visitante no celular**, quero ver o rosto de quem fez o site, sem a cabeça
  cortada.
- Como **quem clona o projeto**, quero saber que formato de foto enviar no Admin.

### RF-24 — Duas ações no hero

- **Given** a home aberta
  **When** o visitante ativa "Ver projetos"
  **Then** a página vai à seção Projetos.
- **Given** a home aberta
  **When** o visitante ativa "Entre em contato"
  **Then** a página vai à seção de contato. O link é um botão de contorno, da mesma
  altura de "Ver projetos": ao lado dele no desktop e embaixo, em largura total, no
  celular.
- **Given** `link_github`, `link_linkedin` e `curriculo` do `Perfil` preenchidos
  **When** a home abre
  **Then** o hero não tem link para eles; GitHub e LinkedIn seguem nos cartões de
  Contato e no rodapé, e o currículo no botão de Sobre.

### RF-25 — Foto de 160 px no celular

- **Given** a home no celular (até 768 px)
  **When** a página abre
  **Then** a foto aparece redonda, com 160 px, acima do selo, e o texto fica
  centralizado.
- **Given** a home a 390 x 844 px
  **When** a página abre
  **Then** o nome, o selo, "Ver projetos" e "Entre em contato" ficam na primeira tela,
  sem rolagem horizontal.

### RF-26 — Recorte que preserva a cabeça

- **Given** uma foto 4:5 no celular
  **When** o círculo a recorta
  **Then** o recorte parte do alto da foto: o que sobra sai de baixo, nunca do alto da
  cabeça.
- **Given** uma foto de outra proporção, no desktop ou no celular
  **When** a moldura a recorta
  **Then** o recorte também parte do alto.
- **Given** o campo de foto do `Perfil` no Admin
  **When** a equipe o edita
  **Then** o texto de ajuda pede um retrato vertical 4:5 com espaço acima da cabeça e
  avisa que o celular mostra a foto num círculo.

**Decisões resolvidas do adendo.**

1. **Duas ações com texto** (2026-11-17). Ficaram as duas ações, em vez das cinco do
   RF-03 e de "Ver projetos" com GitHub, LinkedIn e Currículo como links com rótulo:
   uma escolha clara e espaço para a foto no celular. O GitHub passa a ficar a um
   clique a mais, no Contato e no rodapé.
2. **160 px, não 200 px** (2026-11-17). Com 200 px, "Entre em contato" sai da primeira
   tela de um celular comum, que mostra uns 704 px de página abaixo da barra do
   navegador; com 160 px, as duas ações ficam nela.
3. **O espaço acima da cabeça no desktop vem da foto** (2026-11-17). A foto 4:5 aparece
   inteira na moldura 4:5, então nenhuma regra de CSS cria respiro acima da cabeça sem
   uma faixa vazia ou um corte. O texto de ajuda do Admin orienta o envio de um retrato
   com esse espaço.

### RF-27 — A suíte cobre o adendo

- Com GitHub, LinkedIn e currículo preenchidos, o hero tem só "Ver projetos" (para
  `#projects`) e "Entre em contato" (para `#contact`), e nenhum link de ícone; os links
  seguem no Contato e no rodapé.
- No `styles.css`, a foto do celular tem 160 px, e o recorte da foto parte do alto.
- O texto de ajuda do campo de foto cita a proporção 4:5 e o espaço acima da cabeça.
