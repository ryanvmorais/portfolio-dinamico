"""
Fixtures compartilhadas por toda a suíte de testes.

Estratégia de isolamento: a suíte não depende de um ``collectstatic`` feito antes. O
WhiteNoise procura o ``STATIC_ROOT`` cada vez que o cliente de teste monta os
middlewares e avisa quando a pasta não existe; com ``filterwarnings = ["error"]`` o
aviso derrubaria todo teste que faz um pedido. A pasta vazia de uma sessão o atende sem
tocar a ``staticfiles/`` do repositório.
"""

from pathlib import Path

import pytest
from django.conf import settings


@pytest.fixture(autouse=True, scope="session")
def static_root_vazio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Aponta o ``STATIC_ROOT`` para uma pasta vazia que existe.

    Args:
        tmp_path_factory (pytest.TempPathFactory): Fábrica de pastas temporárias da
            sessão.

    Returns:
        Path: A pasta usada como ``STATIC_ROOT``.
    """
    pasta = tmp_path_factory.mktemp("staticfiles")
    settings.STATIC_ROOT = str(pasta)
    return pasta
