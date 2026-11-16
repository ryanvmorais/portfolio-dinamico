# Configurações notáveis (`portfolio/settings.py`)

Mapa: vai mexer em `settings.py`, middleware, CSP, estáticos, mídia, banco, log ou e-mail? Leia antes.

Um único `settings.py` para dev e produção, ramificado por `if not DEBUG:` —
sem `settings/base.py` + `dev.py` + `prod.py` (decisão de escala, ver
`specs/003-configuracao-seguranca/design.md`, ADR-01).

**Middleware (ordem importa):**
```
SecurityMiddleware → WhiteNoiseMiddleware → SessionMiddleware → CommonMiddleware →
CsrfViewMiddleware → AuthenticationMiddleware → MessageMiddleware →
XFrameOptionsMiddleware → CSPMiddleware
```

**Segurança em produção** (`DEBUG=False` ativa automaticamente):
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE = True`
- HSTS: 1 ano, incluindo subdomínios e preload
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`: atrás do proxy
  da plataforma o TLS termina antes do Django, e sem ler o cabeçalho o
  `SECURE_SSL_REDIRECT` entra em laço de redirect. Fixo em produção, sem
  variável: num servidor que entrega o Django direto à internet, sem proxy,
  remova a linha (spec 006, ADR-03). Sem `CSRF_TRUSTED_ORIGINS`: com o esquema
  `https` e o `Host` preservado pelo proxy, a origem do próprio site já passa
  (ADR-04)
- `ALLOWED_HOSTS` sem espaços e sem item vazio; vazia, a lista recusa todo host
- CSP via `django-csp` 4, no dicionário `CONTENT_SECURITY_POLICY` (o pacote
  ignora os nomes antigos `CSP_*`; o app `csp` em `INSTALLED_APPS` faz o
  `manage.py check` acusar um `CSP_*` esquecido): `script-src 'self'` (sem
  `'unsafe-inline'`: nenhum template usa script inline); `style-src` mantém `'unsafe-inline'` (2 atributos `style=""` inline na
  barra de progresso de habilidades); as fontes vêm de `'self'` (spec 004: o
  Google Fonts saiu de `style-src` e `font-src`)
- URL do Admin ofuscada via `ADMIN_URL` (defesa em profundidade, não
  substitui autenticação forte)

> ⚠️ **Não regredir:** ao adicionar qualquer `<script>` inline num template,
> revise o `script-src` do `CONTENT_SECURITY_POLICY` antes — o navegador bloqueia silenciosamente (só no
> console, sem erro no servidor). Ver `specs/003-configuracao-seguranca/`.

**Arquivos estáticos:** WhiteNoise com `CompressedStaticFilesStorage`, declarado
em `STORAGES["staticfiles"]`. Não use `STATICFILES_STORAGE`: o Django 6.1 ignora
esse nome e os estáticos saem sem compressão (issue #38). `collectstatic` é
obrigatório antes do deploy (o `railpack.json` o roda no build).

**Mídia:** a `servir_midia` (`app_portfolio/views.py`, rota `media/<caminho>` no
`portfolio/urls.py`) entrega o `MEDIA_ROOT` com e sem `DEBUG`, pelo
`django.views.static.serve`, com `Cache-Control: public, max-age=86400`. O
WhiteNoise não serve: ele indexa os arquivos quando o processo sobe, e a imagem
enviada pelo Admin só apareceria no reinício seguinte. `../` e pasta respondem
404; o tipo `image/webp` é registrado no `mimetypes` porque o Python 3.12 só o
conhece pelo `mime.types` do sistema (spec 006, ADR-06).

**Dados graváveis (`DIRETORIO_DADOS`):** o banco (`db.sqlite3`), o `MEDIA_ROOT`
(`media/`) e o cache (`django_cache/`) ficam nessa pasta; vazia, é a raiz do
repositório. Num contêiner, aponte para o volume persistente, senão os três
somem a cada deploy. Caminho relativo parte do `BASE_DIR` (spec 006, ADR-05).

> ⚠️ **Não regredir (cache):** o rate limit usa `FileBasedCache` em `django_cache/`, nunca
> `LocMemCache` (por processo: com vários workers o limite por IP se multiplica). Ver
> `docs/referencia/dependencias-e-cache.md`.

**Banco de dados:** SQLite em desenvolvimento e em produção, no
`DIRETORIO_DADOS`. Uma instância só monta o volume, então o desenho supõe uma
réplica do serviço; o gunicorn pode ter mais de um worker (`WEB_CONCURRENCY`). O
`psycopg2-binary` segue no extra `prod` para quem trocar o `DATABASES` por
PostgreSQL à mão (sem `dj-database-url`).

**Log em produção:** com `DEBUG=False`, o `LOGGING` manda à saída de erro do
processo (`StreamHandler` na raiz, nível WARNING) o traceback do 500 e a falha de
envio de e-mail; o `django.request` fica em ERROR para o 404 de robôs não encher o
log. Sem isso, o padrão do Django só mandaria o 500 por e-mail aos `ADMINS`, que o
projeto não define (spec 006, ADR-07).

**E-mail:** o `MAILERS` do Django 6.1 (os `EMAIL_*` estão depreciados) define um
mailer `default` com o SMTP do Gmail fixo (`smtp.gmail.com:587`, TLS); o TLS
verifica o certificado do Gmail com os certificados do sistema. Requer "Senha de
App" do Google, não a senha normal da conta. O endereço da conta fica no
`ENDERECO_CONTATO`, remetente e destino da notificação do formulário: com o
`MAILERS` definido, ler `settings.EMAIL_HOST_USER` levanta `AttributeError`. Com
`DEBUG=True` e `EMAIL_USER` vazio, o mailer `default` vira o de console (o e-mail
sai no terminal do `runserver`) e `ENDERECO_CONTATO` recebe `contato@example.com`;
em produção, `EMAIL_USER` vazio segue no SMTP e o envio falha à vista (spec 005,
ADR-06).

**Modo demonstração:** `MODO_DEMONSTRACAO` (padrão `False`, lido como o `DEBUG`).
Ligado, o envio válido do formulário de contato para depois da validação: não
grava, não envia e não cria a chave do rate limit, e o visitante vê o aviso com
link para `URL_REPOSITORIO` (constante no `settings.py`; num fork, troque pelo
endereço do fork). Ver `specs/005-modo-demonstracao/`.
