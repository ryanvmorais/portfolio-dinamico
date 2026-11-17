---
feature: Configuração e postura de segurança (settings, CSP, admin, deploy)
status: concluído
date: 2026-09-11
related:
  - 002-formulario-contato
origin: engenharia reversa do código existente (portfolio/settings.py)
---

# Design — Configuração e Segurança

## 1. Visão geral

Um único `portfolio/settings.py`, dividido em 5 blocos numerados por
comentário (ambiente/segredos, middlewares/apps, estáticos/mídia, segurança
avançada condicionada a `DEBUG`, serviços externos). Toda diferença entre dev
e produção é resolvida por variável de ambiente, nunca por um segundo arquivo
de settings.

## 2. Componentes

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| Bloco 1 (env/segredos) | `portfolio/settings.py`, bloco 1 | `SECRET_KEY`, `DEBUG`, `ADMIN_URL_PATH`, `ALLOWED_HOSTS` |
| `MIDDLEWARE` | `portfolio/settings.py`, bloco 2 | Ordem: Security → WhiteNoise → Session → Common → CSRF → Auth → Messages → XFrameOptions → CSP |
| Bloco 4 (cabeçalhos e HTTPS) | `portfolio/settings.py`, bloco 4 | HSTS, cookies seguros, SSL redirect — só com `DEBUG=False` |
| `django-csp` | `portfolio/settings.py`, bloco 4 (`CSP_*`) | Diretivas `CSP_*` (hoje o dicionário `CONTENT_SECURITY_POLICY` do django-csp 4, PR #78) |
| `portfolio/urls.py` | raiz | Monta `admin.site.urls` em `settings.ADMIN_URL_PATH` |
| `whitenoise` | `MIDDLEWARE` + `STORAGES["staticfiles"]` | Serve e comprime estáticos sem servidor dedicado |
| `.env.example` | raiz | Documenta cada variável exigida, sem valores reais |

## 3. Modelo de dados

Não aplicável — esta spec cobre configuração, não models.

## 4. Interfaces

Variáveis de ambiente consumidas por `settings.py` (documentadas em
`.env.example`):

| Variável | Padrão | Obrigatória |
|---|---|---|
| `SECRET_KEY` | — | Sim (levanta `ValueError` se ausente) |
| `DEBUG` | `False` | Não |
| `ADMIN_URL` | `admin/` | Não |
| `ALLOWED_HOSTS` | `*` (dev) / vazio (prod) | Recomendada em produção |
| `EMAIL_USER` / `EMAIL_PASS` | — | Só para o formulário de contato funcionar (spec 002) |

## 5. Decisões técnicas (ADRs)

### ADR-01 — Um único `settings.py` para dev e produção

- **Decisão:** sem `settings/base.py` + `settings/dev.py` + `settings/prod.py`
  (padrão comum em projetos maiores); tudo em um arquivo, ramificado por
  `if not DEBUG:`.
- **Alternativas:** múltiplos módulos de settings (por exemplo, um
  `settings_test.py` para os testes).
- **Porquê:** projeto de escala pequena, um único app — a divisão em módulos
  adicionaria indireção sem benefício proporcional.
- **Trade-off:** os testes rodam contra o mesmo `settings.py` de produção,
  então precisam neutralizar manualmente o que `DEBUG=False` ligaria
  (`disable_ssl_redirect`, ver spec 002) em vez de herdar de um settings de
  teste dedicado.

### ADR-02 — CSP com `'unsafe-inline'` em `style-src`, mas não em `script-src`

**Superseded by** adendo, ADR-05.

- **Decisão (corrigida em 2026-09-11):** `CSP_SCRIPT_SRC = ("'self'",)` — sem
  `'unsafe-inline'`. `CSP_STYLE_SRC` mantém `'unsafe-inline'` porque
  `home.html` usa 2 atributos `style=""` inline (barra de progresso de
  habilidades, com largura dinâmica vinda do banco). (Hoje `script-src` e
  `style-src` do dicionário `CONTENT_SECURITY_POLICY`, PR #78; a decisão segue
  a mesma.)
- **Porquê:** antes da correção, `script-src` também tinha `'unsafe-inline'`
  sem necessidade real (nenhum `<script>` inline em nenhum template) — isso
  anulava boa parte do valor do CSP como defesa contra XSS.
- **Alternativa não adotada:** nonce por request resolveria também o `style-src`, mas
  exigiria mover a largura da barra de progresso para uma custom property CSS
  lida via `data-*` — fora do escopo da modernização de 2026-09-11.

### ADR-03 — Ofuscação da URL do Admin como defesa em profundidade

- **Decisão:** `ADMIN_URL_PATH` via `.env`, sem valor fixo `admin/` em
  produção. Desde 2026-11-16, o valor é normalizado:
  `(os.getenv("ADMIN_URL", "").strip().strip("/") or "admin") + "/"`.
- **Alternativas:** (a) ler o valor cru, como até 2026-11-16; (b) recusar na
  subida o valor sem a barra no fim.
- **Porquê:** reduz o volume de tentativas de brute-force automatizado (bots
  que varrem `/admin/` por padrão), sem substituir autenticação real. Com (a),
  a linha vazia montava o painel na raiz e `painel` sem barra gerava
  `painellogin/`; (b) derruba um deploy por um detalhe de conserto óbvio.
  Normalizar aceita as formas comuns e não deixa caminho quebrado.
- **Trade-off:** segurança por obscuridade — não impede um atacante
  direcionado que descubra a URL por outro meio (linkado, vazado em log,
  etc.). Complementar, não substituto, de uma senha forte. Um caminho com
  barra no meio (`a/b/`) passa como está.

### ADR-04 — Sem 2FA no Admin

- **Decisão:** autenticação do Admin é usuário/senha padrão do Django.
- **Porquê:** escopo e público do projeto (portfólio pessoal, um único
  administrador) não justificam a complexidade de `django-two-factor-auth` +
  `django-axes` — decisão explícita de escala, não descuido.

## 6. Impacto e dependências

- `django-csp`, `whitenoise`, `python-dotenv`, `certifi` são as dependências
  diretas desta spec (declaradas em `pyproject.toml`).
- Qualquer novo `<script>`/`<style>` inline em template exige revisar
  `CSP_SCRIPT_SRC`/`CSP_STYLE_SRC` (hoje `script-src`/`style-src` do
  `CONTENT_SECURITY_POLICY`, PR #78) antes de shippar — regressão silenciosa
  senão (o CSP bloqueia sem erro visível no servidor, só no console do
  navegador).

## 7. Estratégia de testes

Não há teste automatizado desta spec na suíte `pytest` — a verificação é
manual (`manage.py check --deploy` + auditoria de segurança de 2026-09-11:
`pip-audit`, `semgrep`, `detect-secrets`, revisão OWASP). `disable_ssl_redirect`
(spec 002) existe justamente porque os testes de view rodam contra este
`settings.py` sem um settings de teste dedicado.

Exceção: a normalização do `ADMIN_URL` (RF-06, ADR-03) tem teste próprio
(`TestCaminhoDoAdmin` em `app_portfolio/tests.py`), que carrega uma cópia
avulsa do `settings.py` com cada valor da variável.

## Adendo (2026-11-17): CSP sem estilo inline

> Status do adendo: concluído (2026-11-17). Desenha os RF-09 a RF-11 do adendo do `requirements.md`. O
> texto acima fica como está; os ADRs continuam a numeração.

### Visão geral da abordagem do adendo

O honeypot é o último estilo inline da home. Ele passa a ser escondido por uma classe do
`styles.css`, e com isso o `'unsafe-inline'` sai do `style-src`. Nenhum template ganha
nonce nem hash: a política fica `style-src 'self'`, igual ao `script-src`. Um teste lê os
templates como texto e falha se um `style=` ou um `<style>` voltar, como o
`test_comentarios_templates.py` já faz com os comentários.

### Componentes do adendo

#### `templates/home.html`

- A `<div>` do honeypot troca o `style="display:none;"` pela classe
  `contact__honeypot`. O `aria-hidden="true"`, o `tabindex="-1"` e o
  `autocomplete="off"` do campo continuam.

#### `static/css/styles.css`

- Regra nova junto das do formulário de contato: `.contact__honeypot { display: none; }`.
  O `display: none` tira o campo da tela, da ordem do Tab e da árvore de
  acessibilidade de uma vez.

#### `portfolio/settings.py`

- `"style-src": [SELF]`, e o comentário da CSP diz que nenhum template tem estilo nem
  script inline. O `UNSAFE_INLINE` sai do import, porque nenhuma diretiva o usa mais.

#### `app_portfolio/test_estilo_inline.py` (módulo novo)

- Lê todos os templates do projeto como texto, sem banco nem cliente HTTP, e falha se
  algum tiver atributo `style=` ou elemento `<style>`.
- Confere no `styles.css` a regra `.contact__honeypot` com `display: none`.
- Renderiza a home e confere que o campo `honeypot` está dentro do elemento com a classe
  e que o HTML entregue não tem `style=`.

#### `app_portfolio/tests.py`

- O `test_home_envia_a_csp` passa a esperar `style-src` igual a `["'self'"]`.

### Interfaces do adendo

O cabeçalho `Content-Security-Policy` muda numa diretiva: `style-src 'self'` no lugar de
`style-src 'self' 'unsafe-inline'`. Variáveis de ambiente, rotas e o formulário de
contato não mudam.

### ADR-05 — Honeypot escondido por uma classe da folha de estilo

**Supersedes** ADR-02.

- **Decisão:** a `<div>` do honeypot recebe a classe `contact__honeypot`, e o
  `styles.css` a esconde com `display: none`. O `style-src` fica só com `'self'`.
- **Alternativas:**
  - O atributo `hidden` na `<div>`: dispensa a regra de CSS, mas fica escrito no HTML,
    e um robô que leia o HTML pula o campo marcado como escondido sem precisar
    interpretar CSS.
  - Manter o `style=` com um hash e `'unsafe-hashes'`: a CSP aceitaria só aquele
    valor, mas em qualquer elemento da página, e o valor é justamente
    `display:none;`. Um trecho injetado com o mesmo atributo esconderia conteúdo do
    site.
  - Nonce por pedido no `style-src`: o nonce não vale para atributo `style=`, só para
    elemento `<style>`, então exigiria trocar a `<div>` por um bloco `<style>` com nonce
    em cada resposta, para esconder um elemento só.
- **Porquê:** a regra numa folha externa é o que o resto da interface já usa, não pede
  nenhuma exceção na CSP, e quem procura o campo escondido precisa ler o CSS.
- **Trade-off:** o campo passa a depender de o `styles.css` carregar. Se a folha falhar,
  o campo aparece sem rótulo no formulário; uma pessoa que o preenchesse teria o envio
  descartado como o de um robô (spec 002, RF-01). A folha vem do próprio site pelo
  WhiteNoise, e sem ela a página inteira já aparece sem estilo.

### ADR-06 — A regra contra estilo inline lê os templates como texto

- **Decisão:** o teste novo procura `style=` e `<style` no texto de cada template de
  `templates/` e das pastas `templates/` dos apps, e uma checagem a mais renderiza a
  home.
- **Alternativas:** só renderizar páginas e procurar `style=` no HTML entregue.
- **Porquê:** a renderização só cobre os ramos que o teste monta (com ou sem perfil,
  modo demonstração, páginas de erro); o texto cobre todo template, inclusive ramo que
  nenhum teste abre. A renderização da home cobre o que o texto não vê: HTML gerado no
  Python e marcado como seguro.
- **Trade-off:** um `style=` escrito como texto de exemplo dentro de um template também
  falha o teste. Hoje nenhum template tem isso, e a mensagem do teste aponta o arquivo e
  a linha.

### Impacto no código existente do adendo

- O ADR-02 deixa de valer (ganha `**Superseded by** adendo, ADR-05.`), e o RF-05 já
  aponta o RF-09.
- `docs/referencia/configuracoes.md`, `docs/stack.md`, a nota "CSP e scripts/estilos
  inline" do `specs/README.md` e o aviso da CSP no `CLAUDE.md`: o `style-src` não tem
  mais `'unsafe-inline'`, e estilo inline num template é bloqueado como script inline.
- A árvore do `CLAUDE.md` ganha o `test_estilo_inline.py`.

### Estratégia de testes do adendo

- **Suíte (RF-11):** os testes do `test_estilo_inline.py` e o assert novo do
  `test_home_envia_a_csp`. O comportamento do honeypot preenchido segue coberto pelo
  `test_contato_honeypot_bot_protection` (spec 002).
- **Navegador (RF-09, RF-10):** com o servidor de desenvolvimento e os dados do
  `semear_dados_demo`, abrir no Chrome a home (com e sem perfil, modo demonstração ligado
  e desligado) e o Admin (login, lista, edição de um projeto com imagem, uma ação em
  lote), registrando os eventos `securitypolicyviolation` e o console de cada página. A
  conta e o banco da conferência ficam numa pasta temporária, pelo `DIRETORIO_DADOS`.
- **Teclado e leitor de tela (RF-10):** na home, o Tab vai do último campo visível ao
  botão de envio sem parar no honeypot, e a árvore de acessibilidade do Chrome não tem o
  campo.

### Desvios do adendo

1. O `pyproject.toml` põe o `app_portfolio.test_estilo_inline` na lista de overrides do
   mypy da suíte, como os outros módulos de teste: as fixtures `client` e `settings`
   do pytest-django entram sem tipo. — RF-11
2. A renderização da home roda nas quatro combinações do RF-09 (com e sem perfil, modo
   demonstração ligado e desligado), não numa só. — RF-11, ADR-06
3. No HTML entregue, o teste procura o atributo `style` e o elemento `<style>` pelo
   `html.parser` da biblioteca padrão, não pelo texto `style=`, para não acusar um
   texto da página que cite a palavra. — ADR-06

### Notas de implementação do adendo

- Suíte: 331 testes, 22 deles do `test_estilo_inline.py`. Contra o código anterior ao
  adendo, 6 casos do módulo novo falham (o `style=` do `home.html`, a regra ausente no
  `styles.css` e as quatro renderizações da home).
- Navegador: Chrome sem interface (`puppeteer-core`), com o servidor de desenvolvimento
  em duas portas (modo demonstração desligado e ligado) sobre um banco temporário, os
  dados do `semear_dados_demo` e um superusuário de teste. Cada página registrou os
  eventos `securitypolicyviolation`, os erros e os avisos do console.
  - Home, nas quatro combinações: nenhuma violação e nenhum elemento com `[style]` no
    DOM; a caixa do honeypot com `display: none` calculado.
  - Admin: login, índice, listas de projetos e de perfil, inclusão de projeto, edição
    de projeto (campo de imagem e o seletor duplo de tecnologias do
    `filter_horizontal`) e a confirmação da exclusão em lote, sem violação nem erro no
    console. O `<style>` da lista (decisão resolvida 3) não aparece, porque nenhum
    `ModelAdmin` desliga as barras de ações.
  - Controle: um `style=` injetado na home gerou a violação `style-src-attr`, o que
    confirma que a conferência enxerga o bloqueio.
  - "Igual à de antes" foi conferido pela ausência de violação: a mudança só altera o
    que a CSP bloqueia. Não houve comparação de capturas de tela.
- Teclado e leitor de tela: o Tab vai de `mensagem` direto ao botão de envio, e o campo
  `honeypot` fica fora da árvore de acessibilidade do Chrome.
