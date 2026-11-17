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

# Requisitos — Descoberta da demo pelos buscadores e pelas redes sociais

## 1. Contexto e problema

A demo está no ar em `https://portfolio-dinamico.ryanmorais.com.br` (spec 006),
com o modo demonstração ligado (spec 005) e dados fictícios. O que um buscador
ou uma rede social lê dela hoje não diz que é uma demonstração:

- **Título e description vêm do `Perfil`.** O `<title>` e o `og:title` saem do
  `perfil.nome` com o sufixo fixo "| Desenvolvedor Full-Stack" do `base.html`, e
  a description sai do `perfil.bio_curta`. Na demo, o resultado é "Seu Nome |
  Desenvolvedor Full-Stack", com a bio fictícia: o resultado de busca parece o
  portfólio de uma pessoa, não o template de código aberto.
- **O cartão de compartilhamento mostra a foto do perfil.** O `og:image` é a foto
  de banco de imagens cadastrada na demo, e não há `twitter:card`, então algumas
  redes montam um cartão pequeno ou nenhum.
- **Sem endereço canônico.** Não há `<link rel="canonical">` nem `og:url`. O
  endereço absoluto do `og:image` é montado a partir do `Host` do pedido (spec
  004, RF-20).
- **Sem `sitemap.xml` e sem `robots.txt` da origem.** `/sitemap.xml` responde
  404. Em `/robots.txt` responde só o arquivo gerenciado pelo proxy da Cloudflare
  (sinais de conteúdo e bloqueio de robôs de treino de IA), sem a linha
  `Sitemap:`.
- **Sem `security.txt`.** `/.well-known/security.txt` (RFC 9116) responde 404. O
  canal privado de relato existe (avisos de segurança do GitHub e `SECURITY.md`),
  mas quem procura o contato pelo padrão não o encontra no site.
- **Sem ícone de tela inicial.** O site só declara o `favicon.webp`; ao salvar a
  página na tela inicial do celular, o sistema usa uma captura reduzida.

## 2. Objetivos

- Fazer a demo aparecer nos buscadores e nas redes sociais como a demonstração
  do template, com título, description e imagem que dizem isso.
- Dar à demo um endereço canônico vindo da configuração, nunca do `Host` do
  pedido.
- Servir `robots.txt` e `sitemap.xml` da própria aplicação, que convivem com o
  bloco gerenciado do proxy.
- Publicar o contato de segurança em `/.well-known/security.txt` na demo, com um
  teste que avisa antes de o `Expires` vencer.
- Dar ao site um ícone de tela inicial.
- Para quem clona: o mesmo endereço canônico, `robots.txt` e `sitemap.xml` no
  próprio deploy, sem herdar nada que identifique a demo do template.

## 3. Não-objetivos

- **Dados estruturados** (JSON-LD, `schema.org/Person`).
- **Versão em inglês do site** e `hreflang`: o site é em português.
- **Política de robôs de IA no código.** O bloqueio de robôs de treino fica com o
  proxy (decisão resolvida 4); o `robots.txt` da origem não repete a lista.
- **Mudar os dados fictícios da demo.** O hero e as seções seguem mostrando o
  conteúdo cadastrado; só os metadados identificam a demonstração.
- **Enviar o sitemap a buscadores.** É operação de quem publica, fora do código.
- **`/security.txt` na raiz** (local antigo, que a RFC 9116 aceita só como
  redirecionamento).

## 4. Personas

- **Quem busca um template:** As a quem procura um portfólio em Django para
  estudar ou adaptar, I want que o resultado de busca e o cartão compartilhado
  digam que é a demonstração de um template de código aberto, so that eu saiba o
  que vou abrir.
- **Quem clona e publica:** As a quem publica o próprio portfólio a partir do
  template, I want canonical, `robots.txt` e `sitemap.xml` ligados por uma
  variável, so that meu site seja indexado com o meu endereço e o meu nome, sem
  metadados da demo.
- **Quem pesquisa segurança:** As a quem achou uma vulnerabilidade na demo, I want
  o contato em `/.well-known/security.txt`, so that eu relate em privado sem
  procurar o repositório.

## 5. Requisitos funcionais e critérios de aceite

### Endereço público

### RF-01 — Chave `URL_PUBLICA` no `.env`

- **Given** `URL_PUBLICA=https://exemplo.com.br` (com ou sem a barra final)
  **When** a aplicação sobe
  **Then** o endereço público vale `https://exemplo.com.br`, sem a barra final,
  e é a única fonte do endereço absoluto em canonical, `og:url`, `og:image`,
  `robots.txt`, `sitemap.xml` e `security.txt`.
- **Given** `URL_PUBLICA` com valor que não começa por `http://` ou `https://`,
  ou com caminho, query ou fragmento
  **When** a aplicação sobe
  **Then** a subida falha com `ValueError` que cita a chave e o valor esperado,
  como a falta de `SECRET_KEY`.
- **Given** `URL_PUBLICA` vazia ou ausente
  **When** a aplicação sobe
  **Then** ela sobe normalmente, e os RFs abaixo descrevem o que fica de fora.

### Metadados da página

### RF-02 — Canonical e `og:url` da home

- **Given** `URL_PUBLICA` definida
  **When** a home é pedida, com ou sem query string
  **Then** o `<head>` traz `<link rel="canonical" href="<URL_PUBLICA>/">` e
  `<meta property="og:url" content="<URL_PUBLICA>/">`, sem a query string.
- **Given** `URL_PUBLICA` vazia
  **When** a home é pedida
  **Then** o `<head>` não traz canonical nem `og:url`.
- **Given** uma página de erro (400, 403, 404, 500)
  **When** é servida
  **Then** não traz canonical nem `og:url`.

### RF-03 — Título, description e `og:*` da demo

- **Given** `MODO_DEMONSTRACAO=True`
  **When** a home é pedida
  **Then** o `<title>` e o `og:title` são "Demonstração | Portfólio em Django de
  código aberto", e a `description` e o `og:description` são "Demonstração do
  portfolio-dinamico, um portfólio de desenvolvedor em Django com Admin,
  formulário de contato anti-spam e código aberto no GitHub. Os dados são
  fictícios.", qualquer que seja o `Perfil` cadastrado.
- **Given** `MODO_DEMONSTRACAO=False`
  **When** a home é pedida
  **Then** título, description e `og:*` seguem vindo do `Perfil`, como hoje
  (RF-09).

### RF-04 — Imagem do cartão e `twitter:card`

- **Given** `MODO_DEMONSTRACAO=True`
  **When** a home é pedida
  **Then** o `og:image` é a imagem de divulgação do template (1280 × 640), em
  endereço absoluto, com `og:image:width`, `og:image:height` e `og:image:alt`, e
  o `twitter:card` é `summary_large_image`.
- **Given** `MODO_DEMONSTRACAO=False` e o `Perfil` com foto
  **When** a home é pedida
  **Then** o `og:image` é a foto do perfil em endereço absoluto, e o
  `twitter:card` é `summary_large_image`.
- **Given** `MODO_DEMONSTRACAO=False` e o `Perfil` sem foto
  **When** a home é pedida
  **Then** não há `og:image`, e o `twitter:card` é `summary`.
- **Given** um `og:image` em endereço absoluto
  **When** `URL_PUBLICA` está definida
  **Then** o endereço parte dela; vazia, parte do esquema e do `Host` do pedido,
  como hoje (spec 004, RF-20).

### RF-05 — Ícone de tela inicial

**Superseded by** 008-redesenho-da-home, RF-18.

- **Given** qualquer página que estende o `base.html`
  **When** é servida
  **Then** o `<head>` declara um `<link rel="apple-touch-icon">` para um PNG de
  180 × 180, opaco, feito a partir do ícone do site.

### Arquivos de descoberta

### RF-06 — `robots.txt` da aplicação

- **Given** um pedido a `/robots.txt`
  **When** a aplicação responde
  **Then** devolve 200, `text/plain; charset=utf-8`, com `User-agent: *` e
  `Allow: /`.
- **Given** `URL_PUBLICA` definida
  **When** `/robots.txt` é pedido
  **Then** o arquivo termina com `Sitemap: <URL_PUBLICA>/sitemap.xml`; vazia, não
  há linha `Sitemap:`.
- **Given** qualquer valor de `ADMIN_URL`
  **When** `/robots.txt` é pedido
  **Then** o arquivo não cita o caminho do Admin (um `Disallow` revelaria o
  caminho ofuscado, spec 003).

### RF-07 — `sitemap.xml` com a home

- **Given** `URL_PUBLICA` definida
  **When** `/sitemap.xml` é pedido
  **Then** devolve 200, `application/xml`, um sitemap válido (protocolo
  sitemaps.org 0.9) com uma única `<loc>`: `<URL_PUBLICA>/`, igual ao canonical.
- **Given** `URL_PUBLICA` vazia
  **When** `/sitemap.xml` é pedido
  **Then** devolve 404: sem endereço configurado, o sitemap não é montado a
  partir do `Host`.

### RF-08 — `security.txt` na demo

- **Given** `MODO_DEMONSTRACAO=True`
  **When** `/.well-known/security.txt` é pedido
  **Then** devolve 200, `text/plain; charset=utf-8`, com `Contact:` apontando
  para a criação de aviso de segurança no repositório
  (`<URL_REPOSITORIO>/security/advisories/new`), um único `Expires:` em ISO 8601,
  `Preferred-Languages: pt, en` e `Policy:` apontando para o `SECURITY.md` do
  repositório.
- **Given** `MODO_DEMONSTRACAO=True` e `URL_PUBLICA` definida
  **When** `/.well-known/security.txt` é pedido
  **Then** o arquivo traz `Canonical: <URL_PUBLICA>/.well-known/security.txt`;
  com `URL_PUBLICA` vazia, não há linha `Canonical:`.
- **Given** `MODO_DEMONSTRACAO=False`
  **When** `/.well-known/security.txt` é pedido
  **Then** devolve 404: quem publica o próprio portfólio não herda o contato do
  repositório do template.

### Sem regressão

### RF-09 — Sem `URL_PUBLICA` nem modo demonstração, a home segue igual

- **Given** `URL_PUBLICA` vazia e `MODO_DEMONSTRACAO=False`
  **When** a home é pedida
  **Then** título, description e `og:*` são os de hoje, e as únicas diferenças no
  `<head>` são o `twitter:card` (RF-04) e o ícone de tela inicial (RF-05).

## 6. Requisitos não-funcionais

### RNF-01 — Sem dependência nova de runtime

O `pyproject.toml` não ganha dependência de runtime, e o `INSTALLED_APPS` só
ganha app se for do próprio Django.

### RNF-02 — Postura de segurança mantida

A CSP, o `Permissions-Policy` e os cabeçalhos da spec 003 valem também para
`robots.txt`, `sitemap.xml` e `security.txt`; nenhum template ganha `<script>`
ou estilo inline, e `DEBUG=False uv run python manage.py check --deploy` segue
sem aviso novo.

### RNF-03 — Endereço nunca vindo do pedido onde ele vira canônico

Canonical, `og:url`, `sitemap.xml`, a linha `Sitemap:` e o `Canonical:` do
`security.txt` saem só de `URL_PUBLICA`; nenhum deles é montado a partir do
`Host` ou do `X-Forwarded-*` do pedido.

### RNF-04 — Documentado para quem clona

`URL_PUBLICA` entra no `.env.example`, na tabela de variáveis do `CLAUDE.md` e
dos dois READMEs (mesma seção, nos dois idiomas) e no
`docs/referencia/configuracoes.md`. A mudança de sentido do `MODO_DEMONSTRACAO`
(além do formulário, os metadados e o `security.txt`) entra nos mesmos lugares.

## 7. Perguntas em aberto / decisões resolvidas

**Perguntas em aberto:** nenhuma.

**Decisões resolvidas:**

1. **A demo se identifica pelo `MODO_DEMONSTRACAO`** (decisão do mantenedor,
   2026-11-16). O modo já marca o deploy como demonstração pública do template
   (spec 005); estendê-lo aos metadados evita chave nova e não exige mudar os
   dados da demo. Trocar o `perfil.nome` no Admin foi descartado, porque o hero
   passaria a mostrar o aviso no lugar do nome; chaves próprias de título e
   description foram descartadas por serem duas variáveis a mais para um único
   deploy.
2. **Endereço público numa chave própria, `URL_PUBLICA`** (decisão do mantenedor,
   2026-11-16). Derivar do primeiro item do `ALLOWED_HOSTS` foi descartado: a
   ordem da lista passaria a ter um sentido implícito, frágil com `www` ou um
   segundo domínio.
3. **`security.txt` só com o modo demonstração** (decisão do mantenedor,
   2026-11-16). O contato é o do repositório do template; num deploy que não é a
   demo, ele apontaria para quem não responde por aquele site. O `Expires` fica
   fixo no repositório, e um teste falha 30 dias antes do vencimento.
4. **O `robots.txt` da origem convive com o gerenciado do proxy.** Com o
   `robots.txt` gerenciado ligado, a Cloudflare põe o bloco dela (sinais de
   conteúdo e bloqueio de robôs de treino) antes do conteúdo da origem, que segue
   valendo (comportamento conferido em 2026-11-16). Sem a Cloudflare na
   frente, vale só o da origem.
5. **Imagem de divulgação do template no cartão da demo** (decisão do
   mantenedor, 2026-11-16): a mesma imagem 1280 × 640 de `assets/`, que já serve
   de prévia social do repositório.

## 8. Testes

### RF-10 — A suíte cobre os arquivos e os metadados de descoberta

- **Given** a suíte (`uv run pytest`)
  **When** roda, sem rede
  **Then** cobre:
  - `URL_PUBLICA`: normalização da barra final, falha de subida com valor
    inválido e subida normal com ela vazia (RF-01);
  - canonical e `og:url` com e sem `URL_PUBLICA`, com query string na home e
    ausentes nas páginas de erro (RF-02);
  - título, description e `og:*` com o modo ligado e desligado (RF-03, RF-09);
  - `og:image` e `twitter:card` nos três casos e a origem do endereço absoluto
    (RF-04), e o ícone de tela inicial declarado e com 180 × 180 (RF-05);
  - `robots.txt` com e sem `URL_PUBLICA`, sem o caminho do Admin (RF-06);
  - `sitemap.xml` válido com uma `<loc>` igual ao canonical, e 404 sem
    `URL_PUBLICA` (RF-07);
  - `security.txt` só com o modo, os campos obrigatórios, `Contact:` em
    `https://`, um único `Expires`, e falha quando o `Expires` está a menos de
    30 dias ou a mais de 366 dias da data do teste (RF-08);
  - endereço canônico igual em todos os pontos e nunca vindo do `Host` (RNF-03).
