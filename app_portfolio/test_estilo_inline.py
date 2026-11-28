"""
Testes de que nenhum template aplica estilo inline — adendo da spec 003.

A CSP tem ``style-src 'self'``, sem ``'unsafe-inline'``: o navegador bloqueia em
silêncio um atributo ``style=`` ou um elemento ``<style>``, e o servidor não acusa
nada. Estes testes acusam antes. Cobrem também o honeypot do formulário de contato,
que deixou o ``style="display:none;"`` por uma classe do ``styles.css`` (RF-10).

Estratégia de isolamento: os templates e o ``styles.css`` são lidos como texto, sem
banco nem cliente HTTP. Só a renderização da home usa o banco de teste; a fixture
``ambiente_isolado`` desliga a ``URL_PUBLICA`` e o redirecionamento HTTPS (o ``.env``
de quem roda a suíte pode ligá-los) e põe o mailer ``default`` em memória.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.urls import reverse

from app_portfolio.models import Perfil

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

# Um atributo style dentro de uma tag aberta, e o elemento <style>.
_ATRIBUTO_STYLE = re.compile(r"<[a-zA-Z][^>]*\sstyle\s*=", re.IGNORECASE)
_ELEMENTO_STYLE = re.compile(r"<style\b", re.IGNORECASE)

# A regra do honeypot no styles.css, com display: none entre as declarações.
_REGRA_HONEYPOT = re.compile(r"\.contact__honeypot\s*\{[^}]*display:\s*none\s*;")

# A classe que esconde o honeypot: o template e o styles.css precisam usar a mesma.
_CLASSE_HONEYPOT = "contact__honeypot"


# ---------------------------------------------------------------------------
# Fixtures e auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ambiente_isolado(settings) -> None:
    """Parte de um site sem endereço público e sem redirecionamento HTTPS."""
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.URL_PUBLICA = ""
    settings.SECURE_SSL_REDIRECT = False


class _LeitorDeEstilo(HTMLParser):
    """
    Lê o HTML entregue e anota o estilo inline e as classes em volta do honeypot.

    Attributes:
        estilos_inline (list[str]): Tags com atributo ``style`` ou elemento
            ``<style>``, na ordem em que aparecem.
        classes_do_honeypot (list[str] | None): Classes dos elementos abertos em
            volta do campo ``honeypot``; ``None`` se o campo não apareceu.
    """

    # Elementos sem fechamento: não entram na pilha dos abertos.
    _VAZIOS = frozenset({"area", "br", "col", "hr", "img", "input", "link", "meta"})

    def __init__(self) -> None:
        """Começa sem nada anotado e com a pilha de elementos vazia."""
        super().__init__()
        self.estilos_inline: list[str] = []
        self.classes_do_honeypot: list[str] | None = None
        self._abertos: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """
        Anota o estilo inline e, no campo ``honeypot``, as classes em volta dele.

        Args:
            tag (str): Nome da tag, em minúsculas.
            attrs (list[tuple[str, str | None]]): Atributos da tag.
        """
        atributos = dict(attrs)
        if tag == "style" or "style" in atributos:
            self.estilos_inline.append(tag)
        if tag == "input" and atributos.get("name") == "honeypot":
            self.classes_do_honeypot = [c for classes in self._abertos for c in classes]
        if tag not in self._VAZIOS:
            self._abertos.append((atributos.get("class") or "").split())

    def handle_endtag(self, tag: str) -> None:
        """
        Fecha o elemento mais recente da pilha.

        Args:
            tag (str): Nome da tag, em minúsculas.
        """
        if tag not in self._VAZIOS and self._abertos:
            self._abertos.pop()


def _id(caminho: Path) -> str:
    """
    Nomeia o caso parametrizado pelo caminho do template.

    Args:
        caminho (Path): Template conferido.

    Returns:
        str: O caminho relativo à raiz do repositório.
    """
    return caminho.relative_to(_RAIZ).as_posix()


def _linhas_com(padrao: re.Pattern[str], texto: str) -> list[int]:
    """
    Lista as linhas em que o padrão começa.

    Args:
        padrao (re.Pattern[str]): Expressão procurada.
        texto (str): Conteúdo do arquivo.

    Returns:
        list[int]: Números das linhas, a partir de 1.
    """
    return [
        texto.count("\n", 0, achado.start()) + 1 for achado in padrao.finditer(texto)
    ]


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_ha_templates_para_conferir() -> None:
    """Sem templates achados, os testes abaixo passariam sem conferir nada."""
    assert _TEMPLATES


# Os padrões e o leitor são conferidos contra casos escritos aqui: um padrão que nunca
# casa também deixaria todo template passar.
@pytest.mark.parametrize(
    ("trecho", "linhas"),
    [
        ('<p style="color: red">', [1]),
        ('<DIV STYLE="x">', [1]),
        ('<p\n  class="a"\n  style = "x">', [1]),
        ('<p>\n<span style="x">', [2]),
        ('<p class="a" data-style="x">', []),
        ('style="x" fora de uma tag', []),
    ],
)
def test_padrao_do_atributo_style(trecho: str, linhas: list[int]) -> None:
    """Acusa o ``style=`` dentro de uma tag, na linha em que a tag abre."""
    assert _linhas_com(_ATRIBUTO_STYLE, trecho) == linhas


@pytest.mark.parametrize(
    ("trecho", "linhas"),
    [
        ("<style>", [1]),
        ('<p>\n<STYLE media="print">', [2]),
        ('<link rel="stylesheet" href="styles.css">', []),
        ("<stylesheet>", []),
    ],
)
def test_padrao_do_elemento_style(trecho: str, linhas: list[int]) -> None:
    """Acusa o elemento ``<style>``, não a folha ligada por ``<link>``."""
    assert _linhas_com(_ELEMENTO_STYLE, trecho) == linhas


def test_leitor_anota_o_estilo_inline_e_as_classes_do_honeypot() -> None:
    """O elemento vazio não entra na pilha, e o honeypot leva as classes em volta."""
    leitor = _LeitorDeEstilo()
    leitor.feed(
        "<style>p {}</style>"
        '<div class="a b"><img class="z" alt=""><br>'
        '<p style="x"><input name="honeypot"></p></div>'
    )

    assert leitor.estilos_inline == ["style", "p"]
    assert leitor.classes_do_honeypot == ["a", "b"]


def test_leitor_sem_honeypot_fica_em_none() -> None:
    """Sem o campo, o leitor não inventa classes."""
    leitor = _LeitorDeEstilo()
    leitor.feed('<form class="contact__honeypot"><input name="nome"></form>')

    assert leitor.estilos_inline == []
    assert leitor.classes_do_honeypot is None


@pytest.mark.parametrize("caminho", _TEMPLATES, ids=_id)
def test_template_sem_atributo_style(caminho: Path) -> None:
    """A CSP bloqueia o ``style=``: o estilo vai para o ``styles.css``."""
    linhas = _linhas_com(_ATRIBUTO_STYLE, caminho.read_text(encoding="utf-8"))
    assert not linhas, f"style= em {_id(caminho)}, linhas {linhas}"


@pytest.mark.parametrize("caminho", _TEMPLATES, ids=_id)
def test_template_sem_elemento_style(caminho: Path) -> None:
    """A CSP bloqueia o ``<style>``: o estilo vai para o ``styles.css``."""
    linhas = _linhas_com(_ELEMENTO_STYLE, caminho.read_text(encoding="utf-8"))
    assert not linhas, f"<style> em {_id(caminho)}, linhas {linhas}"


def test_styles_css_esconde_o_honeypot() -> None:
    """A classe do honeypot tira o campo da tela, do Tab e do leitor de tela."""
    css = (_RAIZ / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    assert _REGRA_HONEYPOT.search(css)


@pytest.mark.django_db
@pytest.mark.parametrize("com_perfil", [True, False], ids=["com-perfil", "sem-perfil"])
@pytest.mark.parametrize("modo_demonstracao", [False, True], ids=["normal", "demo"])
def test_home_entregue_sem_estilo_inline(
    client, settings, com_perfil: bool, modo_demonstracao: bool
) -> None:
    """O honeypot fica dentro da classe, e nenhum HTML da home leva estilo inline."""
    settings.MODO_DEMONSTRACAO = modo_demonstracao
    if com_perfil:
        Perfil.objects.create(nome="Ana Dev", cargo="Desenvolvedora")
    leitor = _LeitorDeEstilo()
    leitor.feed(client.get(reverse("home")).content.decode())

    assert leitor.estilos_inline == []
    assert leitor.classes_do_honeypot is not None
    assert _CLASSE_HONEYPOT in leitor.classes_do_honeypot
