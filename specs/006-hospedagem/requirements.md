---
feature: Hospedagem da demo na Railway
status: aprovado
date: 2026-11-16
related:
  - 002-formulario-contato
  - 003-configuracao-seguranca
  - 005-modo-demonstracao
origin: nova feature
---

# Requisitos — Hospedagem da demo na Railway

## 1. Contexto e problema

O projeto não tem mais uma demo no ar: a hospedagem anterior saiu da
documentação, e os READMEs não trazem link para ver o site funcionando. A
nova demo vai ficar na Railway, em `https://portfolio-dinamico.ryanmorais.com.br`,
com o domínio passando pelo proxy da Cloudflare.

O código de hoje supõe um servidor que entrega o pedido direto ao Django. Na
Railway, três suposições deixam de valer:

- **HTTPS:** o TLS termina no proxy, e o Django recebe HTTP. Com `DEBUG=False`,
  o `SECURE_SSL_REDIRECT` redireciona todo pedido para HTTPS, e o pedido
  redirecionado chega de novo como HTTP: o site entra em laço de redirect.
- **Disco:** o sistema de arquivos do contêiner é recriado a cada deploy. O
  `db.sqlite3`, a pasta `media/` (fotos e currículo enviados pelo Admin) e a
  `django_cache/` ficam na raiz do repositório e somem no deploy seguinte.
- **Mídia:** com `DEBUG=False`, o Django não serve `/media/`, porque a regra
  supõe um servidor web na frente que cuide disso. Na Railway não há esse
  servidor, e as fotos de perfil e de projeto respondem 404.

Também não há, no repositório, a receita de build e de start: qual comando
instala as dependências, quando o `collectstatic` e o `migrate` rodam, e em que
porta o gunicorn escuta.

## 2. Objetivos

- Deixar no repositório tudo o que a Railway precisa para construir e iniciar o
  projeto a cada push na `main`.
- Fazer o HTTPS, o CSRF, os cookies seguros e o HSTS da spec 003 funcionarem
  atrás do proxy.
- Guardar banco, mídia e cache num diretório configurável, que a plataforma
  monta como volume e que sobrevive ao deploy.
- Servir a mídia enviada pelo Admin com `DEBUG=False`.
- Deixar os erros do servidor visíveis no log da plataforma.
- Pôr a demo no ar com o modo demonstração ligado (spec 005) e o link dela nos
  dois READMEs.

## 3. Não-objetivos

- **Guia de hospedagem passo a passo.** O repositório traz a receita de build e
  as variáveis de ambiente; criar o serviço, o volume e o domínio é feito no
  painel da plataforma.
- **PostgreSQL ou `DATABASE_URL`.** O SQLite segue sendo o banco do projeto.
- **Armazenamento de objetos para a mídia** (S3, R2): o volume atende ao tamanho
  da demo.
- **IP real do visitante e trava de origem da Cloudflare** (decisão resolvida 3).
- **Deploy sem queda e healthcheck.** Com volume, a troca de versão tem uma
  janela curta fora do ar.
- **Subir o piso do Python** (`requires-python`, `.python-version`, matriz do CI).
- **Carregar o conteúdo da demo** (perfil, projetos, habilidades): é operação de
  dados, feita no Admin ou a partir de um backup, fora do código.

## 4. Personas

- **Visitante:** As a visitante, I want abrir a demo pelo link do README, so that
  eu veja o portfólio funcionando antes de clonar.
- **Quem clona e publica:** As a quem quer pôr o projeto no ar, I want a receita
  de build e as variáveis documentadas, so that o deploy funcione sem adaptar o
  `settings.py`.
- **Quem mantém a demo:** As a quem hospeda a demo, I want que banco e mídia
  sobrevivam ao deploy, so that cada push na `main` não apague o conteúdo
  cadastrado no Admin.

## 5. Requisitos funcionais e critérios de aceite

### RF-01 — Build e start declarados no repositório

- **Given** um push na `main`
  **When** a Railway constrói o projeto
  **Then** as dependências vêm do `uv.lock` (sem as ferramentas de dev, com o
  extra `prod`) e o `collectstatic` roda no build.
- **Given** um `uv.lock` que não bate com o `pyproject.toml`
  **When** a Railway constrói o projeto
  **Then** o build falha em vez de resolver as versões de novo.
- **Given** o build concluído
  **When** o serviço inicia
  **Then** o `migrate` roda antes do servidor, e o gunicorn escuta na porta da
  variável `PORT` (8000 se ela faltar).

### RF-02 — HTTPS reconhecido atrás do proxy

- **Given** `DEBUG=False` e um pedido com `X-Forwarded-Proto: https`
  **When** o Django responde
  **Then** não há redirect para HTTPS, o pedido conta como seguro e os cookies de
  sessão e de CSRF saem com `Secure`.
- **Given** `DEBUG=False` e um pedido sem esse cabeçalho, ou com `http`
  **When** o Django responde
  **Then** a resposta é o redirect 301 para HTTPS, como hoje.
- **Given** `DEBUG=True`
  **When** o `runserver` atende um pedido HTTP
  **Then** nada muda no desenvolvimento local.

### RF-03 — Formulário e Admin aceitam POST pelo domínio público

- **Given** `DEBUG=False`, o host em `ALLOWED_HOSTS` e um pedido HTTPS pelo proxy
  **When** o formulário de contato ou o login do Admin é enviado com o token CSRF
  e `Origin` igual ao endereço do site
  **Then** o pedido passa pela verificação de CSRF.
- **Given** o mesmo cenário com `Origin` de outro site
  **When** o pedido chega
  **Then** a resposta é 403, com a página `403_csrf.html`.

### RF-04 — `ALLOWED_HOSTS` tolera espaços e vírgula sobrando

- **Given** `DEBUG=False` e `ALLOWED_HOSTS=exemplo.com, www.exemplo.com,`
  **When** o projeto sobe
  **Then** a lista fica `["exemplo.com", "www.exemplo.com"]`.
- **Given** `DEBUG=False` e `ALLOWED_HOSTS` vazio ou ausente
  **When** chega um pedido
  **Then** todo host é recusado, como hoje (falha fechada).

### RF-05 — Banco, mídia e cache num diretório configurável

- **Given** um `.env` sem `DIRETORIO_DADOS`
  **When** o projeto sobe
  **Then** o banco, a mídia e o cache ficam onde estão hoje (`db.sqlite3`,
  `media/` e `django_cache/` na raiz do repositório).
- **Given** `DIRETORIO_DADOS=/data`
  **When** o projeto sobe
  **Then** o banco fica em `/data/db.sqlite3`, a mídia em `/data/media/` e o
  cache em `/data/django_cache/`.
- **Given** o diretório montado como volume e um deploy novo
  **When** o serviço reinicia
  **Then** o conteúdo cadastrado no Admin e as imagens enviadas continuam lá.

### RF-06 — Mídia servida com `DEBUG=False`

- **Given** `DEBUG=False` e um arquivo enviado pelo Admin
  **When** o navegador pede `/media/<caminho>`
  **Then** a resposta é 200 com o `Content-Type` do arquivo e o cabeçalho
  `X-Content-Type-Options: nosniff`.
- **Given** `DEBUG=False` e um caminho que não existe, uma pasta ou um caminho que
  sai da pasta de mídia (`../`)
  **When** o navegador pede o endereço
  **Then** a resposta é 404, com a página `404.html`, sem listar arquivos.
- **Given** `DEBUG=True`
  **When** o navegador pede `/media/<caminho>`
  **Then** o comportamento é o de hoje.

### RF-07 — Erros aparecem no log do serviço

- **Given** `DEBUG=False` e uma exceção não tratada numa view
  **When** o Django responde 500
  **Then** o traceback sai na saída de erro do processo, que a plataforma mostra
  no log do serviço.
- **Given** `DEBUG=False` e um pedido para um endereço que não existe
  **When** o Django responde 404
  **Then** nada sai no log (robôs que testam caminhos não enchem o log).
- **Given** `DEBUG=False` e uma falha no envio do e-mail do formulário
  **When** a view registra a falha (spec 002)
  **Then** o registro sai no log do serviço.

## 6. Requisitos não-funcionais

### RNF-01 — Sem dependência nova de runtime

A hospedagem usa só o que o projeto já tem: Django, WhiteNoise e, no extra
`prod`, o gunicorn. O `pyproject.toml` não ganha dependência de runtime.

### RNF-02 — Postura de produção mantida

`DEBUG=False uv run python manage.py check --deploy` não acusa aviso novo. A
CSP, o HSTS, o `X-Frame-Options` e os cookies seguros da spec 003 seguem iguais.

### RNF-03 — Uma instância

O SQLite e o cache em arquivo vivem no mesmo volume, que só uma instância monta.
O desenho supõe uma réplica do serviço; o gunicorn pode ter mais de um worker,
porque o `FileBasedCache` é compartilhado entre processos.

### RNF-04 — Desenvolvimento local e CI inalterados

Sem as variáveis novas, o `runserver`, o `uv run pytest` e o CI se comportam
como hoje: mesmos caminhos, mesmas respostas, mesma suíte.

### RNF-05 — Documentado para quem clona

O `.env.example`, os dois READMEs (no mesmo PR, com as mesmas seções), a
referência de configurações e o `docs/stack.md` descrevem a variável nova, a
receita de build e o limite do rate limit atrás de proxy. O link da demo entra
nos dois READMEs só depois de o endereço responder com o conteúdo cadastrado.

## 7. Perguntas em aberto / decisões resolvidas

**Perguntas em aberto:** nenhuma.

**Decisões resolvidas:**

1. **Railway como plataforma.** Deploy a cada push na `main`, cobrança por uso,
   domínio próprio sem trocar de plano e Python na versão do `.python-version`.
2. **SQLite, mídia e cache num volume.** O projeto usa SQLite de propósito
   (um arquivo, sem servidor de banco, serve ao volume de um portfólio). O volume guarda os três num
   lugar só, e o projeto não ganha banco gerenciado nem bucket.
3. **O rate limit segue por `REMOTE_ADDR`** (decisão de projeto, 2026-11-16). Na
   Railway, esse valor é o IP do proxy, então todo visitante divide a mesma chave
   do rate limit. A demo roda com `MODO_DEMONSTRACAO=True`, que pula o rate limit
   (spec 005, decisão 4), e o limite fica documentado para quem publica sem o
   modo. Confiar no `CF-Connecting-IP` exigiria travar a origem com um segredo
   compartilhado, um custo que a demo não justifica.
4. **Só o domínio próprio fica público.** O endereço gerado pela plataforma não é
   publicado: a demo tem um endereço só, o de `ALLOWED_HOSTS`.
5. **Sem e-mail na demo.** As variáveis `EMAIL_*` ficam vazias: o modo
   demonstração responde antes do envio, e nenhuma credencial do Gmail vai para
   a plataforma.

## 8. Testes

### RF-08 — A suíte cobre a configuração de produção

A suíte (pytest, sem rede, sem tocar a pasta de dados real) precisa cobrir:

- `X-Forwarded-Proto: https` com `DEBUG=False`: sem redirect e cookies `Secure`;
  sem o cabeçalho: redirect 301;
- POST do formulário com `Origin` do próprio site aceito e com `Origin` de fora
  recusado com 403;
- leitura de `ALLOWED_HOSTS` com espaços, vírgula no fim e valor vazio;
- leitura de `DIRETORIO_DADOS` ausente e presente (caminhos do banco, da mídia e
  do cache);
- mídia com `DEBUG=False`: arquivo existente (200, `Content-Type`, `nosniff`),
  inexistente (404), pasta (404) e caminho com `../` (404);
- o log de produção: erro 500 registrado, 404 sem registro;
- a receita de build: o arquivo existe e traz o `--locked`, o extra `prod`, o
  `collectstatic`, o `migrate` antes do gunicorn e a porta da variável `PORT`.
