"""
Configurações do projeto Django.

Um arquivo só para desenvolvimento e produção: o que muda entre os dois vem
do ``.env`` (``SECRET_KEY``, ``DEBUG``, ``ALLOWED_HOSTS``, ``ADMIN_URL``,
``MODO_DEMONSTRACAO``, ``URL_PUBLICA``, ``DIRETORIO_DADOS`` e as credenciais de
e-mail). Com
``DEBUG=False`` liga o HTTPS obrigatório (atrás do proxy da plataforma), os
cookies seguros, o HSTS e o log de erros na saída de erro do processo.
"""

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from csp.constants import NONE, SELF, UNSAFE_INLINE
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 1. Ambiente e segurança básica
# ---------------------------------------------------------------------------

# Raiz do repositório: os caminhos abaixo (.env, templates, static) partem dela.
BASE_DIR = Path(__file__).resolve().parent.parent

# Caminho absoluto do .env: o servidor WSGI não roda a partir da raiz do
# projeto, então um caminho relativo não acharia o arquivo no deploy.
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Pasta dos dados graváveis: banco, mídia enviada pelo Admin e cache do rate
# limit. Em produção aponta para o volume montado pela plataforma, que sobrevive
# ao deploy; o resto do contêiner é recriado a cada versão (spec 006, ADR-05).
# Vazia, fica a raiz do repositório. O "/" do Path resolve os dois casos: um
# caminho absoluto (/data) substitui o BASE_DIR, e um relativo fica dentro dele.
_DIRETORIO_DADOS = os.getenv("DIRETORIO_DADOS", "").strip()
DIRETORIO_DADOS = BASE_DIR / _DIRETORIO_DADOS if _DIRETORIO_DADOS else BASE_DIR

# Assina sessões, cookies e tokens CSRF; vem só do .env, nunca do código.
SECRET_KEY = os.getenv("SECRET_KEY")

# Sem chave, o servidor não sobe. A mensagem mostra o caminho procurado,
# que é o que se precisa saber quando o .env não está onde se esperava.
if not SECRET_KEY:
    raise ValueError(
        f"ERRO: A variável SECRET_KEY não foi encontrada no arquivo .env! Caminho verificado: {env_path}"
    )

# Padrão False (seguro por padrão): só um DEBUG=true explícito no .env liga as
# páginas de erro detalhadas, que nunca podem aparecer em produção.
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Modo demonstração do formulário de contato (spec 005): ligado, o envio valida
# os campos mas não grava a mensagem nem envia o e-mail, e o visitante vê um
# aviso de que o formulário é de demonstração. Padrão False: quem clona estuda
# o fluxo completo; só a demo pública liga, para não guardar dado de visitante.
# Ligado, também identifica a demo do template para buscadores e redes sociais
# (título, description e imagem do cartão) e publica o security.txt com o
# contato do repositório (spec 007).
MODO_DEMONSTRACAO = os.getenv("MODO_DEMONSTRACAO", "False").lower() == "true"

# Repositório do código, para onde apontam os avisos do modo demonstração.
# Num fork, troque pelo endereço do seu repositório.
URL_REPOSITORIO = "https://github.com/ryanvmorais/portfolio-dinamico"


def _ler_url_publica(valor: str) -> str:
    """
    Valida o endereço público do site e o devolve sem a barra final.

    O endereço vira canonical, ``og:url`` e sitemap, que o buscador guarda por
    semanas: um valor sem esquema ou com caminho publicaria endereços errados, e
    o erro só apareceria no relatório de indexação. Por isso a subida falha na
    hora, como a falta de ``SECRET_KEY`` (spec 007, ADR-04).

    Args:
        valor (str): Conteúdo de ``URL_PUBLICA`` no ambiente.

    Returns:
        str: O endereço sem a barra final, ou ``""`` se a variável estiver vazia.

    Raises:
        ValueError: Se o valor não for ``http(s)://domínio``, com ou sem a barra
            final, sem caminho, query nem fragmento.
    """
    valor = valor.strip()
    if not valor:
        return ""
    partes = urlsplit(valor)
    if (
        partes.scheme not in ("http", "https")
        or not partes.netloc
        or partes.path not in ("", "/")
        or partes.query
        or partes.fragment
    ):
        raise ValueError(
            "ERRO: URL_PUBLICA deve ser só o esquema e o domínio, como "
            f"https://seu-dominio.com.br; valor recebido: {valor!r}"
        )
    return valor.rstrip("/")


# Endereço público do site (spec 007). Única fonte do endereço absoluto do
# canonical, do og:url, do sitemap e do security.txt: nunca o Host do pedido,
# que o cliente escolhe. Vazia, o site sobe sem canonical nem sitemap.
URL_PUBLICA = _ler_url_publica(os.getenv("URL_PUBLICA", ""))

# Caminho do painel administrativo. Em produção, troque no .env: /admin/ é o
# primeiro caminho que robôs de força bruta testam.
ADMIN_URL_PATH = os.getenv("ADMIN_URL", "admin/")

# Domínios aceitos no cabeçalho Host (defesa contra Host header poisoning); em
# desenvolvimento aceita qualquer um.
# No .env use: ALLOWED_HOSTS=seu-dominio.com.br, www.seu-dominio.com.br
# Espaços e item vazio (vírgula no fim) saem da lista. Vazia, a lista recusa
# todo host: um deploy sem a variável falha fechado.
ALLOWED_HOSTS = (
    ["*"]
    if DEBUG
    else [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Só pelas checagens do django-csp: com o app instalado, um CSP_* do formato
    # antigo vira erro no "manage.py check" em vez de sumir em silêncio.
    "csp",
    "app_portfolio.apps.AppPortfolioConfig",
]


# ---------------------------------------------------------------------------
# 2. Apps, middlewares e templates
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Logo depois do SecurityMiddleware, como pede o WhiteNoise: serve os
    # estáticos sem passar pelas camadas seguintes.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",  # envia o cabeçalho Content-Security-Policy
    # Nega câmera, microfone, localização e afins (o Django não tem configuração
    # para este cabeçalho).
    "app_portfolio.middleware.PermissionsPolicyMiddleware",
]

ROOT_URLCONF = "portfolio.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "portfolio.wsgi.application"

# SQLite: um arquivo, sem servidor de banco; serve ao volume de um portfólio.
# Fica no DIRETORIO_DADOS, para o deploy não apagar o conteúdo do Admin.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DIRETORIO_DADOS / "db.sqlite3",
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# 3. Estáticos e mídia
# ---------------------------------------------------------------------------

STATIC_URL = "static/"

# Fonte dos estáticos do projeto (fora dos apps).
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# Destino do collectstatic; é desta pasta que o WhiteNoise serve o CSS/JS.
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Uploads feitos pelo admin (fotos de projeto e de perfil, currículo). Ficam no
# DIRETORIO_DADOS, junto do banco que guarda o nome de cada arquivo.
MEDIA_URL = "media/"
MEDIA_ROOT = DIRETORIO_DADOS / "media"

# WhiteNoise: comprime os arquivos estáticos (gzip) no collectstatic.
# O nome tem de ser STORAGES: o Django 6.1 ignora o antigo STATICFILES_STORAGE
# (removido no 5.1), e com ele os estáticos saíam sem compressão (issue #38).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# 4. Cabeçalhos de segurança e HTTPS
# ---------------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"  # nenhuma página pode ser enquadrada (clickjacking)

# CSP: de onde a página pode carregar scripts, estilos, imagens e fontes. O
# django-csp 4 só lê este dicionário: os antigos CSP_DEFAULT_SRC, CSP_SCRIPT_SRC
# etc. são ignorados, e com eles o cabeçalho não saía em resposta nenhuma.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        # 'unsafe-inline' só em estilo: a barra de progresso das habilidades usa
        # style="" inline. Script nunca: nenhum template tem <script> inline.
        "style-src": [SELF, UNSAFE_INLINE],
        "script-src": [SELF],
        "img-src": [SELF, "data:", "https:"],
        # As fontes vêm de static/fonts/ (spec 004, RF-17): o Google Fonts saiu
        # de style-src e font-src.
        "font-src": [SELF],
        # base-uri e form-action não herdam o default-src: sem elas, uma tag
        # <base> ou um <form> injetado poderia apontar para fora do site.
        "base-uri": [NONE],
        "form-action": [SELF],
        # Herdaria o 'self'; 'none' explícito, porque o site não embute plugin.
        "object-src": [NONE],
        # O mesmo que o X-Frame-Options DENY, no padrão atual dos navegadores.
        "frame-ancestors": [NONE],
    }
}

# Só em produção: o runserver não fala HTTPS, então com estas opções o site
# local não abriria.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS: o navegador passa a usar só HTTPS por 1 ano (31536000 s).
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Atrás do proxy da plataforma o TLS termina antes do Django, que recebe
    # HTTP. O proxy avisa o protocolo original neste cabeçalho; sem ler, o
    # SECURE_SSL_REDIRECT redireciona para sempre (spec 006, ADR-03). Num
    # servidor que entrega o Django direto à internet, sem proxy, remova a
    # linha: o cliente poderia mandar o cabeçalho e pular o redirect.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # O LOGGING padrão do Django só manda o erro 500 por e-mail aos ADMINS, que
    # o projeto não define: sem isto, o erro não aparece no log do serviço
    # (spec 006, ADR-07).
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "root": {"handlers": ["console"], "level": "WARNING"},
        # 404 é registrado como WARNING no django.request; ERROR deixa só o 500.
        "loggers": {"django.request": {"level": "ERROR"}},
    }

# ---------------------------------------------------------------------------
# 5. E-mail e cache
# ---------------------------------------------------------------------------

# Conta Gmail que envia a notificação do formulário de contato e a recebe: a
# view usa este endereço como remetente e como destino.
ENDERECO_CONTATO = os.getenv("EMAIL_USER")

# MAILERS substitui os EMAIL_* (depreciados no Django 6.1). Com MAILERS
# definido, ler settings.EMAIL_* levanta AttributeError: o endereço da conta
# mora no ENDERECO_CONTATO, não no EMAIL_HOST_USER. Any: as OPTIONS misturam
# str, int, bool e None.
MAILERS: dict[str, dict[str, Any]] = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": "smtp.gmail.com",
            "port": 587,
            "use_tls": True,
            "username": ENDERECO_CONTATO,
            "password": os.getenv("EMAIL_PASS"),
        },
    },
}

# Em desenvolvimento sem conta Gmail, o e-mail do formulário sai impresso no
# terminal do runserver, com um endereço do domínio reservado example.com (RFC
# 2606) como remetente e destino. Só com DEBUG: em produção, EMAIL_USER vazio
# segue falhando no envio, para um deploy sem e-mail não dizer "Mensagem
# enviada!" sem enviar nada (spec 005, ADR-06). O console não aceita as
# OPTIONS do SMTP, então o mailer inteiro é trocado.
if DEBUG and not ENDERECO_CONTATO:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
    ENDERECO_CONTATO = "contato@example.com"

DEFAULT_FROM_EMAIL = f"Projeto Portfólio <{ENDERECO_CONTATO}>"

# Cache em arquivo: usado pelo rate limit do formulário de contato.
# LocMemCache é por processo -- com gunicorn rodando mais de 1 worker (ver
# extra "prod"), cada worker teria seu próprio contador e o limite por IP
# seria multiplicado pelo número de workers (achado da auditoria de
# segurança). FileBasedCache é compartilhado entre processos sem exigir
# infra extra (Redis/Memcached). Fica no DIRETORIO_DADOS, junto do banco.
# O backend é uma subclasse do FileBasedCache: o add() do Django checa e grava
# sem trava, e pedidos simultâneos passariam todos pelo limite; a subclasse
# serializa as reservas com uma trava de arquivo (app_portfolio/cache.py).
CACHES = {
    "default": {
        "BACKEND": "app_portfolio.cache.CacheArquivoAtomico",
        "LOCATION": DIRETORIO_DADOS / "django_cache",
    }
}
