---
feature: Modo demonstração do formulário de contato
status: concluído
date: 2026-11-16
related:
  - 002-formulario-contato
  - 004-correcoes-de-interface
origin: nova feature
---

# Requisitos — Modo demonstração do formulário de contato

## 1. Contexto e problema

O projeto é um template educativo: o formulário de contato existe para ensinar
honeypot, rate limit, sanitização e envio por SMTP (spec 002). Numa demo
pública, porém, o fluxo completo grava no banco o nome, o e-mail e a mensagem
de cada visitante e dispara um e-mail para uma caixa que ninguém vai ler. Isso
gera duas dores:

- **dado pessoal sem finalidade:** guardar nome e e-mail de visitante que só
  queria testar o formulário é passivo de LGPD (art. 6º, I e III: finalidade e
  necessidade);
- **expectativa falsa:** o visitante lê "Mensagem enviada!" e espera uma
  resposta que não vem.

Hoje não há como desligar o envio sem mexer no código. E quem clona o projeto
precisa de uma conta Gmail com senha de app para ver o fluxo do e-mail
funcionar: sem `EMAIL_USER`, todo envio cai em "Não foi possível enviar agora".

## 2. Objetivos

- Uma chave no `.env` que põe o formulário em **modo demonstração**: valida os
  campos, mas não grava, não envia e diz isso ao visitante.
- Deixar claro, antes e depois do envio, que o formulário é de demonstração, e
  apontar para o código no GitHub.
- Com a chave desligada (o padrão), o fluxo da spec 002 fica idêntico: é ele que
  o aluno estuda.
- Em desenvolvimento, ver o e-mail que seria enviado sem configurar o Gmail.

## 3. Não-objetivos

- Trocar o honeypot, o rate limit ou a sanitização (spec 002).
- Apagar as `MensagemContato` já gravadas (limpeza de dados é operação, não
  código).
- Esconder o formulário ou o card `mailto:` da seção de contato.
- Modo demonstração em outras partes do site (o Admin segue igual).
- Envio de e-mail assíncrono ou por outro provedor.

## 4. Personas

- **Visitante da demo:** As a visitante, I want saber que o formulário não
  envia nada, so that eu não espere resposta nem deixe meus dados à toa.
- **Aluno que clonou:** As a aluno, I want ver o fluxo completo e o e-mail que
  sairia, so that eu entenda o SMTP sem precisar de conta Gmail logo de início.
- **Quem publica a demo:** As a quem hospeda o projeto, I want ligar o modo por
  uma variável de ambiente, so that a demo não acumule dados de visitantes.

## 5. Requisitos funcionais e critérios de aceite

### RF-01 — Chave `MODO_DEMONSTRACAO` no `.env`

- **Given** um `.env` sem `MODO_DEMONSTRACAO`
  **When** o projeto sobe
  **Then** o modo fica desligado e o formulário segue o fluxo da spec 002.
- **Given** `MODO_DEMONSTRACAO=True` (sem diferenciar maiúsculas, como o `DEBUG`)
  **When** o projeto sobe
  **Then** o modo fica ligado; qualquer outro valor o deixa desligado.

### RF-02 — Envio no modo demonstração não grava nem envia

- **Given** o modo ligado e um formulário válido
  **When** o visitante envia
  **Then** nenhuma `MensagemContato` é gravada, nenhum e-mail sai e a chave do
  rate limit não é criada (o visitante pode testar de novo na hora).
- **Given** o modo ligado e um envio por AJAX
  **When** o formulário é válido
  **Then** a resposta é JSON com HTTP 200, `"status": "demo"` e a frase do
  aviso em `message`.
- **Given** o modo ligado e um envio sem JavaScript (POST comum)
  **When** o formulário é válido
  **Then** a view redireciona para a home com o aviso em `messages` no nível
  `info`.

### RF-03 — Honeypot e validação seguem valendo no modo

- **Given** o modo ligado e o campo `honeypot` preenchido
  **When** o formulário é enviado
  **Then** o redirect silencioso da spec 002 acontece e nenhum aviso aparece.
- **Given** o modo ligado e um campo obrigatório vazio ou inválido
  **When** o formulário é enviado
  **Then** a resposta é a mesma do fluxo normal (`MENSAGEM_DADOS_INVALIDOS`,
  HTTP 400 no AJAX).

### RF-04 — Aviso fixo no card do formulário

- **Given** o modo ligado
  **When** a home abre
  **Then** o card do formulário mostra, antes do primeiro campo, o aviso
  "Formulário de demonstração: nenhuma mensagem é enviada. Veja como ele
  funciona no GitHub.", com link para o repositório do código.
- **Given** o modo desligado
  **When** a home abre
  **Then** o aviso não aparece no HTML.

### RF-05 — Aviso do envio: neutro, com link e até ser fechado

- **Given** o modo ligado e um envio válido (AJAX ou sem JavaScript)
  **When** a resposta chega
  **Then** aparece o aviso "Este formulário faz parte de um projeto educacional
  e não envia mensagens. Quer ver como ele funciona por dentro? Clone ou baixe
  o código no GitHub.", com link para o repositório, na variante neutra
  (informativa) do aviso: nem a cor de sucesso, nem a de erro.
- **Given** o aviso do envio na tela
  **When** passam os 6 segundos em que o aviso de sucesso some
  **Then** ele continua até o visitante fechá-lo (tem link para seguir).
- **Given** o aviso do envio por AJAX
  **When** ele aparece
  **Then** os campos do formulário são limpos, como no envio com sucesso.

### RF-06 — Sem o modo, nada muda

- **Given** o modo desligado
  **When** qualquer envio acontece (válido, inválido, honeypot, limite, falha
  de SMTP)
  **Then** o comportamento, as respostas e as frases são os da spec 002 e da
  spec 004, RF-03.

### RF-07 — E-mail no terminal em desenvolvimento

- **Given** `DEBUG=True` e `EMAIL_USER` vazio ou ausente
  **When** um envio válido chega com o modo desligado
  **Then** o e-mail é impresso no terminal do `runserver` (backend de console)
  e o visitante vê "Mensagem enviada!".
- **Given** `DEBUG=False` e `EMAIL_USER` vazio
  **When** um envio válido chega
  **Then** o backend segue o SMTP, o envio falha e o visitante vê
  `MENSAGEM_FALHA_ENVIO`, como hoje (a produção não finge que enviou).

## 6. Requisitos não-funcionais

### RNF-01 — Sem dependência nova e dentro da CSP

O modo usa só o Django e o `main.js` existentes. Nenhum `<script>` ou `style`
inline novo (a CSP da spec 003 bloquearia em silêncio), e o link do aviso no
fluxo AJAX é montado com nós do DOM, nunca com `innerHTML` a partir da resposta.

### RNF-02 — Acessível

Os dois avisos passam no contraste AA (4,5:1 para o texto) sobre o fundo do
card e da página. O aviso do envio é anunciado pelo leitor de tela, como os
outros avisos (spec 004, RF-06), e o botão de fechar é alcançável por teclado.
O link tem nome que diz o destino.

### RNF-03 — Documentado para quem clona

A chave aparece no `.env.example` (com o padrão e o efeito), nos dois READMEs
(no mesmo PR, com as mesmas seções) e na referência de configurações.

## 7. Perguntas em aberto / decisões resolvidas

**Perguntas em aberto:** nenhuma.

**Decisões resolvidas:**

1. **Padrão desligado.** Quem clona vê o fluxo completo, que é o objeto de
   estudo; só a demo pública liga o modo.
2. **Validação antes do modo.** Os campos seguem obrigatórios no modo: o
   visitante vê a validação funcionar, que é parte do que a demo mostra.
3. **HTTP 200 com `"status": "demo"`.** O envio não falhou; um status próprio
   deixa o `main.js` escolher a variante do aviso sem tratar como erro.
4. **O rate limit não roda no modo.** Sem gravação nem e-mail, não há o que
   proteger, e o visitante pode testar mais de uma vez.
5. **Console só com `DEBUG=True`.** Em produção, `EMAIL_USER` vazio continua
   sendo erro visível, para que um deploy sem e-mail configurado não responda
   "Mensagem enviada!" sem enviar.

## 8. Testes

### RF-08 — A suíte cobre os dois modos

A suíte (pytest, sem rede, com a fixture `disable_real_email` da spec 002)
precisa cobrir:

- modo ligado, AJAX válido: 200, `"status": "demo"`, nenhuma `MensagemContato`,
  `mail.outbox` vazio, chave do rate limit ausente;
- modo ligado, POST comum válido: redirect e mensagem `info` com a frase do
  aviso;
- modo ligado: honeypot e formulário inválido com as respostas do fluxo normal;
- aviso fixo presente com o modo ligado e ausente com ele desligado;
- `main.js` com o ramo `demo` (variante informativa, sem sumir sozinho) e o
  CSS com a variante `.notification--info`;
- leitura da chave: ausente, `True`, `true` e outro valor;
- backend de console com `DEBUG=True` e `EMAIL_USER` vazio, SMTP nos outros
  casos.
