"""
Rotas do app do portfólio.

O site é uma página única: a raiz aponta para a view ``home``. O ``name``
deixa os templates usarem ``{% url "home" %}`` em vez do caminho fixo, então
mudar a rota não quebra nenhum link.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
]
