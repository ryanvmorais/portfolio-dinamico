"""
Testes de que os comentários dos templates não chegam ao HTML entregue.

Nota interna e marcador de seção são comentários do Django: ``{# #}`` numa linha e
``{% comment %}…{% endcomment %}`` em várias. O ``<!-- -->`` iria para o navegador de
cada visitante, e o Django executa as tags escritas dentro dele. Um ``{# #}`` quebrado em
linhas o Django mostra como texto na página.

Estratégia de isolamento: só o texto dos templates é lido, sem banco nem cliente HTTP.
"""

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# A raiz do repositório, um nível acima da pasta do app.
_RAIZ = Path(__file__).resolve().parents[1]

# Pastas de templates do projeto e dos apps (as do .venv ficam de fora).
_TEMPLATES = sorted(
    caminho
    for pasta in [_RAIZ / "templates", *_RAIZ.glob("*/templates")]
    for caminho in pasta.rglob("*.html")
)

# "{#" seguido de uma quebra de linha antes do "#}": comentário quebrado.
_COMENTARIO_QUEBRADO = re.compile(r"\{#(?:(?!#\})[^\n])*\n")


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _id(caminho: Path) -> str:
    """
    Nomeia o caso parametrizado pelo caminho do template.

    Args:
        caminho (Path): Template conferido.

    Returns:
        str: O caminho relativo à raiz do repositório.
    """
    return caminho.relative_to(_RAIZ).as_posix()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_ha_templates_para_conferir() -> None:
    """Sem templates achados, os testes abaixo passariam sem conferir nada."""
    assert _TEMPLATES


@pytest.mark.parametrize("caminho", _TEMPLATES, ids=_id)
def test_template_nao_usa_comentario_html(caminho: Path) -> None:
    """Comentário para quem mantém o código fica fora do HTML entregue."""
    assert "<!--" not in caminho.read_text(encoding="utf-8")


@pytest.mark.parametrize("caminho", _TEMPLATES, ids=_id)
def test_comentario_de_uma_linha_nao_quebra(caminho: Path) -> None:
    """Bloco de várias linhas vai em ``{% comment %}``, nunca em ``{# #}``."""
    assert not _COMENTARIO_QUEBRADO.search(caminho.read_text(encoding="utf-8"))
