"""
Testes do redesenho da home para quem avalia o portfólio — spec 008.

Cobre a conversão do progresso em nível (a migração ``0025``), o estudo de caso
do ``Projeto``, a marca gerada das iniciais (``marca.py``), o HTML da home
(hero, ordem das seções, cartão de projeto, chips de habilidade, rodapé e logo)
e a migração completa de ida e volta.

Estratégia de isolamento: nenhuma chamada de rede. A fixture autouse
``ambiente_isolado`` desliga o modo demonstração e a ``URL_PUBLICA`` (o ``.env``
de quem roda a suíte pode ligá-los) e põe o mailer ``default`` em memória, como
no resto da suíte. O teste de migração usa ``django_db(transaction=True)``, que
devolve o banco ao estado das migrações ao terminar.
"""

import importlib
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from PIL import Image

from app_portfolio.marca import (
    calcular_iniciais,
    gerar_icone_png,
    montar_favicon_svg,
)
from app_portfolio.models import (
    CategoriaHabilidade,
    Habilidade,
    NivelHabilidade,
    Perfil,
    Projeto,
    Tecnologia,
)

RAIZ = Path(__file__).resolve().parent.parent

# A migração começa por dígito: só o importlib a alcança.
migracao_0025 = importlib.import_module(
    "app_portfolio.migrations.0025_converter_habilidades"
)

# ---------------------------------------------------------------------------
# Fixtures e auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ambiente_isolado(settings, tmp_path) -> None:
    """Parte de um site sem endereço público e sem modo demonstração."""
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.MEDIA_ROOT = str(tmp_path)  # o upload do currículo não suja media/
    settings.URL_PUBLICA = ""
    settings.MODO_DEMONSTRACAO = False
    settings.SECURE_SSL_REDIRECT = False


def _perfil(**campos: Any) -> Perfil:
    """
    Cria o perfil da home com o mínimo obrigatório.

    Args:
        **campos (Any): Campos que substituem os padrões do teste.

    Returns:
        Perfil: O perfil salvo, com todo campo opcional vazio.
    """
    padrao: dict[str, Any] = {"nome": "Ana Dev", "cargo": "Desenvolvedora"}
    padrao.update(campos)
    return Perfil.objects.create(**padrao)


def _home(client) -> str:
    """
    Baixa a home e devolve o HTML, conferindo o 200.

    Args:
        client (django.test.Client): Cliente de teste do Django.

    Returns:
        str: O corpo da resposta em texto.
    """
    resposta = client.get("/")
    assert resposta.status_code == 200
    return str(resposta.content.decode("utf-8"))


def _trecho(html: str, inicio: str, fim: str) -> str:
    """
    Recorta o HTML entre dois marcadores, para conferir uma região só.

    Args:
        html (str): A página inteira.
        inicio (str): Texto que abre a região (incluído).
        fim (str): Texto que fecha a região (excluído), procurado depois do início.

    Returns:
        str: O pedaço do HTML entre os dois.
    """
    comeco = html.index(inicio)
    return html[comeco : html.index(fim, comeco)]


def _hero(html: str) -> str:
    """
    Recorta a seção hero.

    Args:
        html (str): A página inteira.

    Returns:
        str: O HTML do ``<section id="home">``.
    """
    return _trecho(html, 'id="home"', "</section>")


def _rodape(html: str) -> str:
    """
    Recorta o rodapé.

    Args:
        html (str): A página inteira.

    Returns:
        str: O HTML do ``<footer>``.
    """
    return _trecho(html, '<footer class="footer">', "</footer>")


def _projeto(**campos: Any) -> Projeto:
    """
    Monta um ``Projeto`` em memória, sem gravar.

    Args:
        **campos (Any): Campos que substituem os padrões do teste.

    Returns:
        Projeto: A instância, pronta para ler propriedades.
    """
    padrao: dict[str, Any] = {"titulo": "Loja", "descricao": "Uma loja."}
    padrao.update(campos)
    return Projeto(**padrao)


# ---------------------------------------------------------------------------
# Conversão do progresso em nível (RF-20)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("progresso", "nivel"),
    [
        (0, "estudando"),
        (49, "estudando"),
        (50, "ja_usei"),
        (79, "ja_usei"),
        (80, "dia_a_dia"),
        (100, "dia_a_dia"),
    ],
)
def test_nivel_pelo_progresso_nas_bordas(progresso: int, nivel: str) -> None:
    """Cada faixa do RF-20 começa e termina no número certo."""
    assert migracao_0025.nivel_pelo_progresso(progresso) == nivel


# ---------------------------------------------------------------------------
# Estudo de caso (RF-10)
# ---------------------------------------------------------------------------


def test_sem_campo_preenchido_nao_ha_estudo_de_caso() -> None:
    """Os quatro campos vazios (ou só com espaços) não abrem o "Como foi feito"."""
    assert _projeto().tem_estudo_de_caso is False
    assert _projeto(problema="   ").tem_estudo_de_caso is False


def test_um_campo_preenchido_basta() -> None:
    """Qualquer um dos quatro campos com texto liga o estudo de caso."""
    assert _projeto(resultado="Usado por 3 lojas.").tem_estudo_de_caso is True


def test_quatro_campos_preenchidos() -> None:
    """Com os quatro campos, o estudo de caso também aparece."""
    projeto = _projeto(problema="P", papel="Q", decisao_tecnica="R", resultado="S")
    assert projeto.tem_estudo_de_caso is True


# ---------------------------------------------------------------------------
# Marca: iniciais, favicon e ícone de tela inicial (RF-16 a RF-18)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "iniciais"),
    [
        ("Érica de Souza", "ÉS"),
        ("ana maria silva", "AS"),
        ("Madonna", "M"),
        ("João 2º Lima", "JL"),
        ("  Ana   Dev  ", "AD"),
        ("", "SN"),
        ("123 456", "SN"),
        (None, "SN"),
    ],
)
def test_calcular_iniciais(nome: str | None, iniciais: str) -> None:
    """Primeira e última palavra com letra, em maiúsculas; sem nome, "Seu Nome"."""
    assert calcular_iniciais(nome) == iniciais


def test_favicon_svg_pequeno_e_com_as_iniciais() -> None:
    """O SVG cabe em 2 KiB (RNF-04) e traz as iniciais como texto."""
    svg = montar_favicon_svg("ÉS")
    assert len(svg.encode("utf-8")) < 2048
    assert svg.startswith("<svg") and ">ÉS</text>" in svg


def test_favicon_svg_escapa_o_texto() -> None:
    """Um caractere de marcação nunca entra cru no SVG (defesa em profundidade)."""
    svg = montar_favicon_svg("<&")
    assert "&lt;&amp;</text>" in svg
    assert "<&" not in svg


def test_icone_png_opaco_de_180() -> None:
    """O PNG tem 180 x 180 e modo RGB, sem canal de transparência."""
    with Image.open(BytesIO(gerar_icone_png("SN"))) as imagem:
        assert imagem.format == "PNG"
        assert imagem.size == (180, 180)
        assert imagem.mode == "RGB"


def test_icone_png_memoizado() -> None:
    """As mesmas iniciais devolvem o mesmo desenho, sem redesenhar."""
    gerar_icone_png.cache_clear()
    gerar_icone_png("AB")
    gerar_icone_png("AB")
    assert gerar_icone_png.cache_info().hits == 1


@pytest.mark.django_db
class TestRotasDaMarca:
    """As rotas dos ícones gerados, com e sem perfil, e o ?v= do <head>."""

    def test_favicon_svg_com_perfil(self, client) -> None:
        """Com perfil, 200 em SVG, com cache público de um dia."""
        Perfil.objects.create(nome="Ana Dev", cargo="Dev")
        resposta = client.get("/favicon.svg")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "image/svg+xml"
        assert "max-age=86400" in resposta["Cache-Control"]
        assert "public" in resposta["Cache-Control"]
        assert ">AD</text>" in resposta.content.decode()

    def test_icone_png_com_perfil(self, client) -> None:
        """Com perfil, 200 em PNG, com cache público de um dia."""
        Perfil.objects.create(nome="Ana Dev", cargo="Dev")
        resposta = client.get("/apple-touch-icon.png")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "image/png"
        assert "max-age=86400" in resposta["Cache-Control"]

    @pytest.mark.parametrize(
        ("rota", "reserva"),
        [
            ("/favicon.svg", "/static/icons/favicon.webp"),
            ("/apple-touch-icon.png", "/static/icons/apple-touch-icon.png"),
        ],
    )
    def test_sem_perfil_redireciona_para_a_reserva(
        self, client, rota: str, reserva: str
    ) -> None:
        """Sem perfil, 302 para o arquivo de static/icons/, sem cache."""
        resposta = client.get(rota)
        assert resposta.status_code == 302
        assert resposta["Location"] == reserva
        assert "max-age" not in resposta.get("Cache-Control", "")

    def test_rota_recusa_post(self, client) -> None:
        """Só GET e HEAD: o ícone não aceita escrita."""
        assert client.post("/favicon.svg").status_code == 405

    def test_head_declara_o_svg_so_com_perfil(self, client) -> None:
        """Sem perfil, o <head> fica só com o favicon.webp de reserva."""
        html = client.get("/").content.decode()
        assert 'type="image/svg+xml"' not in html
        assert 'type="image/webp"' in html

    def test_versao_dos_icones_muda_com_o_nome(self, client) -> None:
        """Trocar o nome troca o ?v= do favicon e do apple-touch-icon (RF-18)."""
        perfil = Perfil.objects.create(nome="Ana Dev", cargo="Dev")
        html = client.get("/").content.decode()
        assert 'href="/favicon.svg?v=AD"' in html
        assert 'href="/apple-touch-icon.png?v=AD"' in html
        # O SVG vem antes do webp: o navegador usa o primeiro que entende.
        assert html.index("image/svg+xml") < html.index("image/webp")

        perfil.nome = "Érica Souza"
        perfil.save()
        html = client.get("/").content.decode()
        assert re.search(r'href="/favicon\.svg\?v=%C3%89S"', html)


# ---------------------------------------------------------------------------
# Hero (RF-01 a RF-05)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHero:
    """O hero sai do Perfil e dos dados, sem saudação nem código decorativo."""

    def test_sem_saudacao_codigo_nem_explorar(self, client) -> None:
        """O <h1> traz só o nome; saudação, bloco de código e "Explorar" saíram."""
        _perfil(bio_curta="Construo APIs.")
        hero = _hero(_home(client))
        assert '<h1 id="hero-title" class="hero__title">Ana Dev</h1>' in hero
        assert '<p class="hero__role">Desenvolvedora</p>' in hero
        assert "Construo APIs." in hero
        for resto in ("Olá, eu sou", "hero__code-block", "developer.js", "Explorar"):
            assert resto not in hero

    def test_template_sem_texto_fixo_no_hero(self) -> None:
        """Nenhum cargo, tecnologia ou frase de apresentação escritos no home.html."""
        template = (RAIZ / "templates/home.html").read_text(encoding="utf-8")
        hero = _trecho(template, 'id="home"', "</section>")
        for fixo in ("Full-Stack", "Developer", "Python", "Django", "React"):
            assert fixo not in hero

    def test_selo_com_status_e_local(self, client) -> None:
        """Os dois campos aparecem no selo, separados por "·"."""
        _perfil(status_trabalho="Disponível", localizacao="Recife, PE")
        selo = _trecho(_home(client), 'class="hero__selo"', "</p>")
        assert "Disponível · Recife, PE" in selo

    def test_selo_so_com_status(self, client) -> None:
        """Sem local, o selo fica só com o status, sem separador."""
        _perfil(status_trabalho="Disponível")
        selo = _trecho(_home(client), 'class="hero__selo"', "</p>")
        assert "Disponível" in selo
        assert "·" not in selo

    def test_sem_status_nao_ha_selo(self, client) -> None:
        """Status vazio esconde o selo, mesmo com o local preenchido."""
        _perfil(localizacao="Recife, PE")
        assert "hero__selo" not in _home(client)

    def test_acoes_levam_a_projetos_e_ao_contato(self, client) -> None:
        """O "Ver projetos" vai a #projects; o "ou entre em contato", a #contact."""
        _perfil()
        hero = _hero(_home(client))
        assert re.search(
            r'<a href="#projects" class="btn btn--primary">\s*Ver projetos', hero
        )
        assert (
            '<a href="#contact" class="hero__contato">ou entre em contato</a>' in hero
        )

    def test_links_de_icone_com_cada_campo(self, client) -> None:
        """GitHub e LinkedIn em nova aba, currículo como download, com nome."""
        arquivo = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", "application/pdf")
        _perfil(
            link_github="https://github.com/ana",
            link_linkedin="https://www.linkedin.com/in/ana",
            curriculo=arquivo,
        )
        hero = _hero(_home(client))
        assert re.search(
            r'href="https://github\.com/ana"[^>]*target="_blank"[^>]*'
            r'rel="noopener noreferrer"[^>]*aria-label="GitHub"',
            hero,
        )
        assert 'aria-label="LinkedIn"' in hero
        assert re.search(r'href="/media/curriculo/cv[^"]*"[^>]*download', hero)
        assert 'aria-label="Baixar currículo"' in hero

    def test_sem_links_nao_ha_icones(self, client) -> None:
        """Campos vazios não geram link nenhum, nem href="None"."""
        _perfil()
        html = _home(client)
        assert "hero__links" not in html
        assert 'href="None"' not in html

    def test_numeros_no_plural(self, client) -> None:
        """Anos do perfil e projetos contados, no plural."""
        _perfil(anos_experiencia=5)
        Projeto.objects.create(titulo="A", descricao="a")
        Projeto.objects.create(titulo="B", descricao="b")
        numeros = _trecho(_home(client), 'class="hero__numeros"', "</ul>")
        assert "5+</strong> anos de experiência" in numeros
        assert "2</strong> projetos publicados" in numeros

    def test_numeros_no_singular(self, client) -> None:
        """Com 1, "ano" e "projeto publicado" no singular."""
        _perfil(anos_experiencia=1)
        Projeto.objects.create(titulo="A", descricao="a")
        numeros = _trecho(_home(client), 'class="hero__numeros"', "</ul>")
        assert "1+</strong> ano de experiência" in numeros
        assert "1</strong> projeto publicado<" in numeros

    def test_so_o_numero_que_existe(self, client) -> None:
        """Zero anos some; os projetos ficam."""
        _perfil(anos_experiencia=0)
        Projeto.objects.create(titulo="A", descricao="a")
        numeros = _trecho(_home(client), 'class="hero__numeros"', "</ul>")
        assert "experiência" not in numeros
        assert "projeto publicado" in numeros

    def test_sem_numeros_nao_ha_linha(self, client) -> None:
        """Sem anos e sem projetos, a linha de números não aparece."""
        _perfil()
        assert "hero__numeros" not in _home(client)

    def test_foto_e_a_imagem_prioritaria(self, client) -> None:
        """A foto do hero carrega cedo, com medidas, e cai na reserva sem foto."""
        _perfil()
        foto = re.search(r'<img[^>]*class="hero__foto"[^>]*>', _home(client), re.S)
        assert foto
        tag = foto.group(0)
        assert 'fetchpriority="high"' in tag
        assert 'loading="lazy"' not in tag
        assert 'width="340"' in tag and 'height="425"' in tag
        assert "icons/default_perfil.webp" in tag
        assert 'alt="Foto de Ana Dev"' in tag

    def test_selo_do_sobre_pelos_anos(self, client) -> None:
        """O selo da foto do Sobre lê anos_experiencia; com zero, some."""
        _perfil(anos_experiencia=3)
        assert "about__experience-badge" in _home(client)
        Perfil.objects.update(anos_experiencia=0)
        assert "about__experience-badge" not in _home(client)


# ---------------------------------------------------------------------------
# Ordem das seções, menu e rótulos (RF-07, RF-08)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrdemERotulos:
    """Projetos logo depois do hero, com o menu e os rótulos novos."""

    ORDEM = ["#home", "#projects", "#about", "#skills", "#contact"]

    def test_secoes_na_ordem_nova(self, client) -> None:
        """Hero, Projetos, Sobre, Habilidades, Contato, com as âncoras de antes."""
        html = _home(client)
        posicoes = [html.index(f'id="{ancora[1:]}"') for ancora in self.ORDEM]
        assert posicoes == sorted(posicoes)

    def test_menu_e_links_rapidos_na_mesma_ordem(self, client) -> None:
        """O menu do topo e os "Links rápidos" seguem a ordem das seções."""
        html = _home(client)
        menu = re.findall(r'href="(#\w+)" class="nav__link', html)
        rapidos = re.findall(r'href="(#\w+)" class="footer__link"', html)
        assert menu == self.ORDEM
        assert rapidos == self.ORDEM

    def test_rotulos_novos(self, client) -> None:
        """Os quatro rótulos dizem o que a seção oferece; os antigos saíram."""
        html = _home(client)
        for rotulo in (
            "Quem sou",
            "Estudos de caso",
            "Com o que trabalho",
            "Próximo passo",
        ):
            assert f'<span class="section__subtitle">{rotulo}</span>' in html
        for antigo in (
            "Conheça-me",
            "Meu Trabalho",
            "Minhas Competências",
            "Vamos Conversar",
        ):
            assert antigo not in html


# ---------------------------------------------------------------------------
# Cartão de projeto (RF-09, RF-10)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCartaoDeProjeto:
    """Links da versão no ar e do código, e o estudo de caso."""

    def test_versao_no_ar_e_codigo(self, client) -> None:
        """Os dois links em nova aba, com o título do projeto no nome acessível."""
        Projeto.objects.create(
            titulo="Loja",
            descricao="d",
            link_online="https://example.com/loja",
            link_github="https://github.com/a/loja",
        )
        acoes = _trecho(_home(client), 'class="project-card__acoes"', "</div>")
        for endereco in ("https://example.com/loja", "https://github.com/a/loja"):
            assert re.search(
                rf'href="{re.escape(endereco)}"[^>]*target="_blank"[^>]*'
                r'rel="noopener noreferrer"',
                acoes,
            )
        assert 'Ver online<span class="sr-only">: Loja</span>' in acoes
        assert 'Código<span class="sr-only">: Loja</span>' in acoes

    def test_so_a_versao_no_ar(self, client) -> None:
        """Com um endereço só, só o link dele aparece."""
        Projeto.objects.create(
            titulo="Loja", descricao="d", link_online="https://example.com/loja"
        )
        acoes = _trecho(_home(client), 'class="project-card__acoes"', "</div>")
        assert "Ver online" in acoes
        assert "Código" not in acoes

    def test_sem_links_nao_ha_linha_de_acoes(self, client) -> None:
        """Sem nenhum endereço, o cartão não tem linha de ações."""
        Projeto.objects.create(titulo="Loja", descricao="d")
        html = _home(client)
        assert "project-card__acoes" not in html
        assert 'href="None"' not in html

    def test_estudo_de_caso_com_os_campos_preenchidos(self, client) -> None:
        """O "Como foi feito" nasce fechado e mostra só os campos com texto."""
        Projeto.objects.create(
            titulo="Loja", descricao="d", problema="Vendas no papel.", resultado="Ok."
        )
        caso = _trecho(_home(client), "<details", "</details>")
        assert "open" not in caso.split(">", 1)[0]
        assert ">Como foi feito</summary>" in caso
        assert "<dt>Problema</dt>" in caso and "Vendas no papel." in caso
        assert "<dt>Resultado</dt>" in caso
        assert "Meu papel" not in caso and "Decisão técnica" not in caso

    def test_sem_estudo_de_caso_nao_ha_details(self, client) -> None:
        """Os quatro campos vazios: o cartão não tem "Como foi feito"."""
        Projeto.objects.create(titulo="Loja", descricao="d")
        assert "<details" not in _home(client)

    def test_cartao_declara_as_tecnologias(self, client) -> None:
        """data-tecnologias traz os ids, separados por espaço, para o filtro."""
        django = Tecnologia.objects.create(nome="Django")
        python = Tecnologia.objects.create(nome="Python")
        projeto = Projeto.objects.create(titulo="Loja", descricao="d")
        projeto.tecnologias.set([django, python])
        atributo = re.search(r'data-tecnologias="([^"]*)"', _home(client))
        assert atributo
        assert sorted(atributo.group(1).split()) == sorted(
            [str(django.pk), str(python.pk)]
        )

    def test_linha_de_estado_do_filtro_nasce_escondida(self, client) -> None:
        """A linha do filtro por chip existe escondida, focável só por script."""
        html = _home(client)
        linha = re.search(r'<p class="projects__estado"[^>]*>', html)
        assert linha
        assert 'tabindex="-1"' in linha.group(0) and "hidden" in linha.group(0)
        assert (
            '<button type="button" class="projects__limpar">Limpar filtro</button>'
            in html
        )


# ---------------------------------------------------------------------------
# Habilidades em chips (RF-11, RF-12, RF-14)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChipsDeHabilidade:
    """Chips agrupados por nível, com a contagem dos projetos que os provam."""

    @pytest.fixture
    def habilidades(self) -> dict[str, Tecnologia]:
        """
        Cria uma categoria com três habilidades em dois níveis.

        Returns:
            dict[str, Tecnologia]: As tecnologias criadas, pelo nome.
        """
        django = Tecnologia.objects.create(nome="Django")
        python = Tecnologia.objects.create(nome="Python")
        for titulo in ("A", "B"):
            projeto = Projeto.objects.create(titulo=titulo, descricao="d")
            projeto.tecnologias.add(django)
        Projeto.objects.get(titulo="A").tecnologias.add(python)

        categoria = CategoriaHabilidade.objects.create(nome="Back-end")
        Habilidade.objects.create(categoria=categoria, nome="Python", tecnologia=python)
        Habilidade.objects.create(categoria=categoria, nome="Django", tecnologia=django)
        Habilidade.objects.create(
            categoria=categoria, nome="GraphQL", nivel=NivelHabilidade.ESTUDANDO
        )
        return {"django": django, "python": python}

    def test_niveis_na_ordem_e_sem_nivel_vazio(self, client, habilidades) -> None:
        """O nível "Uso no dia a dia" vem antes de "Estudando"; nível vazio some."""
        skills = _trecho(_home(client), 'id="skills"', "</section>")
        assert '<h3 class="skills__category-title">Back-end</h3>' in skills
        assert skills.index("Uso no dia a dia") < skills.index("Estudando")
        assert "Já usei em projeto" not in skills

    def test_chip_com_projetos_e_botao_com_contagem(self, client, habilidades) -> None:
        """Contagem no plural e no singular; o chip leva o id e o nome da tecnologia."""
        skills = _trecho(_home(client), 'id="skills"', "</section>")
        django = habilidades["django"]
        assert re.search(
            rf'<button type="button" class="chip" data-tecnologia="{django.pk}" '
            r'data-nome="Django" aria-pressed="false">\s*<span>Django '
            r'<span class="chip__contagem">· 2 projetos</span></span>',
            skills,
        )
        assert "· 1 projeto</span>" in skills

    def test_chip_sem_projeto_nao_e_interativo(self, client, habilidades) -> None:
        """Sem tecnologia ligada, o chip é texto: <span>, sem contagem."""
        skills = _trecho(_home(client), 'id="skills"', "</section>")
        assert '<span class="chip">GraphQL</span>' in skills

    def test_tecnologia_sem_projeto_tambem_nao(self, client) -> None:
        """Ligada a uma tecnologia que nenhum projeto usa, o chip segue texto."""
        categoria = CategoriaHabilidade.objects.create(nome="Dados")
        sql = Tecnologia.objects.create(nome="SQL")
        Habilidade.objects.create(categoria=categoria, nome="SQL", tecnologia=sql)
        assert '<span class="chip">SQL</span>' in _home(client)

    def test_sem_porcentagem_barra_nem_faixa(self, client, habilidades) -> None:
        """Nada de barra, porcentagem ou faixa de ícones de tecnologia."""
        skills = _trecho(_home(client), 'id="skills"', "</section>")
        for resto in ('role="progressbar"', "%", "skills__icons", "icons/tech/"):
            assert resto not in skills


# ---------------------------------------------------------------------------
# Rodapé e logo (RF-15, RF-16)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRodapeELogo:
    """O rodapé lê o perfil; o logo ganha o monograma das iniciais."""

    def test_rodape_com_bio_e_as_duas_redes(self, client) -> None:
        """A bio curta vira a frase, e só GitHub e LinkedIn aparecem, em nova aba."""
        _perfil(
            bio_curta="Construo APIs.",
            link_github="https://github.com/ana",
            link_linkedin="https://www.linkedin.com/in/ana",
        )
        rodape = _rodape(_home(client))
        assert '<p class="footer__description">Construo APIs.</p>' in rodape
        assert re.search(r'href="https://github\.com/ana"[^>]*target="_blank"', rodape)
        assert 'href="https://www.linkedin.com/in/ana"' in rodape

    def test_rodape_sem_bio_nem_redes(self, client) -> None:
        """Sem bio e sem os dois links, somem a frase e o bloco de redes."""
        _perfil()
        rodape = _rodape(_home(client))
        assert "footer__description" not in rodape
        assert "footer__social" not in rodape
        assert 'href="None"' not in rodape

    def test_nenhuma_rede_fixa(self, client) -> None:
        """Facebook, Instagram, X e TikTok saíram da página."""
        _perfil(link_github="https://github.com/ana")
        html = _home(client)
        for rede in (
            "facebook.com",
            "instagram.com",
            "x.com/",
            "tiktok.com",
            "Facebook",
        ):
            assert rede not in html

    def test_logo_com_monograma_decorativo(self, client) -> None:
        """Menu e rodapé mostram as iniciais escondidas do leitor de tela e o nome."""
        _perfil(nome="Érica de Souza")
        html = _home(client)
        monograma = (
            '<span class="logo__monograma" data-iniciais="ÉS" aria-hidden="true">'
            "</span>"
        )
        assert html.count(monograma) == 2
        assert 'aria-label="Érica de Souza, voltar ao início"' in html
        assert "logo-bracket" not in html


# ---------------------------------------------------------------------------
# Sem regressão (RF-22)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_home_200_com_todo_opcional_vazio(client) -> None:
    """Perfil, projeto e habilidade com o mínimo: 200, sem href="None"."""
    _perfil()
    Projeto.objects.create(titulo="Loja", descricao="d")
    categoria = CategoriaHabilidade.objects.create(nome="Back-end")
    Habilidade.objects.create(categoria=categoria, nome="Python")
    html = _home(client)
    assert 'href="None"' not in html


@pytest.mark.django_db
def test_home_200_sem_perfil(client) -> None:
    """Sem perfil nenhum, a home abre com o nome padrão do template."""
    html = _home(client)
    assert '<h1 id="hero-title" class="hero__title">Seu Nome</h1>' in html
    assert 'data-iniciais="SN"' in html


# ---------------------------------------------------------------------------
# Migração de ida e volta (RF-20, ADR-03)
# ---------------------------------------------------------------------------

APP = "app_portfolio"
ANTES = [(APP, "0023_alter_perfil_curriculo")]
DEPOIS = [(APP, "0026_remove_campos_sem_uso")]


def _migrar(alvo: list[tuple[str, str]]) -> Any:
    """
    Leva o banco de teste até a migração pedida.

    Args:
        alvo (list[tuple[str, str]]): Pares ``(app, migração)`` de destino.

    Returns:
        Any: O registro de modelos históricos daquele ponto (``apps``).
    """
    executor = MigrationExecutor(connection)
    executor.migrate(alvo)
    return executor.loader.project_state(alvo).apps


@pytest.mark.django_db(transaction=True)
def test_migracao_converte_os_dados_e_volta() -> None:
    """Da 0023 à 0026: nível pelo progresso, ligação pelo nome, sem Estatistica."""
    try:
        antigos = _migrar(ANTES)
        tecnologia = antigos.get_model(APP, "Tecnologia")
        python = tecnologia.objects.create(nome="Python", ordem=1)
        tecnologia.objects.create(nome="python", ordem=5)
        categoria = antigos.get_model(APP, "CategoriaHabilidade").objects.create(
            nome="Back-end"
        )
        habilidade = antigos.get_model(APP, "Habilidade")
        for nome, progresso in (
            ("PYTHON", 90),
            ("React / Vue.js", 60),
            ("GraphQL", 20),
        ):
            habilidade.objects.create(
                categoria=categoria, nome=nome, progresso=progresso
            )
        antigos.get_model(APP, "Estatistica").objects.create(
            titulo="5+", legenda="Anos"
        )

        novos = _migrar(DEPOIS)
        convertidas = {
            h.nome: (h.nivel, h.tecnologia_id)
            for h in novos.get_model(APP, "Habilidade").objects.all()
        }
        # Sem diferença de maiúsculas, e a de menor ordem entre as homônimas.
        assert convertidas["PYTHON"] == ("dia_a_dia", python.pk)
        assert convertidas["React / Vue.js"] == ("ja_usei", None)
        assert convertidas["GraphQL"] == ("estudando", None)
        with pytest.raises(LookupError):
            novos.get_model(APP, "Estatistica")
        assert "app_portfolio_estatistica" not in connection.introspection.table_names()

        # Volta: o progresso aproximado de cada nível.
        de_volta = _migrar(ANTES)
        progressos = dict(
            de_volta.get_model(APP, "Habilidade").objects.values_list(
                "nome", "progresso"
            )
        )
        assert progressos == {"PYTHON": 90, "React / Vue.js": 65, "GraphQL": 30}
    finally:
        # Os próximos testes precisam do esquema atual.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


def test_campos_antigos_sairam_dos_modelos() -> None:
    """Progresso, opção de barras, ícones e mostrar_no_home não existem mais."""
    campos = {
        modelo: {campo.name for campo in modelo._meta.get_fields()}
        for modelo in (Perfil, Habilidade, Tecnologia, CategoriaHabilidade)
    }
    assert "mostrar_progresso" not in campos[Perfil]
    assert "progresso" not in campos[Habilidade]
    assert not {"icone", "mostrar_no_home"} & campos[Tecnologia]
    assert "icone" not in campos[CategoriaHabilidade]
