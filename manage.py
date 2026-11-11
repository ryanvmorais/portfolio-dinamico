#!/usr/bin/env python
"""
Utilitário de linha de comando do Django (``runserver``, ``migrate``...).

Aponta para ``portfolio.settings`` e repassa os argumentos ao Django.
"""

import os
import sys


def main() -> None:
    """Executa as tarefas administrativas do Django."""
    # setdefault: uma DJANGO_SETTINGS_MODULE já definida no ambiente prevalece.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # A causa mais comum é rodar fora do ambiente virtual do projeto.
        raise ImportError(
            "Não foi possível importar o Django. Verifique se ele está instalado "
            "e se o seu ambiente virtual (venv) está ativo."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
