"""
Configuração do app ``app_portfolio``.

Define o tipo de chave primária dos models e o nome com que o app aparece no
painel administrativo.
"""

from django.apps import AppConfig


class AppPortfolioConfig(AppConfig):
    """Registro do app no Django."""

    # BigAutoField (64 bits) fixado no app: os IDs não dependem do
    # DEFAULT_AUTO_FIELD do projeto, e o Django não emite o aviso W042.
    default_auto_field = "django.db.models.BigAutoField"

    name = "app_portfolio"

    # Sem isto, o painel exibiria o nome do módulo ("App_Portfolio").
    verbose_name = "Gestão do Portfólio"
