"""
Descoberta do site por buscadores e redes sociais (spec 007).

Reúne o que depende do endereço público (``URL_PUBLICA``) e do modo
demonstração: os metadados do ``<head>`` da home (título, description,
canonical, ``og:*`` e ``twitter:card``) e os arquivos ``robots.txt``,
``sitemap.xml`` e ``.well-known/security.txt``.

O endereço que vira canônico (canonical, ``og:url``, sitemap e o ``Canonical:``
do ``security.txt``) sai só da configuração, nunca do ``Host`` do pedido, que o
cliente escolhe. Os arquivos são montados aqui, em Python, sem template: têm
poucas linhas, e duas delas dependem da configuração (ADR-01).
"""

from xml.sax.saxutils import escape

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe

from .models import Perfil

# ---------------------------------------------------------------------------
# Textos e imagem da demo
# ---------------------------------------------------------------------------

# Com o modo demonstração, o resultado de busca e o cartão compartilhado dizem
# que o site é a demo do template, não o portfólio de uma pessoa (RF-03).
TITULO_DEMONSTRACAO = "Demonstração | Portfólio em Django de código aberto"
DESCRICAO_DEMONSTRACAO = (
    "Demonstração do portfolio-dinamico, um portfólio de desenvolvedor em Django "
    "com Admin, formulário de contato anti-spam e código aberto no GitHub. "
    "Os dados são fictícios."
)

# Imagem do cartão da demo, em static/ (RF-04, ADR-05). As dimensões vão no
# og:image:width/height, para a rede montar o cartão sem baixar a imagem antes.
IMAGEM_DEMONSTRACAO = "img/portfolio-django-divulgacao.jpg"
LARGURA_IMAGEM_DEMONSTRACAO = 1280
ALTURA_IMAGEM_DEMONSTRACAO = 640
ALT_IMAGEM_DEMONSTRACAO = (
    "Portfólio Dinâmico com Django: template educativo de segurança, consultas "
    "sem N+1 e testes com pytest, ao lado de um trecho do views.py"
)

# Sem o modo, os textos vêm do Perfil, com os mesmos padrões de antes da spec
# 007 (RF-09): o sufixo do título e a description para perfil sem bio curta.
SUFIXO_TITULO = "Desenvolvedor Full-Stack"
DESCRICAO_PADRAO = "Portfólio de Desenvolvedor Full-Stack focado em soluções robustas."

# ---------------------------------------------------------------------------
# security.txt
# ---------------------------------------------------------------------------

# Data em que o contato deixa de valer (RFC 9116, 2.5.5). Fixa de propósito: o
# leitor precisa saber se o canal ainda é cuidado, e uma data calculada na hora
# nunca venceria. O teste falha 30 dias antes; renove por até um ano (ADR-07).
EXPIRES_SECURITY_TXT = "2027-11-01T00:00:00Z"

# ---------------------------------------------------------------------------
# Metadados do <head>
# ---------------------------------------------------------------------------


def _endereco_absoluto(request: HttpRequest, caminho: str) -> str:
    """
    Transforma um caminho do site (``/static/...``, ``/media/...``) em endereço
    absoluto.

    As redes sociais exigem endereço absoluto no ``og:image`` (spec 004, RF-20).
    Com ``URL_PUBLICA``, ele parte dela; sem ela, do esquema e do ``Host`` do
    pedido, que o ``ALLOWED_HOSTS`` já restringe em produção.

    Args:
        request (HttpRequest): Pedido em atendimento.
        caminho (str): Caminho a partir da raiz do site, começando por ``/``.

    Returns:
        str: O endereço absoluto.
    """
    if settings.URL_PUBLICA:
        return f"{settings.URL_PUBLICA}{caminho}"
    return request.build_absolute_uri(caminho)


def montar_metadados(
    request: HttpRequest, perfil: Perfil | None
) -> dict[str, str | int]:
    """
    Decide os metadados do ``<head>`` da home (ADR-03).

    O ``base.html`` só renderiza o que esta função devolve. Com o modo
    demonstração, título, description e imagem são os da demo do template; sem
    ele, vêm do ``Perfil``, como antes da spec 007.

    Args:
        request (HttpRequest): Pedido da home.
        perfil (Perfil | None): Perfil exibido, ou ``None`` se não há nenhum.

    Returns:
        dict[str, str | int]: ``titulo``, ``descricao``, ``og_titulo``,
            ``og_descricao``, ``url_canonica`` (vazia sem ``URL_PUBLICA``),
            ``imagem`` (endereço absoluto ou vazia), ``imagem_largura`` e
            ``imagem_altura`` (0 quando desconhecidas), ``imagem_alt`` (vazia
            fora da demo) e ``twitter_card``.
    """
    if settings.MODO_DEMONSTRACAO:
        titulo = og_titulo = TITULO_DEMONSTRACAO
        descricao = og_descricao = DESCRICAO_DEMONSTRACAO
        caminho_imagem = static(IMAGEM_DEMONSTRACAO)
        largura, altura = LARGURA_IMAGEM_DEMONSTRACAO, ALTURA_IMAGEM_DEMONSTRACAO
        imagem_alt = ALT_IMAGEM_DEMONSTRACAO
    else:
        nome = perfil.nome if perfil else ""
        bio_curta = (perfil.bio_curta if perfil else None) or ""
        # Os padrões diferem entre o <title> e o og:title desde a spec 001;
        # mantê-los é o que garante a home de quem clona igual à de antes.
        titulo = f"{nome or 'Seu Nome'} | {SUFIXO_TITULO}"
        og_titulo = f"{nome or 'Portfólio'} | {SUFIXO_TITULO}"
        descricao = bio_curta or DESCRICAO_PADRAO
        og_descricao = bio_curta
        caminho_imagem = perfil.foto.url if perfil and perfil.foto else ""
        largura = altura = 0
        imagem_alt = ""

    imagem = _endereco_absoluto(request, caminho_imagem) if caminho_imagem else ""
    url_canonica = f"{settings.URL_PUBLICA}/" if settings.URL_PUBLICA else ""
    return {
        "titulo": titulo,
        "descricao": descricao,
        "og_titulo": og_titulo,
        "og_descricao": og_descricao,
        "url_canonica": url_canonica,
        "imagem": imagem,
        "imagem_largura": largura,
        "imagem_altura": altura,
        "imagem_alt": imagem_alt,
        "twitter_card": "summary_large_image" if imagem else "summary",
    }


# ---------------------------------------------------------------------------
# robots.txt, sitemap.xml e security.txt
# ---------------------------------------------------------------------------


def _texto(linhas: list[str]) -> HttpResponse:
    """
    Responde um arquivo de texto com uma linha por item e quebra no fim.

    Args:
        linhas (list[str]): Linhas do arquivo, sem a quebra de linha.

    Returns:
        HttpResponse: Resposta 200 em ``text/plain; charset=utf-8``.
    """
    return HttpResponse(
        "\n".join(linhas) + "\n", content_type="text/plain; charset=utf-8"
    )


@require_safe
@cache_control(public=True, max_age=86400)
def robots_txt(request: HttpRequest) -> HttpResponse:
    """
    Libera o site inteiro aos robôs e aponta o sitemap (RF-06).

    Não cita o caminho do Admin: um ``Disallow`` revelaria o ``ADMIN_URL``
    escondido (spec 003), e a tela de login do Admin já pede para não ser
    indexada. A política de robôs de IA fica com o proxy, quando há um.

    Args:
        request (HttpRequest): Pedido GET ou HEAD (os outros métodos recebem 405).

    Returns:
        HttpResponse: O ``robots.txt``, com a linha ``Sitemap:`` só quando há
            ``URL_PUBLICA``.
    """
    linhas = ["User-agent: *", "Allow: /"]
    if settings.URL_PUBLICA:
        linhas += ["", f"Sitemap: {settings.URL_PUBLICA}/sitemap.xml"]
    return _texto(linhas)


@require_safe
@cache_control(public=True, max_age=86400)
def sitemap_xml(request: HttpRequest) -> HttpResponse:
    """
    Lista a única página do site para os buscadores (RF-07).

    Montado à mão, sem o ``django.contrib.sitemaps``, que tiraria o domínio do
    ``Host`` do pedido (ADR-02).

    Args:
        request (HttpRequest): Pedido GET ou HEAD (os outros métodos recebem 405).

    Returns:
        HttpResponse: Sitemap com a home, em ``application/xml``.

    Raises:
        Http404: Se ``URL_PUBLICA`` está vazia: sem endereço configurado, não
            há sitemap.
    """
    if not settings.URL_PUBLICA:
        raise Http404("Sitemap sem URL_PUBLICA.")
    corpo = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{escape(settings.URL_PUBLICA + '/')}</loc></url>\n"
        "</urlset>\n"
    )
    return HttpResponse(corpo, content_type="application/xml")


@require_safe
@cache_control(public=True, max_age=86400)
def security_txt(request: HttpRequest) -> HttpResponse:
    """
    Publica o contato de segurança da demo do template (RF-08, RFC 9116).

    Só existe com o modo demonstração: o contato é o do repositório do template,
    que não responde pelo site de quem clona e publica o próprio portfólio.

    Args:
        request (HttpRequest): Pedido GET ou HEAD (os outros métodos recebem 405).

    Returns:
        HttpResponse: O ``security.txt``, com ``Canonical:`` só quando há
            ``URL_PUBLICA``.

    Raises:
        Http404: Se o modo demonstração está desligado.
    """
    if not settings.MODO_DEMONSTRACAO:
        raise Http404("security.txt só na demonstração.")
    linhas = [
        "# Contato de segurança da demonstração do portfolio-dinamico (RFC 9116).",
        "# Relate em privado, pelos avisos de segurança do GitHub; o escopo e os",
        "# prazos estão na política.",
        f"Contact: {settings.URL_REPOSITORIO}/security/advisories/new",
        f"Expires: {EXPIRES_SECURITY_TXT}",
        "Preferred-Languages: pt, en",
    ]
    if settings.URL_PUBLICA:
        linhas.append(f"Canonical: {settings.URL_PUBLICA}/.well-known/security.txt")
    linhas.append(f"Policy: {settings.URL_REPOSITORIO}/blob/main/SECURITY.md")
    return _texto(linhas)
