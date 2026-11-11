"""
Rotas globais do projeto.

Monta o painel administrativo num caminho configurável, inclui as rotas do
app do portfólio e, só em desenvolvimento, serve os arquivos de mídia.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path
from django.views.generic.base import RedirectView

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
]


# ---------------------------------------------------------------------------
# Mídia em desenvolvimento
# ---------------------------------------------------------------------------


# Em produção quem serve /media/ é o servidor web; o Django só o faz com
# DEBUG=True, para as fotos enviadas pelo admin aparecerem no runserver.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
