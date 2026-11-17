"""
Marca do site gerada do nome cadastrado: iniciais, favicon e ícone de tela inicial.

Quem clona o template ganha a própria marca sem editar imagem (spec 008,
ADR-09): as iniciais saem do ``Perfil.nome``, o favicon é um SVG com elas e o
ícone de tela inicial é um PNG desenhado pelo Pillow com a Inter do projeto.
Sem perfil, as duas rotas redirecionam para os arquivos de ``static/icons/``.
"""

from functools import lru_cache
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_safe
from PIL import Image, ImageDraw, ImageFont

from .models import Perfil

# O padrão do template quando o perfil não tem nome (o mesmo do base.html).
NOME_PADRAO = "Seu Nome"

# Cores do tema escuro do site (tokens --color-bg-primary e --color-accent do CSS).
COR_FUNDO = "#0a1628"
COR_MARCA = "#00d4ff"

# O iOS pede 180 x 180 e arredonda os cantos sozinho (spec 007, ADR-06).
LADO_ICONE = 180
FONTE_ICONE = settings.BASE_DIR / "static" / "fonts" / "inter-latin-variavel.woff2"

# Um dia de cache: o ?v= do base.html muda com as iniciais e fura esse cache.
SEGUNDOS_DE_CACHE = 86400

# ---------------------------------------------------------------------------
# Iniciais e desenho
# ---------------------------------------------------------------------------


def calcular_iniciais(nome: str | None) -> str:
    """
    Calcula as iniciais da marca a partir do nome (RF-16).

    Junta a primeira letra da primeira e da última palavra que começam por
    letra, em maiúsculas (``str.upper`` mantém o acento). Nome de uma palavra
    dá uma letra; nome vazio ou sem letra usa o padrão do template.

    Args:
        nome (str | None): O ``Perfil.nome``, ou ``None`` sem perfil.

    Returns:
        str: Uma ou duas letras maiúsculas (``"Érica de Souza"`` vira ``"ÉS"``).
    """
    palavras = [palavra for palavra in (nome or "").split() if palavra[0].isalpha()]
    if not palavras:
        palavras = NOME_PADRAO.split()
    if len(palavras) == 1:
        return palavras[0][0].upper()
    return (palavras[0][0] + palavras[-1][0]).upper()


def montar_favicon_svg(iniciais: str) -> str:
    """
    Monta o SVG do favicon: as iniciais em ciano num quadrado de 32 x 32.

    As iniciais passam pelo ``escape`` antes de entrar no texto, embora só
    tenham letras (defesa em profundidade). O SVG não carrega fonte externa: o
    navegador desenha as letras na fonte sem serifa do sistema (ADR-09).

    Args:
        iniciais (str): O resultado de ``calcular_iniciais``.

    Returns:
        str: O documento SVG, com menos de 2 KiB.
    """
    # Duas letras pedem corpo menor para caber no quadrado de 32 px.
    tamanho = 15 if len(iniciais) > 1 else 19
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        f'<rect x="1" y="1" width="30" height="30" rx="7" fill="{COR_FUNDO}" '
        f'stroke="{COR_MARCA}" stroke-width="2"/>'
        f'<text x="16" y="16.5" fill="{COR_MARCA}" font-family="system-ui, '
        "'Segoe UI', Roboto, Helvetica, Arial, sans-serif\" "
        f'font-size="{tamanho}" font-weight="800" text-anchor="middle" '
        f'dominant-baseline="central">{escape(iniciais)}</text>'
        "</svg>"
    )


@lru_cache(maxsize=8)
def gerar_icone_png(iniciais: str) -> bytes:
    """
    Desenha o ícone de tela inicial: PNG opaco de 180 x 180 com o monograma.

    Memoizado: o desenho só roda de novo quando as iniciais mudam.

    Args:
        iniciais (str): O resultado de ``calcular_iniciais``.

    Returns:
        bytes: O PNG em modo ``RGB`` (sem transparência, que o iOS pinta de preto).
    """
    imagem = Image.new("RGB", (LADO_ICONE, LADO_ICONE), COR_FUNDO)
    desenho = ImageDraw.Draw(imagem)

    # Moldura ciana recuada, como a borda do monograma do logo.
    margem = 18
    desenho.rounded_rectangle(
        (margem, margem, LADO_ICONE - margem, LADO_ICONE - margem),
        radius=28,
        outline=COR_MARCA,
        width=6,
    )

    fonte = ImageFont.truetype(str(FONTE_ICONE), 64 if len(iniciais) > 1 else 80)
    fonte.set_variation_by_name("ExtraBold")
    # anchor="mm" centra pelo meio da caixa do texto, nos dois eixos.
    centro = LADO_ICONE / 2
    desenho.text((centro, centro), iniciais, fill=COR_MARCA, font=fonte, anchor="mm")

    saida = BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _resposta_com_cache(conteudo: str | bytes, tipo: str) -> HttpResponse:
    """
    Responde o ícone gerado com o cabeçalho de cache público (RNF-04).

    Args:
        conteudo (str | bytes): O SVG ou o PNG.
        tipo (str): O ``Content-Type`` da resposta.

    Returns:
        HttpResponse: Status 200 com ``Cache-Control: public, max-age=86400``.
    """
    resposta = HttpResponse(conteudo, content_type=tipo)
    patch_cache_control(resposta, public=True, max_age=SEGUNDOS_DE_CACHE)
    return resposta


@require_safe
def favicon_svg(request: HttpRequest) -> HttpResponse:
    """
    Serve o favicon SVG com as iniciais do perfil (RF-17).

    Sem perfil, redireciona (302, sem cache) para o ``favicon.webp``: o perfil
    cadastrado depois passa a valer no pedido seguinte.

    Args:
        request (HttpRequest): Pedido GET ou HEAD.

    Returns:
        HttpResponse: O SVG (200) ou o redirecionamento para a reserva.
    """
    perfil = Perfil.objects.first()
    if perfil is None:
        return HttpResponseRedirect(staticfiles_storage.url("icons/favicon.webp"))
    svg = montar_favicon_svg(calcular_iniciais(perfil.nome))
    return _resposta_com_cache(svg, "image/svg+xml")


@require_safe
def icone_tela_inicial(request: HttpRequest) -> HttpResponse:
    """
    Serve o ícone de tela inicial PNG com o monograma do perfil (RF-18).

    Sem perfil, redireciona (302, sem cache) para o ``apple-touch-icon.png``.

    Args:
        request (HttpRequest): Pedido GET ou HEAD.

    Returns:
        HttpResponse: O PNG (200) ou o redirecionamento para a reserva.
    """
    perfil = Perfil.objects.first()
    if perfil is None:
        return HttpResponseRedirect(
            staticfiles_storage.url("icons/apple-touch-icon.png")
        )
    png = gerar_icone_png(calcular_iniciais(perfil.nome))
    return _resposta_com_cache(png, "image/png")
