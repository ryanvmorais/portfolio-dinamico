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

# Design — Hospedagem da demo na Railway

## 1. Visão geral

A Railway constrói o projeto com o Railpack, o construtor padrão dela, a partir
de um `railpack.json` na raiz. Esse arquivo declara o build e o start: no build,
`uv sync` pelo lock e `collectstatic`; no start, `migrate` e o gunicorn na porta
`PORT`. O Railpack lê a versão do Python no `.python-version`.

O `settings.py` continua único (spec 003, ADR-01). Ele ganha uma variável,
`DIRETORIO_DADOS`, que leva o banco, a mídia e o cache para o volume montado
pela plataforma. Dentro do bloco `if not DEBUG:`, ganha o cabeçalho do proxy
(`SECURE_PROXY_SSL_HEADER`) e um `LOGGING` que manda os erros para a saída de
erro do processo. A mídia passa a ser servida por uma view fina sobre o
`django.views.static.serve`, ligada também com `DEBUG=False`.

## 2. Componentes

| Arquivo | Muda o quê |
| --- | --- |
| `railpack.json` (novo) | Build e start (RF-01) |
| `portfolio/settings.py` | `DIRETORIO_DADOS`, `ALLOWED_HOSTS` sem espaços, `SECURE_PROXY_SSL_HEADER`, `LOGGING` (RF-02, RF-04, RF-05, RF-07) |
| `app_portfolio/views.py` | View `servir_midia` (RF-06) |
| `portfolio/urls.py` | Rota de mídia sempre ligada, no lugar do `static()` só com `DEBUG` (RF-06) |
| `app_portfolio/tests.py` | Testes do RF-08, reaproveitando o `_carregar_settings` e a fixture `disable_real_email` |
| `.env.example`, `README.md`, `README.en.md`, `CLAUDE.md`, `docs/referencia/configuracoes.md`, `docs/referencia/dependencias-e-cache.md`, `docs/stack.md` | Variável nova, receita de build, limite do rate limit atrás de proxy, link da demo (RNF-05) |

### `railpack.json`

```json
{
  "$schema": "https://schema.railpack.com",
  "steps": {
    "build": {
      "commands": [
        "uv sync --locked --no-dev --extra prod",
        "python manage.py collectstatic --noinput"
      ]
    }
  },
  "deploy": {
    "startCommand": "python manage.py migrate --noinput && gunicorn portfolio.wsgi:application --bind 0.0.0.0:${PORT:-8000}"
  }
}
```

- `--locked` falha se o lock não bater com o `pyproject.toml` (RF-01). O CI usa
  `--frozen`, que instala sem conferir; o build de produção confere.
- O `collectstatic` do build importa o `settings.py`, que exige `SECRET_KEY`: na
  Railway, as variáveis do serviço também valem no build.
- O número de workers não fica fixo no comando: o gunicorn lê `WEB_CONCURRENCY`
  (padrão 1). Mais de um worker é seguro, porque o `FileBasedCache` é
  compartilhado entre processos (RNF-03).

### `settings.py`

```python
# Pasta dos dados graváveis: banco, mídia enviada pelo Admin e cache do rate
# limit. Em produção aponta para o volume montado pela plataforma.
_DIRETORIO_DADOS = os.getenv("DIRETORIO_DADOS", "").strip()
DIRETORIO_DADOS = BASE_DIR / _DIRETORIO_DADOS if _DIRETORIO_DADOS else BASE_DIR
```

O operador `/` do `Path` resolve os dois casos: um caminho absoluto
(`/data`) substitui o `BASE_DIR`, e um relativo (`dados`) fica dentro dele.
`DATABASES["default"]["NAME"]`, `MEDIA_ROOT` e `CACHES["default"]["LOCATION"]`
passam a partir de `DIRETORIO_DADOS`. Sem a variável, os três caminhos são os de
hoje (RF-05, RNF-04).

```python
ALLOWED_HOSTS = (
    ["*"]
    if DEBUG
    else [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
)
```

Com a variável vazia, a lista fica `[]` em vez de `[""]`: o efeito é o mesmo
(todo host recusado), e o `check --deploy` passa a avisar da lista vazia
(`security.W020`). O CI já define `ALLOWED_HOSTS` nesse passo (RF-04).

No bloco `if not DEBUG:`:

```python
# Atrás do proxy da plataforma o TLS termina antes do Django, que recebe HTTP.
# O proxy avisa o protocolo original neste cabeçalho; sem ler, o
# SECURE_SSL_REDIRECT redireciona para sempre.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# O LOGGING padrão do Django só manda o erro 500 por e-mail aos ADMINS, que o
# projeto não define: sem isto, o erro não aparece no log do serviço.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    # 404 é registrado como WARNING no django.request; ERROR deixa só o 500.
    "loggers": {"django.request": {"level": "ERROR"}},
}
```

O erro 500 sobe do `django.request` para o logger `django` (cujo console só
imprime com `DEBUG=True`) e dele para a raiz, que imprime no `stderr`. O
`logger.exception` da falha de e-mail (spec 002) vem do `app_portfolio.views`, de
nível ERROR, e também chega à raiz (RF-07).

### `servir_midia` e a rota

```python
@require_safe
@cache_control(public=True, max_age=86400)
def servir_midia(request: HttpRequest, caminho: str) -> HttpResponseBase:
    return serve(request, caminho, document_root=settings.MEDIA_ROOT)
```

```python
path(f"{settings.MEDIA_URL}<path:caminho>", servir_midia, name="midia"),
```

O `serve` junta o caminho ao `MEDIA_ROOT` com `safe_join` (o `../` vira 404),
recusa pasta com 404 (sem `show_indexes`), põe o `Content-Type` pela extensão e
responde 304 ao `If-Modified-Since`. O `nosniff` vem do `SecurityMiddleware`
(`SECURE_CONTENT_TYPE_NOSNIFF`), e a CSP do `django-csp` também vale nessas
respostas. A view lê o `MEDIA_ROOT` a cada pedido, então o teste troca a pasta
pela fixture `settings` sem recarregar as rotas. O 404 levanta `Http404`, que
renderiza o `404.html` com `DEBUG=False`; o `cache_control` só marca a resposta
200 ou 304 (RF-06).

## 3. Modelo de dados

Nenhuma mudança. Nenhuma migração.

## 4. Interfaces

### Variáveis de ambiente (novas ou com uso novo)

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `DIRETORIO_DADOS` | raiz do repositório | Pasta de `db.sqlite3`, `media/` e `django_cache/`; na Railway, o caminho do volume (ex.: `/data`) |
| `PORT` | 8000 | Porta do gunicorn; a plataforma define |
| `WEB_CONCURRENCY` | 1 | Workers do gunicorn (lida pelo próprio gunicorn) |
| `ALLOWED_HOSTS` | vazio (recusa tudo) | Agora tolera espaços e vírgula no fim |

A demo roda com `DEBUG=False`, `MODO_DEMONSTRACAO=True`, `ALLOWED_HOSTS` com o
domínio próprio, `ADMIN_URL` trocado, `DIRETORIO_DADOS` no volume e `EMAIL_*`
vazias.

### Rotas

| Rota | Antes | Depois |
| --- | --- | --- |
| `/media/<caminho>` | Só com `DEBUG=True` (`static()`) | Sempre, pela `servir_midia` (GET e HEAD) |

## 5. Decisões técnicas (ADRs)

### ADR-01 — Build e start no `railpack.json`

- **Decisão:** um `railpack.json` na raiz, com os comandos de build e o de start.
- **Alternativas:** (a) Dockerfile; (b) `railway.json` com `buildCommand` e
  `startCommand`; (c) só o painel da plataforma.
- **Porquê:** o Railpack já detecta o Python pelo `.python-version` e o uv pelo
  `uv.lock`; o arquivo só fixa os comandos, com esquema validável. O Dockerfile
  traria imagem base, instalação do uv e cache de camadas para manter à mão. O
  painel deixaria a receita fora do repositório, onde quem clona não a vê.
- **Trade-off:** o arquivo só serve ao Railpack. Em outra plataforma, os comandos
  são os mesmos, mas vão para o formato dela.

### ADR-02 — `migrate` no start, antes do gunicorn

- **Decisão:** o start roda `migrate --noinput && gunicorn ...`.
- **Alternativas:** (a) `migrate` no build; (b) comando de pré-deploy da
  plataforma.
- **Porquê:** o banco mora no volume, que o build não vê: (a) migraria um banco
  descartável. No start, a ordem fica num comando só, o mesmo que rodaria em
  qualquer servidor, e o `&&` impede o gunicorn de subir sobre uma migração que
  falhou. (b) acrescenta um passo próprio da plataforma, sem ganho numa
  instância só.
- **Trade-off:** cada reinício roda o `migrate`, que sem migração pendente leva
  menos de um segundo.

### ADR-03 — `SECURE_PROXY_SSL_HEADER` fixo em produção

- **Decisão:** com `DEBUG=False`, o Django sempre confia no `X-Forwarded-Proto`.
- **Alternativas:** (a) uma variável para ligar (`ATRAS_DE_PROXY`); (b) não ler
  o cabeçalho e desligar o `SECURE_SSL_REDIRECT`, deixando o redirect para o
  proxy.
- **Porquê:** toda hospedagem de Django com HTTPS põe um proxy na frente
  (plataforma, nginx, Caddy), e todos mandam esse cabeçalho; uma variável a mais
  seria um jeito novo de errar o deploy. (b) tiraria o redirect do código e o
  `check --deploy` passaria a avisar.
- **Trade-off:** num servidor sem proxy, o cliente poderia mandar o cabeçalho e
  pular o redirect, mas só no pedido dele, e o cookie `Secure` e o HSTS seguem
  valendo. Um site que entrega o Django direto à internet precisa remover a linha
  (fica dito no comentário).

### ADR-04 — Sem `CSRF_TRUSTED_ORIGINS`

- **Decisão:** a verificação de origem do CSRF fica como está.
- **Alternativas:** `CSRF_TRUSTED_ORIGINS` lido do ambiente.
- **Porquê:** o Django aceita o `Origin` igual a `esquema://host` do pedido. Com o
  ADR-03, o esquema é `https`; o proxy da plataforma e a Cloudflare preservam o
  `Host`, que está em `ALLOWED_HOSTS`. A origem do próprio site já passa (RF-03).
- **Trade-off:** atrás de um proxy que reescreva o `Host`, a variável seria
  necessária; não é o caso da demo, e o teste do RF-03 acusa se deixar de passar.

### ADR-05 — Uma variável só para os dados graváveis

- **Decisão:** `DIRETORIO_DADOS` define a pasta do banco, da mídia e do cache.
- **Alternativas:** (a) uma variável por caminho (`CAMINHO_BANCO`, `MEDIA_ROOT`,
  `CAMINHO_CACHE`); (b) `DATABASE_URL` com `dj-database-url`.
- **Porquê:** os três vão juntos para o mesmo volume; três variáveis seriam três
  chances de deixar um fora dele e perder dado no deploy seguinte. (b) traria uma
  dependência (RNF-01) para um banco que segue SQLite.
- **Trade-off:** quem quiser a mídia num disco e o banco em outro precisa editar o
  `settings.py`.

### ADR-06 — Mídia pelo `serve` do Django, atrás de uma view fina

- **Decisão:** a `servir_midia` chama o `django.views.static.serve` com
  `Cache-Control: public, max-age=86400`, com e sem `DEBUG`.
- **Alternativas:** (a) WhiteNoise; (b) bucket (S3, R2) com `django-storages`;
  (c) servidor web na frente.
- **Porquê:** (a) o WhiteNoise indexa os arquivos quando o processo sobe, e a
  mídia nova enviada pelo Admin só apareceria no reinício seguinte. (b) traz
  dependência, credencial e cobrança para uma demo com poucas imagens (decisão
  resolvida 2). (c) não existe na plataforma. A Cloudflare guarda as imagens em
  cache pela extensão, então o Django serve cada arquivo poucas vezes.
- **Trade-off:** a documentação do Django desaconselha o `serve` em produção por
  eficiência e por não ter passado por auditoria de segurança. Aqui o tráfego é
  baixo, o envio é só pelo Admin (o `ImageField` passa pelo Pillow, que recusa o
  que não é imagem) e a CSP e o `nosniff` valem nas respostas. O `max-age` de um
  dia não esconde troca de imagem: o Django gera nome novo quando o arquivo já
  existe.

### ADR-07 — Erros na saída de erro, sem o 404

- **Decisão:** `LOGGING` com um `StreamHandler` na raiz (WARNING) e o
  `django.request` em ERROR, só com `DEBUG=False`.
- **Alternativas:** (a) definir `ADMINS` e mandar o erro por e-mail; (b) serviço
  de monitoramento (Sentry).
- **Porquê:** a plataforma já guarda o `stdout` e o `stderr` de cada deploy; (a)
  exigiria e-mail configurado, que a demo não tem (decisão resolvida 5), e (b)
  traria dependência e conta. O 404 fica fora porque robôs testam caminhos o dia
  inteiro e afogariam o erro real.
- **Trade-off:** o aviso de `Host` inválido (`django.security.DisallowedHost`) e a
  falha de CSRF (`django.security.csrf`) continuam no log; com o domínio gerado
  pela plataforma fora do ar (decisão resolvida 4), são raros.

## 6. Impacto e dependências

- **Dependências:** nenhuma nova. O `gunicorn` já está no extra `prod`.
- **Desenvolvimento:** sem `DIRETORIO_DADOS`, os caminhos não mudam; a mídia passa
  a sair com `Cache-Control` também no `runserver`, o que não atrapalha porque a
  troca de imagem gera nome novo.
- **`portfolio/urls.py`:** o `static()` e o `if settings.DEBUG:` saem; o
  docstring do módulo e o comentário da seção de mídia mudam junto.
- **CI:** nada muda; o passo `check --deploy` já define `DEBUG=False` e
  `ALLOWED_HOSTS`.
- **Spec 002:** fica como está (registro concluído). O limite do rate limit atrás
  de proxy vai para `docs/referencia/dependencias-e-cache.md`, seção "Cache do
  rate limit".
- **Operação fora do repositório:** a configuração da hospedagem e a carga do
  conteúdo não passam pelo código; o link entra nos READMEs só com a demo no ar
  (RNF-05).

## 7. Estratégia de testes

Tudo em `app_portfolio/tests.py`, sem rede e sem tocar a pasta de dados real:

- **Leitura do `settings.py`:** o `_carregar_settings` (spec 005) carrega uma
  cópia avulsa com o ambiente pedido; a lista de variáveis que ele limpa ganha
  `ALLOWED_HOSTS` e `DIRETORIO_DADOS`. Cobre `ALLOWED_HOSTS` com espaços, vírgula
  no fim e vazio; `DIRETORIO_DADOS` ausente, absoluto e relativo (caminhos do
  banco, da mídia e do cache); `SECURE_PROXY_SSL_HEADER` e `LOGGING` presentes com
  `DEBUG=False` e ausentes com `DEBUG=True`; o nível do `django.request` e o
  handler da raiz.
- **Proxy e CSRF:** a fixture `settings` liga `SECURE_SSL_REDIRECT`, os cookies
  seguros e o `SECURE_PROXY_SSL_HEADER`. GET com `HTTP_X_FORWARDED_PROTO="https"`:
  200 e `csrftoken` com `secure`; sem ele: 301. POST com
  `Client(enforce_csrf_checks=True)`, token lido do cookie e `HTTP_ORIGIN` do
  próprio host: passa pelo CSRF (o formulário vai inválido, para a view responder
  sem gravar nem enviar); com `HTTP_ORIGIN` de outro site: 403.
- **Mídia:** `settings.MEDIA_ROOT` aponta para o `tmp_path`, com um `.webp` e uma
  subpasta. Arquivo: 200, `Content-Type: image/webp`, `nosniff`, `Cache-Control`
  com `max-age=86400`; inexistente, pasta e `../`: 404; POST: 405.
- **Receita de build:** lê o `railpack.json` como JSON e confere `--locked`,
  `--extra prod`, `collectstatic`, `migrate` antes de `gunicorn` e
  `${PORT:-8000}`.
