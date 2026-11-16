"""
Rotas globais do projeto.

Monta o painel administrativo num caminho configurável, inclui as rotas do
app do portfólio e serve os arquivos de mídia, com ou sem DEBUG.
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path
from django.views.generic.base import RedirectView

from app_portfolio.views import servir_midia

urlpatterns = [
    # O caminho do admin vem do settings (ADMIN_URL no .env) em vez de
    # "admin/": a tela de login fica fora do caminho que robôs testam primeiro.
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path("", include("app_portfolio.urls")),
    # O navegador pede /favicon.ico por conta própria. O arquivo é o
    # favicon.webp (a rota apontava para um favicon.png que não existe e
    # respondia 404; spec 004, RF-20). staticfiles_storage.url() devolve o
    # caminho absoluto (/static/...), não o relativo que STATIC_URL sozinho dava.
    path(
        "favicon.ico",
        RedirectView.as_view(url=staticfiles_storage.url("icons/favicon.webp")),
    ),
    # Mídia enviada pelo admin, também com DEBUG=False: a plataforma da demo
    # não tem servidor web na frente do Django para servir /media/, e o
    # static() do Django só funciona com DEBUG (spec 006, RF-06). O Django
    # devolve o MEDIA_URL com a barra inicial ("/media/"), e a rota não leva.
    path(f"{settings.MEDIA_URL.lstrip('/')}<path:caminho>", servir_midia, name="midia"),
]
