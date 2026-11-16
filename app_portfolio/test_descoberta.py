"""
Testes da descoberta da demo pelos buscadores e pelas redes sociais — spec 007.

Cobre a leitura de ``URL_PUBLICA`` no ``settings.py``, as imagens do cartão e da
tela inicial, os metadados do ``<head>`` (pela função ``montar_metadados`` e pelo
HTML da home) e os arquivos ``robots.txt``, ``sitemap.xml`` e ``security.txt``,
inclusive o prazo do ``Expires``.

Estratégia de isolamento: nenhuma chamada de rede. O ``settings.py`` é lido numa
cópia avulsa (``_carregar_settings`` de ``tests.py``), sem tocar a configuração
em uso. Nos outros testes, a fixture ``settings`` do pytest-django zera
``URL_PUBLICA`` e ``MODO_DEMONSTRACAO`` (o ``.env`` de quem roda a suíte pode
ligá-los), e cada teste liga o que precisa. O mailer ``default`` vai para o
backend em memória, como no resto da suíte.
"""

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

import pytest
from django.contrib.staticfiles import finders
from django.http import HttpRequest
from django.test import RequestFactory
from PIL import Image

from app_portfolio.descoberta import (
    ALT_IMAGEM_DEMONSTRACAO,
    ALTURA_IMAGEM_DEMONSTRACAO,
    DESCRICAO_DEMONSTRACAO,
    EXPIRES_SECURITY_TXT,
    IMAGEM_DEMONSTRACAO,
    LARGURA_IMAGEM_DEMONSTRACAO,
    TITULO_DEMONSTRACAO,
    montar_metadados,
)
from app_portfolio.models import Perfil
from app_portfolio.tests import _carregar_settings

# Endereço público dos testes que ligam URL_PUBLICA
URL = "https://exemplo.com.br"

# O Expires do security.txt vence (RFC 9116, 2.5.5): a suíte fica vermelha um
# mês antes, com tempo de renovar sem o arquivo valer como vencido (ADR-07).
AVISO_EXPIRES_DIAS = 30
# A RFC recomenda menos de um ano; a folga de um dia cobre a renovação no dia.
MAXIMO_EXPIRES_DIAS = 366

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

# ---------------------------------------------------------------------------
# Fixtures e auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ambiente_isolado(settings) -> None:
    """Parte de um site sem endereço público e sem modo demonstração."""
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.URL_PUBLICA = ""
    settings.MODO_DEMONSTRACAO = False
    settings.SECURE_SSL_REDIRECT = False


def _pedido(host: str = "testserver") -> HttpRequest:
    """
    Monta um GET da home com o ``Host`` pedido.

    Args:
        host (str): Valor do cabeçalho ``Host`` (precisa caber no
            ``ALLOWED_HOSTS`` do teste).

    Returns:
        HttpRequest: Pedido pronto para a ``montar_metadados``.
    """
    return RequestFactory().get("/", HTTP_HOST=host)


def _perfil_em_memoria(**campos: Any) -> Perfil:
    """
    Cria um ``Perfil`` sem gravar no banco (a ``montar_metadados`` só lê campos).

    Args:
        **campos (Any): Campos que substituem os padrões; Any porque cada
            campo do model tem um tipo.

    Returns:
        Perfil: Instância não salva.
    """
    return Perfil(**{"nome": "Ana Dev", "cargo": "Dev", **campos})


def _head(client, caminho: str = "/") -> str:
    """
    Baixa a página e devolve só o ``<head>``.

    Args:
        client (django.test.Client): Cliente de teste do Django.
        caminho (str): Caminho pedido, com query string se houver.

    Returns:
        str: O trecho entre ``<head>`` e ``</head>``.
    """
    html = str(client.get(caminho).content.decode("utf-8"))
    return html[html.index("<head>") : html.index("</head>")]


def _meta(head: str, atributo: str, nome: str) -> str | None:
    """
    Lê o ``content`` de uma ``<meta>`` do ``<head>``.

    Args:
        head (str): Trecho do ``<head>``.
        atributo (str): ``property`` (Open Graph) ou ``name``.
        nome (str): Valor do atributo, como ``og:url``.

    Returns:
        str | None: O ``content``, ou ``None`` se a tag não existe.
    """
    padrao = rf'<meta {atributo}="{re.escape(nome)}" content="([^"]*)"'
    achado = re.search(padrao, head)
    return achado.group(1) if achado else None


# ---------------------------------------------------------------------------
# RF-01 — URL_PUBLICA no settings.py
# ---------------------------------------------------------------------------


class TestUrlPublica:
    @pytest.mark.parametrize(
        "valor",
        [
            "https://exemplo.com.br",
            "https://exemplo.com.br/",
            " https://exemplo.com.br ",
        ],
    )
    def test_sai_sem_a_barra_final(self, monkeypatch, valor: str) -> None:
        """Com ou sem barra (e espaço em volta), o endereço sai sem a barra."""
        modulo = _carregar_settings(monkeypatch, URL_PUBLICA=valor)
        assert modulo.URL_PUBLICA == "https://exemplo.com.br"

    def test_aceita_http_e_porta(self, monkeypatch) -> None:
        """http:// e porta explícita são válidos (deploy sem TLS, teste local)."""
        modulo = _carregar_settings(monkeypatch, URL_PUBLICA="http://localhost:8000")
        assert modulo.URL_PUBLICA == "http://localhost:8000"

    def test_vazia_ou_ausente_sobe_normalmente(self, monkeypatch) -> None:
        """Sem a variável, o site sobe com o endereço público vazio."""
        assert _carregar_settings(monkeypatch).URL_PUBLICA == ""
        assert _carregar_settings(monkeypatch, URL_PUBLICA="").URL_PUBLICA == ""

    @pytest.mark.parametrize(
        "valor",
        [
            "exemplo.com.br",
            "ftp://exemplo.com.br",
            "https://exemplo.com.br/portfolio",
            "https://exemplo.com.br/?a=1",
            "https://exemplo.com.br/#topo",
            "https://",
        ],
    )
    def test_valor_invalido_derruba_a_subida(self, monkeypatch, valor: str) -> None:
        """Sem esquema, outro esquema, caminho, query ou fragmento: ValueError."""
        with pytest.raises(ValueError, match="URL_PUBLICA"):
            _carregar_settings(monkeypatch, URL_PUBLICA=valor)


# ---------------------------------------------------------------------------
# RF-04 e RF-05 — Imagem do cartão e ícone de tela inicial
# ---------------------------------------------------------------------------


class TestImagens:
    def test_imagem_de_divulgacao_tem_1280_por_640(self) -> None:
        """A proporção 2:1 é a que o summary_large_image mostra sem corte."""
        caminho = finders.find(IMAGEM_DEMONSTRACAO)
        assert caminho, IMAGEM_DEMONSTRACAO
        with Image.open(caminho) as imagem:
            assert imagem.size == (
                LARGURA_IMAGEM_DEMONSTRACAO,
                ALTURA_IMAGEM_DEMONSTRACAO,
            )
            assert imagem.size == (1280, 640)

    def test_icone_de_tela_inicial_tem_180_e_e_opaco(self) -> None:
        """Sem canal alfa: o iOS pintaria de preto o fundo transparente."""
        caminho = finders.find("icons/apple-touch-icon.png")
        assert caminho
        with Image.open(caminho) as imagem:
            assert imagem.size == (180, 180)
            assert imagem.mode == "RGB"


# ---------------------------------------------------------------------------
# RF-02 a RF-04 e RF-09 — montar_metadados
# ---------------------------------------------------------------------------


class TestMontarMetadados:
    def test_demo_usa_textos_e_imagem_da_demo(self, settings) -> None:
        """O Perfil cadastrado não aparece nos metadados da demo."""
        settings.MODO_DEMONSTRACAO = True
        settings.URL_PUBLICA = URL
        perfil = _perfil_em_memoria(bio_curta="Bio", foto="perfil/ana.webp")
        dados = montar_metadados(_pedido(), perfil)
        assert dados["titulo"] == dados["og_titulo"] == TITULO_DEMONSTRACAO
        assert dados["descricao"] == dados["og_descricao"] == DESCRICAO_DEMONSTRACAO
        assert dados["imagem"] == f"{URL}/static/{IMAGEM_DEMONSTRACAO}"
        assert (dados["imagem_largura"], dados["imagem_altura"]) == (1280, 640)
        assert dados["imagem_alt"] == ALT_IMAGEM_DEMONSTRACAO
        assert dados["twitter_card"] == "summary_large_image"
        assert dados["url_canonica"] == f"{URL}/"

    def test_sem_modo_os_textos_vem_do_perfil(self) -> None:
        """Título e description de antes da spec 007 (RF-09)."""
        perfil = _perfil_em_memoria(bio_curta="Bio curta")
        dados = montar_metadados(_pedido(), perfil)
        assert dados["titulo"] == "Ana Dev | Desenvolvedor Full-Stack"
        assert dados["og_titulo"] == "Ana Dev | Desenvolvedor Full-Stack"
        assert dados["descricao"] == dados["og_descricao"] == "Bio curta"

    def test_sem_perfil_mantem_os_padroes_de_antes(self) -> None:
        """Os padrões do <title> e do og:title continuam diferentes, como antes."""
        dados = montar_metadados(_pedido(), None)
        assert dados["titulo"] == "Seu Nome | Desenvolvedor Full-Stack"
        assert dados["og_titulo"] == "Portfólio | Desenvolvedor Full-Stack"
        assert str(dados["descricao"]).startswith("Portfólio de Desenvolvedor")
        assert dados["og_descricao"] == ""
        assert dados["imagem"] == "" and dados["twitter_card"] == "summary"

    def test_perfil_com_foto_tem_cartao_grande(self, settings) -> None:
        """A foto do perfil vira og:image absoluta a partir de URL_PUBLICA."""
        settings.URL_PUBLICA = URL
        perfil = _perfil_em_memoria(foto="perfil/ana.webp")
        dados = montar_metadados(_pedido(), perfil)
        assert dados["imagem"] == f"{URL}/media/perfil/ana.webp"
        assert dados["imagem_largura"] == 0 and dados["imagem_alt"] == ""
        assert dados["twitter_card"] == "summary_large_image"

    def test_perfil_sem_foto_tem_cartao_pequeno(self) -> None:
        """Sem imagem, summary: o cartão grande sairia vazio."""
        dados = montar_metadados(_pedido(), _perfil_em_memoria())
        assert dados["imagem"] == "" and dados["twitter_card"] == "summary"

    def test_sem_url_publica_host_vai_so_para_a_imagem(self, settings) -> None:
        """O Host nunca vira canonical (RNF-03); a imagem segue a spec 004, RF-20."""
        settings.ALLOWED_HOSTS = ["forjado.example"]
        perfil = _perfil_em_memoria(foto="perfil/ana.webp")
        dados = montar_metadados(_pedido("forjado.example"), perfil)
        assert dados["url_canonica"] == ""
        assert dados["imagem"] == "http://forjado.example/media/perfil/ana.webp"

    def test_com_url_publica_host_forjado_nao_aparece(self, settings) -> None:
        """Com URL_PUBLICA, nenhum endereço sai do Host."""
        settings.URL_PUBLICA = URL
        settings.ALLOWED_HOSTS = ["forjado.example"]
        perfil = _perfil_em_memoria(foto="perfil/ana.webp")
        dados = montar_metadados(_pedido("forjado.example"), perfil)
        assert "forjado" not in str(dados)


# ---------------------------------------------------------------------------
# RF-02 a RF-05 — <head> da home
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHeadDaHome:
    def test_canonical_e_og_url_sem_query_string(self, client, settings) -> None:
        """A home com ?utm_source=... aponta para o endereço limpo."""
        settings.URL_PUBLICA = URL
        head = _head(client, "/?utm_source=teste")
        assert f'<link rel="canonical" href="{URL}/">' in head
        assert _meta(head, "property", "og:url") == f"{URL}/"

    def test_sem_url_publica_nao_ha_canonical(self, client) -> None:
        """Sem endereço configurado, nada de canonical nem og:url."""
        head = _head(client)
        assert 'rel="canonical"' not in head
        assert _meta(head, "property", "og:url") is None

    def test_demo_no_head(self, client, settings) -> None:
        """Título, description, og:* e cartão da demo, com o Perfil cadastrado."""
        settings.MODO_DEMONSTRACAO = True
        settings.URL_PUBLICA = URL
        Perfil.objects.create(nome="Seu Nome", cargo="Dev", bio_curta="Bio fictícia")
        head = _head(client)
        assert f"<title>{TITULO_DEMONSTRACAO}</title>" in head
        assert _meta(head, "name", "description") == DESCRICAO_DEMONSTRACAO
        assert _meta(head, "property", "og:title") == TITULO_DEMONSTRACAO
        assert _meta(head, "property", "og:image:width") == "1280"
        assert _meta(head, "property", "og:image:height") == "640"
        assert _meta(head, "property", "og:image:alt") == ALT_IMAGEM_DEMONSTRACAO
        assert _meta(head, "name", "twitter:card") == "summary_large_image"
        assert "Seu Nome" not in head and "Bio fictícia" not in head

    def test_sem_modo_head_vem_do_perfil(self, client) -> None:
        """Fora da demo, o <title> é o de antes e o cartão é pequeno sem foto."""
        Perfil.objects.create(nome="Ana Dev", cargo="Dev")
        head = _head(client)
        assert "<title>Ana Dev | Desenvolvedor Full-Stack</title>" in head
        assert _meta(head, "name", "twitter:card") == "summary"
        assert _meta(head, "property", "og:image:width") is None

    def test_icone_de_tela_inicial_declarado(self, client) -> None:
        """O apple-touch-icon aponta para o PNG de 180 px."""
        head = _head(client)
        assert re.search(
            r'rel="apple-touch-icon" href="[^"]*apple-touch-icon\.png"', head
        )

    def test_pagina_404_sem_canonical(self, client, settings) -> None:
        """As páginas de erro não herdam o base.html e ficam sem canonical."""
        settings.URL_PUBLICA = URL
        settings.DEBUG = False
        resposta = client.get("/nao-existe/")
        assert resposta.status_code == 404
        assert 'rel="canonical"' not in resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# RF-06 — robots.txt
# ---------------------------------------------------------------------------


class TestRobotsTxt:
    def test_libera_tudo_sem_sitemap_sem_url_publica(self, client) -> None:
        """Sem endereço configurado, não há linha Sitemap:."""
        resposta = client.get("/robots.txt")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "text/plain; charset=utf-8"
        assert resposta.content.decode() == "User-agent: *\nAllow: /\n"

    def test_aponta_o_sitemap_com_url_publica(self, client, settings) -> None:
        """A linha Sitemap: leva o endereço absoluto, da configuração."""
        settings.URL_PUBLICA = URL
        texto = client.get("/robots.txt").content.decode()
        assert texto.splitlines()[-1] == f"Sitemap: {URL}/sitemap.xml"

    def test_nao_revela_o_caminho_do_admin(self, client, settings) -> None:
        """Um Disallow com o ADMIN_URL entregaria o caminho escondido."""
        settings.URL_PUBLICA = URL
        settings.ADMIN_URL_PATH = "painel-secreto-123/"
        texto = client.get("/robots.txt").content.decode()
        assert "painel-secreto" not in texto and "Disallow" not in texto

    def test_so_get_e_head(self, client) -> None:
        """POST recebe 405, como na servir_midia."""
        assert client.post("/robots.txt").status_code == 405


# ---------------------------------------------------------------------------
# RF-07 — sitemap.xml
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSitemapXml:
    def test_404_sem_url_publica(self, client) -> None:
        """Sem endereço configurado, o sitemap não é montado a partir do Host."""
        assert client.get("/sitemap.xml").status_code == 404

    def test_uma_loc_igual_ao_canonical(self, client, settings) -> None:
        """Sitemap válido com a home, no mesmo endereço do canonical."""
        settings.URL_PUBLICA = URL
        resposta = client.get("/sitemap.xml")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "application/xml"
        raiz = ET.fromstring(resposta.content)
        assert raiz.tag == f"{SITEMAP_NS}urlset"
        locs = [loc.text for loc in raiz.iter(f"{SITEMAP_NS}loc")]
        assert locs == [f"{URL}/"]
        assert f'<link rel="canonical" href="{locs[0]}">' in _head(client)

    def test_host_forjado_nao_entra(self, client, settings) -> None:
        """O endereço sai de URL_PUBLICA mesmo com outro Host no pedido."""
        settings.URL_PUBLICA = URL
        settings.ALLOWED_HOSTS = ["forjado.example"]
        resposta = client.get("/sitemap.xml", HTTP_HOST="forjado.example")
        assert b"forjado" not in resposta.content


# ---------------------------------------------------------------------------
# RF-08 — security.txt
# ---------------------------------------------------------------------------


def _campos(texto: str) -> dict[str, list[str]]:
    """
    Lê os campos de um ``security.txt``, sem os comentários.

    Args:
        texto (str): Conteúdo do arquivo.

    Returns:
        dict[str, list[str]]: Os valores de cada campo, na ordem do arquivo.
    """
    campos: dict[str, list[str]] = {}
    for linha in texto.splitlines():
        achado = re.fullmatch(r"([A-Za-z-]+): (.+)", linha)
        if achado:
            campos.setdefault(achado.group(1), []).append(achado.group(2))
    return campos


class TestSecurityTxt:
    def test_404_sem_modo_demonstracao(self, client, settings) -> None:
        """Quem publica o próprio portfólio não herda o contato do template."""
        settings.URL_PUBLICA = URL
        assert client.get("/.well-known/security.txt").status_code == 404

    def test_campos_na_demo(self, client, settings) -> None:
        """Contact https, um Expires só, Preferred-Languages, Canonical e Policy."""
        settings.MODO_DEMONSTRACAO = True
        settings.URL_PUBLICA = URL
        resposta = client.get("/.well-known/security.txt")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "text/plain; charset=utf-8"
        campos = _campos(resposta.content.decode())
        repositorio = settings.URL_REPOSITORIO
        assert campos["Contact"] == [f"{repositorio}/security/advisories/new"]
        assert all(c.startswith("https://") for c in campos["Contact"])
        assert campos["Expires"] == [EXPIRES_SECURITY_TXT]
        assert campos["Preferred-Languages"] == ["pt, en"]
        assert campos["Canonical"] == [f"{URL}/.well-known/security.txt"]
        assert campos["Policy"] == [f"{repositorio}/blob/main/SECURITY.md"]

    def test_sem_url_publica_nao_ha_canonical(self, client, settings) -> None:
        """O Canonical: só sai da configuração."""
        settings.MODO_DEMONSTRACAO = True
        campos = _campos(client.get("/.well-known/security.txt").content.decode())
        assert "Canonical" not in campos and "Contact" in campos

    def test_expires_nem_perto_de_vencer_nem_longe_demais(self) -> None:
        """Vermelho 30 dias antes do vencimento: hora de renovar a data (ADR-07)."""
        vence = datetime.fromisoformat(EXPIRES_SECURITY_TXT)
        dias = (vence - datetime.now(UTC)).days
        assert dias >= AVISO_EXPIRES_DIAS, (
            f"O Expires do security.txt vence em {dias} dias: renove "
            "EXPIRES_SECURITY_TXT em app_portfolio/descoberta.py."
        )
        assert dias <= MAXIMO_EXPIRES_DIAS
