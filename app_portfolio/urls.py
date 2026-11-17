"""
Rotas do app do portfólio.

O site é uma página única: a raiz aponta para a view ``home``. O ``name``
deixa os templates usarem ``{% url "home" %}`` em vez do caminho fixo, então
mudar a rota não quebra nenhum link.

Os arquivos que buscadores e pesquisadores de segurança procuram em caminhos
fixos (``robots.txt``, ``sitemap.xml`` e ``.well-known/security.txt``) saem do
módulo ``descoberta`` (spec 007). O favicon SVG e o ícone de tela inicial,
gerados das iniciais do perfil, saem do módulo ``marca`` (spec 008); o
``apple-touch-icon.png`` fica na raiz porque o iOS o procura ali mesmo sem o
``<link>``.
"""

from django.urls import path

from . import descoberta, marca, views

urlpatterns = [
    path("", views.home, name="home"),
    path("robots.txt", descoberta.robots_txt, name="robots_txt"),
    path("sitemap.xml", descoberta.sitemap_xml, name="sitemap_xml"),
    path(
        ".well-known/security.txt",
        descoberta.security_txt,
        name="security_txt",
    ),
    path("favicon.svg", marca.favicon_svg, name="favicon_svg"),
    path(
        "apple-touch-icon.png",
        marca.icone_tela_inicial,
        name="icone_tela_inicial",
    ),
]
