---
feature: Modo demonstração do formulário de contato
status: concluído
date: 2026-11-16
related:
  - 002-formulario-contato
  - 004-correcoes-de-interface
origin: nova feature
---

# Design — Modo demonstração do formulário de contato

## 1. Visão geral

Uma chave booleana, `MODO_DEMONSTRACAO`, lida do `.env` no `settings.py`. A
view `home` ganha um corte no ramo do POST: depois do honeypot e da validação,
e antes do rate limit, o modo ligado responde o aviso de demonstração e
encerra, sem `form.save()`, sem `send_mail()` e sem `cache.add()`. Com o modo
desligado, o código a partir desse ponto é o de hoje, linha por linha.

Na interface, dois avisos. O fixo fica no topo do card do formulário e só é
renderizado com o modo ligado. O do envio reaproveita o componente
`.notification` da spec 004 (ADR-06 de lá) na variante informativa, com um link
para o repositório e sem sumir sozinho. Os dois fluxos (AJAX e POST comum)
mostram o mesmo texto; o link vem de dados estruturados, nunca de HTML na
resposta.

O backend de console para desenvolvimento é uma linha condicional no bloco de
e-mail do `settings.py`.

## 2. Componentes

```
portfolio/settings.py          # MODO_DEMONSTRACAO, URL_REPOSITORIO, console em dev
app_portfolio/views.py         # corte do modo, MENSAGEM_DEMONSTRACAO, TEXTO_LINK_DEMONSTRACAO, contexto
templates/home.html            # aviso fixo .contact__aviso no topo do <form>
templates/base.html            # notification--{{ message.level_tag }} + link quando extra_tags tem "demo"
static/js/main.js              # ramo status "demo"; mostrarNotificacao() aceita link
static/css/styles.css          # .contact__aviso e .notification--info (com o link)
.env.example                   # MODO_DEMONSTRACAO na seção 3
app_portfolio/tests.py         # grupo novo TestModoDemonstracao
app_portfolio/test_interface.py # aviso fixo, main.js e CSS lidos como texto
README.md / README.en.md       # a chave na tabela/lista de variáveis
CLAUDE.md                      # tabela de variáveis + passo novo no fluxo do contato
docs/referencia/configuracoes.md # e-mail: console em dev; a chave do modo
specs/README.md                # linha 005 no índice
```

## 3. Modelo de dados

Nenhuma mudança. `MensagemContato` segue igual; o modo só deixa de gravar.

## 4. Interfaces

### Settings

| Nome | Tipo | Origem | Padrão |
|---|---|---|---|
| `MODO_DEMONSTRACAO` | `bool` | `os.getenv("MODO_DEMONSTRACAO", "False").lower() == "true"` | `False` |
| `URL_REPOSITORIO` | `str` | constante no `settings.py` | URL do repositório público do projeto |
| `EMAIL_BACKEND` | `str` | console se `DEBUG` e `EMAIL_USER` vazio; SMTP nos outros casos | SMTP |

### Resposta do POST com o modo ligado e formulário válido

AJAX (`X-Requested-With: XMLHttpRequest`), HTTP 200:

```json
{
  "status": "demo",
  "message": "Este formulário faz parte de um projeto educacional e não envia mensagens. Quer ver como ele funciona por dentro?",
  "link": {
    "texto": "Clone ou baixe o código no GitHub",
    "url": "<URL_REPOSITORIO>"
  }
}
```

POST comum: `messages.info(request, MENSAGEM_DEMONSTRACAO, extra_tags="demo")`
e `redirect("home")`. O `base.html` completa o aviso com o link quando
`"demo"` está em `message.extra_tags`.

O aviso que o visitante vê, nos dois fluxos, é `message` + espaço + link +
ponto final, que reproduz a frase aprovada no RF-05.

### Contexto da `home`

Duas chaves novas: `modo_demonstracao` (`bool`) e `url_repositorio` (`str`).
O `base.html` só é estendido pela `home.html` (as páginas de erro usam o
`erro.html`), então o contexto da view chega aos dois templates.

### Interface (mockup aprovado)

Aprovada a alternativa "aviso no topo do formulário", a 390 e a 1280 px, com
os tokens e medidas reais do `styles.css`:

- **Aviso fixo** (`.contact__aviso`, um `<p>` antes do primeiro `.form__group`):
  ícone "i" em SVG inline (`aria-hidden`, cor `--color-accent`), texto em
  `--color-gray-100`, `font-size` 0,875 rem, padding 0,875 × 1 rem, margem
  inferior 1,5 rem, borda de 1 px `rgba(0, 212, 255, 0.35)`, fundo
  `rgba(0, 212, 255, 0.08)`, raio `--radius-md`. Texto: "Formulário de
  demonstração: nenhuma mensagem é enviada. [Veja como ele funciona no
  GitHub]." O link em `--color-accent`, peso 500, abre em nova aba
  (`rel="noopener"`).
- **Aviso do envio** (`.notification.notification--info`): fundo
  `--color-info` (#1d4ed8), texto branco, link branco sublinhado, botão de
  fechar de 44 px igual aos outros avisos. Texto: "Este formulário faz parte de
  um projeto educacional e não envia mensagens. Quer ver como ele funciona por
  dentro? [Clone ou baixe o código no GitHub]."

As capturas da tela real (390 e 1280 px, modo ligado, antes e depois do envio)
entram nesta pasta na implementação, em WebP.

## 5. Decisões técnicas (ADRs)

### ADR-01 — Chave própria no `.env`, desligada por padrão

- **Decisão:** `MODO_DEMONSTRACAO` separado do `DEBUG`, lido como o `DEBUG`
  (`"true"` sem diferenciar maiúsculas).
- **Alternativas:** (a) ligar o modo sempre que `DEBUG=False`; (b) constante
  no código.
- **Porquê:** quem clona e publica o próprio portfólio quer receber mensagens
  em produção; amarrar ao `DEBUG` tiraria isso. A constante exigiria editar o
  código para cada ambiente.
- **Trade-off:** mais uma variável para documentar.

### ADR-02 — O corte vem depois da validação e antes do rate limit

- **Decisão:** a ordem no POST passa a ser honeypot → `form.is_valid()` →
  **modo demonstração** → rate limit → sanitização → gravação → e-mail.
- **Alternativas:** (a) cortar antes da validação; (b) gravar e só não enviar.
- **Porquê:** (a) esconderia a validação, que é parte do que a demo mostra;
  (b) manteria o dado pessoal sem finalidade, que é o problema da spec. Antes do
  rate limit, o visitante pode testar de novo e nenhuma chave nasce no cache.
- **Trade-off:** sem rate limit, um robô que passe pelo honeypot pode postar à
  vontade; o custo é só uma validação de formulário por requisição, sem banco e
  sem SMTP.

### ADR-03 — O link vai em dados estruturados, não em HTML

- **Decisão:** o JSON traz `link: {texto, url}` e o `main.js` monta o `<a>` com
  `createElement` e `textContent`; no fluxo sem JavaScript, o `base.html` monta
  o link a partir de `extra_tags="demo"`.
- **Alternativas:** (a) HTML pronto em `message` e `innerHTML` no `main.js`;
  (b) `format_html` na mensagem do Django e a URL fixa no `main.js`.
- **Porquê:** (a) abre caminho para XSS se a frase um dia vier de dado
  editável, e contraria o `textContent` que a spec 004 adotou; (b) duplicaria a
  URL no JavaScript. Com dados, o texto e a URL têm fonte única na view e no
  `settings.py`.
- **Trade-off:** o `base.html` ganha um `{% if %}` para o caso `demo`, e a
  classe do aviso passa de `message.tags` para `message.level_tag` (com
  `extra_tags`, `message.tags` vira `"demo info"` e quebraria a classe BEM).

### ADR-04 — URL do repositório como constante no `settings.py`

- **Decisão:** `URL_REPOSITORIO` no `settings.py`, usado pela view e pelos
  dois templates.
- **Alternativas:** (a) variável de ambiente; (b) URL escrita no template e no
  JavaScript.
- **Porquê:** a URL muda só num fork, e aí quem fez o fork edita uma linha; uma
  variável de ambiente a mais não compensa. (b) espalharia o mesmo valor por
  três arquivos.
- **Trade-off:** um fork que ligar o modo sem trocar a constante aponta para o
  repositório original.

### ADR-05 — O aviso com link fica até ser fechado

- **Decisão:** `mostrarNotificacao()` recebe um `link` opcional; com link, o
  aviso não some em `TEMPO_DO_AVISO` (6 s), como o de erro.
- **Alternativas:** sumir em 6 s, como o de sucesso.
- **Porquê:** quem quer seguir o link precisa de tempo para ler e clicar; um
  alvo que some sozinho também falha no critério 2.2.1 (tempo ajustável) da
  WCAG.
- **Trade-off:** o visitante fecha o aviso à mão.

### ADR-06 — E-mail no console só em desenvolvimento sem `EMAIL_USER`

- **Decisão:** com `DEBUG=True` e `EMAIL_USER` vazio, `EMAIL_BACKEND` vira o
  de console e `EMAIL_HOST_USER` recebe `contato@example.com` (domínio
  reservado da RFC 2606), para o e-mail impresso ter remetente e destino.
- **Alternativas:** (a) console sempre que `EMAIL_USER` estiver vazio; (b)
  deixar como hoje.
- **Porquê:** (a) faria um deploy sem e-mail responder "Mensagem enviada!" sem
  enviar nada; (b) obriga o aluno a criar senha de app do Gmail antes de ver o
  fluxo funcionar.
- **Trade-off:** em desenvolvimento sem Gmail, o visitante local vê "Mensagem
  enviada!" mesmo sem e-mail real; o terminal mostra o que teria saído.

## 6. Impacto e dependências

- **Sem dependência nova** (RNF-01); nenhum `<script>` ou `style` inline novo:
  o SVG do ícone é marcação, não script, e a CSP da spec 003 não muda.
- **`base.html`:** `message.tags` → `message.level_tag`. Para as mensagens
  atuais (sem `extra_tags`) o resultado é o mesmo (`success`, `error`); os
  testes da spec 004 que procuram `notification--success` e
  `notification--error` seguem valendo.
- **`main.js`:** a assinatura vira `mostrarNotificacao(mensagem, tipo, link)`;
  as chamadas atuais não passam `link` e não mudam. Edição só no trecho, sem
  Prettier (4 espaços, aspas simples).
- **`views.py`:** a docstring da `home` e o docstring do módulo citam o corte.
- **Modo desligado:** fluxo idêntico ao de hoje (RF-06); a suíte atual passa
  sem alteração.

## 7. Estratégia de testes

Tudo em pytest, sem rede, com as fixtures autouse do `tests.py`
(`disable_real_email` em `locmem`, cache limpo).

- **View, modo ligado** (`settings.MODO_DEMONSTRACAO = True` pela fixture
  `settings`): AJAX válido → 200, `status == "demo"`, `message` e `link` com a
  URL de `URL_REPOSITORIO`, `MensagemContato.objects.count() == 0`,
  `mail.outbox == []`, `cache.get("contact_limit_127.0.0.1") is None`; POST
  comum válido → redirect, mensagem de nível `info` com `"demo"` em
  `extra_tags`; honeypot → redirect sem mensagem; inválido → 400 com
  `MENSAGEM_DADOS_INVALIDOS`; dois envios seguidos → os dois respondem `demo`.
- **Templates:** com o modo ligado, a home tem `contact__aviso` e o link para
  `URL_REPOSITORIO`; desligado, não tem; depois do POST comum, a home seguinte
  tem `notification--info` e o link "Clone ou baixe o código no GitHub".
- **Leitura da chave e do backend:** `importlib.reload(portfolio.settings)` com
  `monkeypatch` no ambiente e em `dotenv.load_dotenv` (no-op, para o `.env`
  local não interferir), lendo só o módulo recarregado: `MODO_DEMONSTRACAO`
  ausente/`True`/`true`/`sim`; `EMAIL_BACKEND` console com `DEBUG=True` e
  `EMAIL_USER` vazio, SMTP com `DEBUG=False` ou com `EMAIL_USER` preenchido. O
  `django.conf.settings` em uso não muda.
- **Texto (padrão do `test_interface.py`):** o `main.js` tem o ramo
  `status === 'demo'`, cria o link com `createElement('a')` e não usa
  `innerHTML` nele; o `styles.css` tem `.contact__aviso` e
  `.notification--info`.
- **À mão, na implementação:** contraste dos dois avisos medido no Chrome, Tab
  até o link e o botão de fechar, e o aviso anunciado pelo leitor de tela.

## Desvios

1. **Testes da leitura das chaves (RF-08, seção 7):** em vez de
   `importlib.reload(portfolio.settings)`, o `tests.py` executa uma cópia avulsa
   do arquivo (`importlib.util.spec_from_file_location`), fora do `sys.modules`.
   O módulo em uso não muda, e o teste não precisa recarregá-lo de volta no fim.
2. **Contexto da `home` (RF-05, ADR-03):** além de `modo_demonstracao` e
   `url_repositorio`, a view passa `texto_link_demonstracao`, para o `base.html`
   não repetir o texto do link que o JSON já leva (fonte única na view).
3. **Isolamento dos testes (RF-06):** `tests.py` e `test_interface.py` desligam
   o modo numa fixture autouse; sem ela, quem roda a suíte com
   `MODO_DEMONSTRACAO=True` no `.env` veria o fluxo normal falhar.
4. **Largura dos avisos (RF-05):** o contêiner `.notifications` ganhou teto de
   28rem. Na tela real a 1280 px, o aviso do modo (bem mais longo que
   "Mensagem enviada!") se esticava pela largura inteira, por cima do rodapé;
   no celular, segue a folga das bordas da spec 004.
5. **Região viva dos avisos (RNF-02):** na conferência com o NVDA, o aviso do
   envio por AJAX não era anunciado. O `main.js` criava a região
   `role="status"` junto com o primeiro aviso, e o leitor de tela só anuncia
   mudança numa região que já estava na página. O `base.html` passou a
   renderizar a região sempre, vazia quando não há mensagem. A correção vale
   também para os avisos de sucesso e de erro da spec 004 (RF-06).
6. **Botão de fechar no anúncio (RNF-02):** o "×" do botão entrou num `<span>`
   com `aria-hidden`; o NVDA lia o símbolo no fim do anúncio e agora lê o nome
   do botão ("Fechar aviso"), que vem do `aria-label`.
7. **Posição do botão de fechar (RF-05):** o "×" passou do meio vertical para o
   canto superior direito do aviso (`align-self: flex-start`). No aviso de
   várias linhas do modo, centralizado, ele ficava solto no meio da caixa.
8. **Capturas (seção 4):** as capturas da tela real (390 e 1280 px, antes e
   depois do envio) foram tiradas e usadas na conferência, mas não ficam
   versionadas nesta pasta: não acrescentam ao projeto o que o código e os
   testes já registram.

## Notas de implementação

- **Contraste (RNF-02):** aviso fixo sobre o fundo composto `#183751` (ciano a
  8% sobre o card): texto 10,0:1 e link 6,96:1. Aviso do envio: branco sobre
  `--color-info`, 6,41:1. O `test_interface.py` recalcula os três a partir dos
  tokens.
- **Teclado (RNF-02):** no Chrome, o link do aviso fixo é alcançado no 19º Tab a
  390 px e no 24º a 1280 px, com o anel de foco de 2 px; o Tab seguinte vai para
  o campo Nome. No aviso do envio, o Tab vai do link para o botão de fechar, e o
  Enter fecha.
- **Leitor de tela (RNF-02):** com o NVDA, depois do envio por AJAX, o anúncio é
  a frase inteira do RF-05, o link e "Fechar aviso" (depois dos desvios 5 e 6).
- **Tempo (ADR-05):** o aviso do envio segue na tela depois de 7 s, nas duas
  larguras.
- **CSP (RNF-01):** console sem bloqueio nos dois fluxos; nenhum script ou
  estilo inline novo. O ícone do aviso fixo é SVG inline (marcação).
- **Largura:** a 1280 px o aviso do envio mede 448 px (teto de 28rem do desvio
  4); a 390 px, 342 px, sem rolagem horizontal.
