"""
Configurações do projeto Django.

Um arquivo só para desenvolvimento e produção: o que muda entre os dois vem
do ``.env`` (``SECRET_KEY``, ``DEBUG``, ``ALLOWED_HOSTS``, ``ADMIN_URL`` e as
credenciais de e-mail). Com ``DEBUG=False`` liga o HTTPS obrigatório, os
cookies seguros e o HSTS.
"""

import os
import ssl
from pathlib import Path

import certifi
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

# Caminho do painel administrativo. Em produção, troque no .env: /admin/ é o
# primeiro caminho que robôs de força bruta testam.
ADMIN_URL_PATH = os.getenv("ADMIN_URL", "admin/")

# Domínios aceitos no cabeçalho Host (defesa contra Host header poisoning); em
# desenvolvimento aceita qualquer um.
# No .env use: ALLOWED_HOSTS=djangofullstackportfolio.pythonanywhere.com
ALLOWED_HOSTS = ["*"] if DEBUG else os.getenv("ALLOWED_HOSTS", "").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
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

# Destino do collectstatic; é desta pasta que o PythonAnywhere serve o CSS/JS.
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Uploads feitos pelo admin (fotos de projeto e de perfil, currículo).
MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

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

# CSP: de onde a página pode carregar scripts, estilos, imagens e fontes.
CSP_DEFAULT_SRC = ("'self'",)
# As fontes agora vêm de static/fonts/ (spec 004, RF-17): o Google Fonts saiu de
# style-src e font-src.
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_SCRIPT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'",)

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

# ---------------------------------------------------------------------------
# 5. E-mail e cache
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASS")
DEFAULT_FROM_EMAIL = f"Projeto Portfólio <{EMAIL_HOST_USER}>"

# Cadeia de CAs do certifi: em alguns servidores o Python não acha os
# certificados do sistema e o TLS com o Gmail falharia.
EMAIL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Cache em arquivo: usado pelo rate limit do formulário de contato.
# LocMemCache é por processo -- com gunicorn rodando mais de 1 worker (ver
# extra "prod"), cada worker teria seu próprio contador e o limite por IP
# seria multiplicado pelo número de workers (achado da auditoria de
# segurança). FileBasedCache é compartilhado entre processos sem exigir
# infra extra (Redis/Memcached) no plano gratuito do PythonAnywhere.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "django_cache",
    }
}
