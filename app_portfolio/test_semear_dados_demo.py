"""
Testes do comando ``semear_dados_demo`` e da configuração do Lighthouse CI.

Cobre:
- o comando recusa rodar com ``DEBUG=False`` e é idempotente;
- as habilidades saem com nível e tecnologia ligada, e os projetos com a versão no
  ar e o estudo de caso, sem estatísticas (spec 008, RF-21);
- a proporção do adendo da spec 008 (RF-30, RF-31): seis projetos, dois por
  categoria, com cinco tecnologias e tudo o que o card mostra; três categorias de
  habilidade com 3, 2 e 1 habilidades por nível e a contagem descendo de nível para
  nível;
- toda URL da configuração do Lighthouse (``.github/lighthouse/``) responde 200 com os
  dados semeados, e o mobile e o desktop auditam as mesmas páginas com as mesmas
  checagens;
- a Home não carrega imagem, script ou CSS de fora: o CI roda sem rede externa.

Estratégia de isolamento: nada é mockado. O comando grava imagens de verdade e leva
mais de um segundo, então roda uma vez por classe (``banco_semeado``), fora da transação
de cada teste, com a mídia numa pasta temporária; os testes da classe só leem o banco, e
o fim da classe apaga o que o comando criou. O ``DEBUG=True`` é ligado por
``override_settings`` na semeadura e pela fixture ``settings`` nos testes, porque o
runner de testes força ``DEBUG=False``.
"""

import json
import re
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from django.apps import apps
from django.conf import LazySettings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, override_settings

from app_portfolio.models import (
    CategoriaHabilidade,
    CategoriaProjeto,
    Habilidade,
    NivelHabilidade,
    Perfil,
    Projeto,
    Tecnologia,
)

pytestmark = pytest.mark.django_db

# Pasta da configuração do Lighthouse CI: fica na raiz do repositório, fora do app.
_LIGHTHOUSE = Path(__file__).resolve().parents[1] / ".github" / "lighthouse"

# Auditorias que têm asserção própria: a nota geral de acessibilidade (limite de 0,95)
# passaria mesmo com cada uma delas reprovada.
_ASSERCOES_PROPRIAS = (
    "color-contrast",
    "unsized-images",
    "target-size",
    "errors-in-console",
)

# Tudo o que o comando cria, na ordem em que pode ser apagado.
_MODELOS_SEMEADOS = (
    Habilidade,
    CategoriaHabilidade,
    Projeto,
    CategoriaProjeto,
    Tecnologia,
    Perfil,
)

# Elementos que baixam o recurso de ``src``/``srcset``/``poster`` sozinhos.
_TAGS_COM_SRC = frozenset({"img", "script", "source", "iframe", "video", "audio"})

# Valores de ``rel`` de um ``<link>`` que não baixam nada.
_REL_SEM_DOWNLOAD = frozenset({"canonical", "alternate", "author", "me", "license"})


# ---------------------------------------------------------------------------
# Fixtures e auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pasta_de_midia(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Pasta temporária da mídia que o comando grava, uma por módulo.

    Args:
        tmp_path_factory (pytest.TempPathFactory): Fábrica de pastas da sessão.

    Returns:
        Path: A pasta usada como ``MEDIA_ROOT``.
    """
    return tmp_path_factory.mktemp("midia_demo")


@pytest.fixture
def _demo(settings: LazySettings, pasta_de_midia: Path) -> None:
    """
    Liga o ``DEBUG``, desliga o redirect para HTTPS e isola a mídia.

    Args:
        settings (LazySettings): Fixture do pytest-django.
        pasta_de_midia (Path): A pasta de mídia do módulo.
    """
    settings.DEBUG = True
    settings.SECURE_SSL_REDIRECT = False
    settings.MEDIA_ROOT = str(pasta_de_midia)


@pytest.fixture(scope="class")
def banco_semeado(
    django_db_setup: None,
    django_db_blocker: Any,
    pasta_de_midia: Path,
) -> Iterator[None]:
    """
    Roda o comando uma vez para a classe e apaga o que ele criou no fim.

    Os dados ficam fora da transação de cada teste, então valem para todos os testes
    da classe; o que um teste grava em cima deles é desfeito pela transação dele.

    Args:
        django_db_setup (None): Banco de teste já criado (pytest-django).
        django_db_blocker (Any): Libera o acesso ao banco fora de um teste.
        pasta_de_midia (Path): A pasta de mídia do módulo.

    Yields:
        None: Os testes da classe rodam com o banco semeado.
    """
    with (
        django_db_blocker.unblock(),
        override_settings(DEBUG=True, MEDIA_ROOT=str(pasta_de_midia)),
    ):
        call_command("semear_dados_demo")
    yield
    with django_db_blocker.unblock():
        for modelo in _MODELOS_SEMEADOS:
            modelo.objects.all().delete()


def _configuracao(perfil: str) -> dict[str, Any]:
    """
    Lê a configuração do Lighthouse CI de um perfil.

    Args:
        perfil (str): ``"mobile"`` ou ``"desktop"``.

    Returns:
        dict[str, Any]: O bloco ``ci`` do JSON.
    """
    arquivo = _LIGHTHOUSE / f"{perfil}.json"
    bloco: dict[str, Any] = json.loads(arquivo.read_text(encoding="utf-8"))["ci"]
    return bloco


def _caminhos(perfil: str) -> list[str]:
    """
    Lista os caminhos que o Lighthouse CI audita num perfil.

    Args:
        perfil (str): ``"mobile"`` ou ``"desktop"``.

    Returns:
        list[str]: Caminhos (``/``), sem o host do servidor local.
    """
    urls: list[str] = _configuracao(perfil)["collect"]["url"]
    return [re.sub(r"^https?://[^/]+", "", url) for url in urls]


class _LeitorDeRecursos(HTMLParser):
    """
    Lista os endereços que o navegador baixa sozinho ao abrir a página.

    Attributes:
        enderecos (list[str]): Cada ``src``, candidato do ``srcset``, ``poster`` e
            ``href`` de ``<link>`` que baixa algo, na ordem da página.
    """

    def __init__(self) -> None:
        """Começa sem endereço anotado."""
        super().__init__()
        self.enderecos: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """
        Anota os endereços de recurso da tag.

        Args:
            tag (str): Nome da tag, em minúsculas.
            attrs (list[tuple[str, str | None]]): Atributos da tag.
        """
        atributos = {nome: valor or "" for nome, valor in attrs}
        if tag in _TAGS_COM_SRC:
            for nome in ("src", "poster"):
                if atributos.get(nome):
                    self.enderecos.append(atributos[nome])
            for candidato in atributos.get("srcset", "").split(","):
                if candidato.strip():
                    self.enderecos.append(candidato.split()[0])
        elif tag == "link" and atributos.get("href"):
            rel = set(atributos.get("rel", "").lower().split())
            if not rel <= _REL_SEM_DOWNLOAD:
                self.enderecos.append(atributos["href"])


def _recursos_de_fora(html: str) -> list[str]:
    """
    Lista os recursos da página que vêm de outro host.

    Args:
        html (str): O HTML entregue.

    Returns:
        list[str]: Os endereços absolutos (``http:``, ``https:`` ou ``//``).
    """
    leitor = _LeitorDeRecursos()
    leitor.feed(html)
    return [e for e in leitor.enderecos if e.startswith(("http:", "https:", "//"))]


# ---------------------------------------------------------------------------
# O comando
# ---------------------------------------------------------------------------


def test_recusa_rodar_com_debug_desligado() -> None:
    """Dado ``DEBUG=False``, o comando para antes de criar qualquer coisa."""
    with pytest.raises(CommandError, match="DEBUG=True"):
        call_command("semear_dados_demo")
    assert [modelo.objects.count() for modelo in _MODELOS_SEMEADOS] == [0] * 6


def test_nenhuma_estatistica() -> None:
    """O modelo Estatistica saiu do projeto: não há o que semear (spec 008, RF-05)."""
    nomes = {
        modelo.__name__ for modelo in apps.get_app_config("app_portfolio").get_models()
    }
    # Controle positivo: a lista dos models do app foi lida de fato.
    assert "Perfil" in nomes
    assert "Estatistica" not in nomes


@pytest.mark.usefixtures("banco_semeado", "_demo")
class TestBancoSemeado:
    def test_cria_perfil_projetos_e_habilidades(self) -> None:
        """Dado ``DEBUG=True``, cria tudo o que a Home exibe, com as imagens."""
        perfil = Perfil.objects.get()
        assert perfil.foto
        assert perfil.anos_experiencia > 0
        projetos = list(Projeto.objects.all())
        assert len(projetos) == 6
        assert all(projeto.imagem for projeto in projetos)
        assert Habilidade.objects.count() == 18

    def test_habilidades_com_nivel_e_tecnologia(self) -> None:
        """Os três níveis aparecem, e a habilidade com projeto fica ligada (RF-21)."""
        niveis = set(Habilidade.objects.values_list("nivel", flat=True))
        assert niveis == set(NivelHabilidade.values)
        python = Habilidade.objects.get(nome="Python")
        assert python.tecnologia is not None
        assert python.tecnologia.projeto_set.exists()

    def test_projetos_com_versao_no_ar_e_estudo_de_caso(self) -> None:
        """Todo projeto tem o endereço no ar em example.com e o estudo de caso."""
        projetos = list(Projeto.objects.all())
        assert len(projetos) == 6
        for projeto in projetos:
            assert projeto.link_online
            assert projeto.link_online.startswith("https://example.com/")
            assert projeto.tem_estudo_de_caso

    def test_projetos_equilibrados(self) -> None:
        """Seis projetos, dois por categoria, com as mesmas peças no card (RF-30)."""
        assert Projeto.objects.count() == 6
        categorias = list(CategoriaProjeto.objects.all())
        assert len(categorias) == 3
        for categoria in categorias:
            assert categoria.projetos.count() == 2, categoria.nome
        for projeto in Projeto.objects.all():
            assert projeto.tecnologias.count() == 5, projeto.titulo
            assert projeto.link_github
            assert all(
                campo.strip()
                for campo in (
                    projeto.problema,
                    projeto.papel,
                    projeto.decisao_tecnica,
                    projeto.resultado,
                )
            ), projeto.titulo

    def test_habilidades_na_proporcao_e_com_contagem_descendo(self) -> None:
        """
        Cada categoria tem 3, 2 e 1 habilidades por nível; no dia a dia a contagem varia
        e fica acima da de "já usei", e "estudando" não tem projeto (RF-31).
        """
        assert CategoriaHabilidade.objects.count() == 3
        contagens_do_dia_a_dia: set[int] = set()
        for categoria in CategoriaHabilidade.objects.all():
            por_nivel: dict[str, list[int]] = {
                nivel: [] for nivel in NivelHabilidade.values
            }
            for habilidade in categoria.habilidades.select_related("tecnologia"):
                tecnologia = habilidade.tecnologia
                por_nivel[habilidade.nivel].append(
                    tecnologia.projeto_set.count() if tecnologia else 0
                )
            assert [len(por_nivel[nivel]) for nivel in NivelHabilidade.values] == [
                3,
                2,
                1,
            ]
            assert min(por_nivel[NivelHabilidade.DIA_A_DIA]) > max(
                por_nivel[NivelHabilidade.JA_USEI]
            )
            assert por_nivel[NivelHabilidade.JA_USEI] == [1, 1]
            assert por_nivel[NivelHabilidade.ESTUDANDO] == [0]
            contagens_do_dia_a_dia.update(por_nivel[NivelHabilidade.DIA_A_DIA])
        assert len(contagens_do_dia_a_dia) > 1

    def test_cada_filtro_mostra_dois_projetos(self, client: Client) -> None:
        """Na home semeada, cada categoria marca dois cards para o filtro (RF-30)."""
        html = client.get("/").content.decode()

        for slug in ("web-app", "api", "mobile"):
            assert html.count(f'data-category="{slug}"') == 2, slug

    def test_rodar_duas_vezes_nao_duplica_nada(self) -> None:
        """Dado um banco já semeado, rodar de novo não cria registro nenhum."""
        antes = [modelo.objects.count() for modelo in _MODELOS_SEMEADOS]
        # Controle: o banco semeado tem registro de cada model, então uma
        # duplicação mudaria a contagem.
        assert all(antes)

        call_command("semear_dados_demo")

        assert [modelo.objects.count() for modelo in _MODELOS_SEMEADOS] == antes

    @pytest.mark.parametrize("perfil", ["mobile", "desktop"])
    def test_toda_url_auditada_responde_200(self, perfil: str, client: Client) -> None:
        """Cada página auditada existe no banco semeado (senão o CI audita um 404)."""
        respostas = {c: client.get(c).status_code for c in _caminhos(perfil)}

        assert respostas
        assert respostas == {c: 200 for c in _caminhos(perfil)}

    def test_nenhuma_pagina_carrega_recurso_de_fora(self, client: Client) -> None:
        """No banco semeado, nenhuma página puxa imagem, script ou CSS de outro host."""
        caminhos = _caminhos("mobile")
        assert caminhos
        for caminho in caminhos:
            html = client.get(caminho).content.decode()
            assert _recursos_de_fora(html) == [], caminho


# ---------------------------------------------------------------------------
# O leitor de recursos externos
# ---------------------------------------------------------------------------


# Casos escritos aqui: um leitor que nunca acha nada também deixaria toda página passar.
@pytest.mark.parametrize(
    ("trecho", "de_fora"),
    [
        ('<img src="https://cdn.example/a.png">', ["https://cdn.example/a.png"]),
        ('<script src="//cdn.example/a.js"></script>', ["//cdn.example/a.js"]),
        (
            '<link href="http://fontes.example/a.css" rel="stylesheet">',
            ["http://fontes.example/a.css"],
        ),
        (
            '<link rel="icon" href="https://cdn.example/i.png">',
            ["https://cdn.example/i.png"],
        ),
        (
            '<img src="/a.png" srcset="/a.png 1x, https://cdn.example/a2.png 2x">',
            ["https://cdn.example/a2.png"],
        ),
        (
            '<video poster="https://cdn.example/capa.jpg"></video>',
            ["https://cdn.example/capa.jpg"],
        ),
        ('<img src="/static/a.png" srcset="/static/a@2x.png 2x">', []),
        ('<a href="https://github.com/exemplo">GitHub</a>', []),
        ('<link rel="canonical" href="https://exemplo.com.br/">', []),
        ('<meta property="og:image" content="https://exemplo.com.br/a.jpg">', []),
    ],
)
def test_leitor_acha_cada_recurso_de_fora(trecho: str, de_fora: list[str]) -> None:
    """Acha o endereço absoluto em src, srcset, poster e link; navegação não conta."""
    assert _recursos_de_fora(trecho) == de_fora


# ---------------------------------------------------------------------------
# A configuração do Lighthouse
# ---------------------------------------------------------------------------


def test_mobile_e_desktop_auditam_as_mesmas_paginas_com_as_mesmas_checagens() -> None:
    """Dado os dois perfis, só os limites mudam: páginas e auditorias são as mesmas."""
    mobile, desktop = _configuracao("mobile"), _configuracao("desktop")

    assert mobile["collect"]["url"] == desktop["collect"]["url"]
    assert (
        mobile["assert"]["assertions"].keys() == desktop["assert"]["assertions"].keys()
    )
    assert desktop["collect"]["settings"]["preset"] == "desktop"
    assert "preset" not in mobile["collect"]["settings"]


@pytest.mark.parametrize("perfil", ["mobile", "desktop"])
@pytest.mark.parametrize("auditoria", _ASSERCOES_PROPRIAS)
def test_auditorias_com_assercao_propria(perfil: str, auditoria: str) -> None:
    """Dado cada perfil, as auditorias que a nota geral esconde têm asserção de erro."""
    regra = _configuracao(perfil)["assert"]["assertions"][auditoria]

    assert regra[0] == "error"
