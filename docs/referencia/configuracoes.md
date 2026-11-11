# Configurações notáveis (`portfolio/settings.py`)

Mapa: vai mexer em `settings.py`, middleware, CSP, estáticos, banco ou e-mail? Leia antes.

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
- CSP via `django-csp`: `script-src 'self'` (sem `'unsafe-inline'`: nenhum
  template usa script inline);
  `style-src` mantém `'unsafe-inline'` (2 atributos `style=""` inline na
  barra de progresso de habilidades); as fontes vêm de `'self'` (spec 004: o
  Google Fonts saiu de `style-src` e `font-src`)
- URL do Admin ofuscada via `ADMIN_URL` (defesa em profundidade, não
  substitui autenticação forte)

> ⚠️ **Não regredir:** ao adicionar qualquer `<script>` inline num template,
> revise `CSP_SCRIPT_SRC` antes — o navegador bloqueia silenciosamente (só no
> console, sem erro no servidor). Ver `specs/003-configuracao-seguranca/`.

**Arquivos estáticos:** WhiteNoise com `CompressedStaticFilesStorage`, declarado
em `STORAGES["staticfiles"]`. Não use `STATICFILES_STORAGE`: o Django 6.1 ignora
esse nome e os estáticos saem sem compressão (issue #38). `collectstatic` é
obrigatório antes do deploy.

> ⚠️ **Não regredir (cache):** o rate limit usa `FileBasedCache` em `django_cache/`, nunca
> `LocMemCache` (por processo: com vários workers o limite por IP se multiplica). Ver
> `docs/referencia/dependencias-e-cache.md`.

**Banco de dados:** SQLite em desenvolvimento; PostgreSQL em produção via
`psycopg2-binary` (extra `prod`), configurado manualmente em `DATABASES` (sem
`dj-database-url` — troca direta na config quando o deploy usa Postgres).

**E-mail:** SMTP do Gmail fixo (`smtp.gmail.com:587`); `EMAIL_SSL_CONTEXT`
via `certifi` para funcionar em qualquer SO. Requer "Senha de App" do Google,
não a senha normal da conta.
