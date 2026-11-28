"""
Testes das correções de interface da auditoria — spec 004, RF-01 a RF-24.

O último grupo cobre a interface do modo demonstração (spec 005): o aviso fixo
do formulário, o aviso do envio com link e as regras novas do CSS e do JS.

Cobre o HTML renderizado da home (cliente de teste do Django), as respostas da
view de contato, as páginas de erro e as regras que só existem em arquivo
estático: o CSS e o JavaScript são lidos como texto e conferidos por regra
(contraste calculado dos tokens, blocos ``@media``, marcadores de comportamento).
O navegador real (axe-core, Tab, medidas do hero) foi usado na auditoria e fica
fora do pytest.

Estratégia de isolamento: nenhuma chamada de rede. O mailer ``default`` do
``settings.MAILERS`` vai para o backend em memória e ``ENDERECO_CONTATO`` ganha um
valor de teste, para
nenhum POST do formulário tentar o SMTP real do Gmail com a credencial do
``.env`` de quem roda a suíte. ``MEDIA_ROOT`` aponta para uma pasta temporária
(upload de currículo e de imagens), o cache é limpo a cada teste (rate limit por
IP) e ``SECURE_SSL_REDIRECT`` fica desligado. A falha de SMTP é simulada com
``send_mail`` mockado no ponto de uso (``app_portfolio.views``).
"""

import io
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory
from django.urls import reverse
from django.views.defaults import permission_denied, server_error
from PIL import Image

from app_portfolio.models import (
    CategoriaProjeto,
    Perfil,
    Projeto,
)
from app_portfolio.views import (
    MENSAGEM_DADOS_INVALIDOS,
    MENSAGEM_DEMONSTRACAO,
    MENSAGEM_ENVIADO,
    MENSAGEM_FALHA_ENVIO,
    MENSAGEM_LIMITE_ENVIO,
    TEXTO_LINK_DEMONSTRACAO,
)

RAIZ = Path(__file__).resolve().parent.parent

# Lidos uma vez como texto: a quebra de linha CRLF do Windows vira LF aqui.
CSS = (RAIZ / "static/css/styles.css").read_text(encoding="utf-8")
JS = (RAIZ / "static/js/main.js").read_text(encoding="utf-8")

# Mesmo piso do CSS para texto normal (WCAG 2.2, critério 1.4.3)
CONTRASTE_MINIMO = 4.5

# Corpo mínimo de um envio válido do formulário de contato
ENVIO_VALIDO = {
    "nome": "Visitante",
    "email": "visitante@example.com",
    "assunto": "Oi",
    "mensagem": "Mensagem de teste",
    "honeypot": "",
}
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


# ---------------------------------------------------------------------------
# Fixtures e auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ambiente_isolado(settings, tmp_path) -> None:
    """Isola e-mail, mídia, cache e redirecionamento HTTPS de cada teste."""
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.ENDERECO_CONTATO = "contato-teste@example.com"
    settings.MEDIA_ROOT = str(tmp_path)
    settings.SECURE_SSL_REDIRECT = False
    # O modo demonstração vem do .env local; os testes do modo o ligam à parte.
    settings.MODO_DEMONSTRACAO = False
    cache.clear()  # isola o rate limit por IP entre os testes


def _perfil(**campos) -> Perfil:
    """
    Cria o perfil da home com valores de teste.

    Args:
        **campos (dict): Campos do ``Perfil`` que substituem os padrões.

    Returns:
        Perfil: Perfil salvo, sem foto e sem currículo (ambos opcionais).
    """
    padrao = {"nome": "Ana Dev", "cargo": "Desenvolvedora"}
    return Perfil.objects.create(**{**padrao, **campos})


def _home(client) -> str:
    """
    Baixa a home e devolve o HTML.

    Args:
        client (django.test.Client): Cliente de teste do Django.

    Returns:
        str: Corpo da resposta decodificado em UTF-8.
    """
    resposta = client.get(reverse("home"))
    assert resposta.status_code == 200
    return str(resposta.content.decode("utf-8"))  # str(): o mypy vê Any no client


def _bloco(texto: str, cabecalho: str) -> str:
    """
    Extrai o conteúdo de um bloco ``{ ... }`` a partir do seu cabeçalho.

    Args:
        texto (str): CSS completo.
        cabecalho (str): Texto que abre o bloco, ex.: ``"@media (max-width: 640px)"``.

    Returns:
        str: O que está entre as chaves do bloco, com as chaves internas casadas.
    """
    inicio = texto.index(cabecalho)
    abre = texto.index("{", inicio)
    profundidade = 0
    for posicao in range(abre, len(texto)):
        if texto[posicao] == "{":
            profundidade += 1
        elif texto[posicao] == "}":
            profundidade -= 1
            if profundidade == 0:
                return texto[abre + 1 : posicao]
    raise AssertionError(f"bloco sem fechamento: {cabecalho}")


def _regra(texto: str, seletor: str) -> str:
    """
    Devolve as declarações da primeira regra cujo seletor é exatamente ``seletor``.

    Args:
        texto (str): CSS (ou o conteúdo de um bloco ``@media``).
        seletor (str): Seletor completo, ex.: ``".hero__stats"``.

    Returns:
        str: Texto entre as chaves da regra.
    """
    achado = re.search(rf"(?m)^\s*{re.escape(seletor)}\s*\{{([^}}]*)\}}", texto)
    assert achado, f"regra não encontrada: {seletor}"
    return achado.group(1)


def _tokens() -> dict[str, str]:
    """
    Lê as cores ``--color-*`` hexadecimais do ``:root`` do CSS.

    Returns:
        dict[str, str]: Nome do token (sem ``--``) para o valor ``#rrggbb``.
    """
    raiz = _bloco(CSS, ":root")
    return dict(re.findall(r"--(color-[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", raiz))


def _luminancia(cor: str) -> float:
    """
    Calcula a luminância relativa de uma cor ``#rrggbb`` (WCAG).

    Args:
        cor (str): Cor hexadecimal com ``#``.

    Returns:
        float: Luminância entre 0 (preto) e 1 (branco).
    """
    canais = [int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineares = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais
    ]
    return 0.2126 * lineares[0] + 0.7152 * lineares[1] + 0.0722 * lineares[2]


def _contraste(frente: str, fundo: str) -> float:
    """
    Calcula a razão de contraste WCAG entre duas cores.

    Args:
        frente (str): Cor do texto, ``#rrggbb``.
        fundo (str): Cor do fundo, ``#rrggbb``.

    Returns:
        float: Razão de 1 a 21.
    """
    claro, escuro = sorted((_luminancia(frente), _luminancia(fundo)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


# ---------------------------------------------------------------------------
# RF-01 — Home sem currículo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCurriculoOpcional:
    def test_home_sem_curriculo_responde_200(self, client) -> None:
        """Perfil sem PDF não derruba a home com ValueError (antes: erro 500)."""
        _perfil()
        html = _home(client)
        assert "Download CV" not in html

    def test_home_com_curriculo_mostra_o_botao(self, client) -> None:
        """Com o PDF anexado, o botão aparece e aponta para o arquivo."""
        arquivo = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", "application/pdf")
        _perfil(curriculo=arquivo)
        html = _home(client)
        assert "Download CV" in html
        assert "/media/curriculo/cv" in html


# ---------------------------------------------------------------------------
# RF-02 — O hero cabe na primeira tela do celular
# ---------------------------------------------------------------------------


class TestHeroNoCelular:
    """Spec 008 (ADR-10, RF-04): o hero substituiu o bloco de código e a tela inteira."""

    def test_hero_tem_a_altura_do_conteudo(self) -> None:
        """Sem min-height de tela inteira: o topo de Projetos aparece na primeira tela."""
        hero = _regra(CSS, ".hero")
        assert "min-height" not in hero
        assert "100svh" not in hero and "100vh" not in hero

    def test_foto_vai_para_o_topo_e_fica_redonda_no_celular(self) -> None:
        """Até 768 px a foto sobe (order: -1), tem 160 px e é redonda (adendo, RF-25)."""
        bloco = _bloco(CSS, "@media (max-width: 768px) {\n    .hero__container")
        moldura = _regra(bloco, ".hero__foto-moldura")
        assert "order: -1" in moldura and "width: 160px" in moldura
        assert "border-radius: var(--radius-full)" in _regra(bloco, ".hero__foto")
        assert "grid-template-columns: 1fr" in _regra(bloco, ".hero__container")
        assert "width: 100%" in _regra(bloco, ".hero__acoes .btn")

    def test_foto_recortada_pelo_alto(self) -> None:
        """O recorte parte do alto: o círculo não corta a cabeça (adendo, ADR-12)."""
        assert "object-position: center top" in _regra(CSS, ".hero__foto")


# ---------------------------------------------------------------------------
# RF-03 — O visitante vê o resultado do envio
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeedbackDoFormulario:
    def test_limite_de_envio_devolve_a_frase_completa_em_json(self, client) -> None:
        """O 429 traz a mensagem completa (antes: "Muitas tentativas...")."""
        url = reverse("home")
        client.post(url, ENVIO_VALIDO, **AJAX)
        resposta = client.post(url, ENVIO_VALIDO, **AJAX)
        assert resposta.status_code == 429
        assert resposta.json()["message"] == MENSAGEM_LIMITE_ENVIO
        assert "..." not in resposta.json()["message"]

    def test_dados_invalidos_devolvem_mensagem_em_json(self, client) -> None:
        """O 400 explica o que fazer, não só "Dados inválidos."."""
        resposta = client.post(
            reverse("home"), {**ENVIO_VALIDO, "email": "nao-e-email"}, **AJAX
        )
        assert resposta.status_code == 400
        assert resposta.json()["message"] == MENSAGEM_DADOS_INVALIDOS

    def test_falha_de_smtp_devolve_mensagem_em_json(self, client) -> None:
        """O 500 por falha de e-mail traz a frase para o visitante."""
        with patch("app_portfolio.views.send_mail", side_effect=Exception("SMTP")):
            resposta = client.post(reverse("home"), ENVIO_VALIDO, **AJAX)
        assert resposta.status_code == 500
        assert resposta.json()["message"] == MENSAGEM_FALHA_ENVIO

    def test_envio_html_valido_mostra_aviso_de_sucesso(self, client) -> None:
        """Sem JavaScript, o redirect leva um aviso de sucesso visível."""
        resposta = client.post(reverse("home"), ENVIO_VALIDO, follow=True)
        html = resposta.content.decode("utf-8")
        assert "notification notification--success" in html
        assert MENSAGEM_ENVIADO in html

    def test_envio_html_barrado_mostra_o_limite(self, client) -> None:
        """Sem JavaScript, o segundo envio mostra o aviso de limite."""
        url = reverse("home")
        client.post(url, ENVIO_VALIDO, follow=True)
        html = client.post(url, ENVIO_VALIDO, follow=True).content.decode("utf-8")
        assert "notification notification--error" in html
        assert MENSAGEM_LIMITE_ENVIO in html

    def test_envio_html_invalido_mostra_aviso(self, client) -> None:
        """Sem JavaScript, o formulário inválido volta com um aviso de erro."""
        resposta = client.post(reverse("home"), {**ENVIO_VALIDO, "email": "x"})
        html = resposta.content.decode("utf-8")
        assert MENSAGEM_DADOS_INVALIDOS in html
        assert "notification--error" in html

    def test_envio_html_com_falha_de_smtp_mostra_aviso(self, client) -> None:
        """Sem JavaScript, a falha de e-mail também avisa o visitante."""
        with patch("app_portfolio.views.send_mail", side_effect=Exception("SMTP")):
            resposta = client.post(reverse("home"), ENVIO_VALIDO)
        assert MENSAGEM_FALHA_ENVIO in resposta.content.decode("utf-8")

    def test_javascript_trata_toda_resposta_que_nao_e_sucesso(self) -> None:
        """O main.js tem o ramo de erro com a mensagem do servidor (antes só success)."""
        assert "resposta.ok" in JS
        assert re.search(r"\}\s*else\s*\{\s*mostrarNotificacao\(", JS)
        assert "dados.message" in JS


# ---------------------------------------------------------------------------
# RF-04 — Menu do celular e foco por teclado
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMenuDoCelular:
    def test_botao_do_menu_declara_o_estado(self, client) -> None:
        """O hambúrguer nasce com aria-expanded="false" e aponta para o painel."""
        _perfil()
        html = _home(client)
        botao = re.search(r'<button[^>]*id="nav-toggle"[^>]*>', html)
        assert botao
        assert 'aria-expanded="false"' in botao.group(0)
        assert 'aria-controls="nav-menu"' in botao.group(0)

    def test_javascript_bloqueia_o_painel_fechado(self) -> None:
        """O painel é inert fechado (no celular) e o foco vai e volta ao abrir e fechar."""
        assert "const bloqueado = MENU_DE_CELULAR.matches && !menuEstaAberto();" in JS
        assert "navMenu.inert = bloqueado;" in JS
        assert "matchMedia('(max-width: 768px)')" in JS
        assert "setAttribute('aria-expanded', 'true')" in JS
        assert "devolverFoco" in JS
        assert "e.key === 'Escape'" in JS

    def test_javascript_devolve_o_foco_antes_do_inert(self) -> None:
        """O foco volta ao botão ANTES do painel virar inert (senão cai no body)."""
        # Fatia até a função seguinte: o cabeçalho de fecharMenu() tem chaves
        # (parâmetro desestruturado) que atrapalhariam o _bloco().
        corpo = JS[JS.index("function fecharMenu(") : JS.index("function iniciarMenu(")]
        assert corpo.index("navToggle.focus()") < corpo.index("sincronizarMenu()")

    def test_corte_do_menu_bate_com_o_css(self) -> None:
        """O ponto de corte do JavaScript é o mesmo do @media do menu."""
        assert "@media (max-width: 768px) {\n    .nav__menu" in CSS

    def test_ha_anel_de_foco_para_teclado(self) -> None:
        """Existe regra :focus-visible, e o JS não alterna mais .keyboard-nav."""
        assert "outline: 2px solid var(--color-accent)" in _regra(CSS, ":focus-visible")
        assert "keyboard-nav" not in JS

    def test_outline_none_so_nos_campos_com_anel_proprio(self) -> None:
        """O único outline: none é o do campo, que troca por borda e sombra."""
        regra = _regra(CSS, ".form__input:focus,\n.form__textarea:focus")
        assert "outline: none" in regra and "box-shadow" in regra
        assert CSS.count("outline: none") == 1


# ---------------------------------------------------------------------------
# Adendo, RF-25 a RF-28 — Painel abaixo da barra, botão único, véu e redes
# ---------------------------------------------------------------------------

LINK_GITHUB = "https://github.com/ana-dev"
LINK_LINKEDIN = "https://www.linkedin.com/in/ana-dev"


def _extras(html: str) -> str:
    """
    Recorta o bloco de redes e currículo do painel do menu.

    Args:
        html (str): HTML da home.

    Returns:
        str: Do ``nav__extras`` até o fim do painel, ou ``""`` sem o bloco.
    """
    if 'class="nav__extras"' not in html:
        return ""
    inicio = html.index('class="nav__extras"')
    return html[inicio : html.index('class="nav__veu"', inicio)]


def _perfil_completo(**campos) -> Perfil:
    """
    Cria o perfil com GitHub, LinkedIn e currículo, menos o que ``campos`` zerar.

    Args:
        **campos (dict): Campos do ``Perfil`` que substituem os padrões.

    Returns:
        Perfil: Perfil salvo.
    """
    padrao = {
        "link_github": LINK_GITHUB,
        "link_linkedin": LINK_LINKEDIN,
        "curriculo": SimpleUploadedFile("cv.pdf", b"%PDF-1.4", "application/pdf"),
    }
    return _perfil(**{**padrao, **campos})


@pytest.mark.django_db
class TestMenuComRedesECurriculo:
    def test_tres_campos_dao_os_dois_grupos(self, client) -> None:
        """Com os três campos, "Redes Sociais" tem GitHub e LinkedIn em nova aba e "Currículo" baixa o PDF."""
        _perfil_completo()
        bloco = _extras(_home(client))
        assert 'id="nav-grupo-redes">Redes Sociais</p>' in bloco
        assert 'id="nav-grupo-curriculo">Currículo</p>' in bloco
        assert bloco.count('aria-labelledby="nav-grupo-redes"') == 1
        assert bloco.count('aria-labelledby="nav-grupo-curriculo"') == 1
        for endereco, nome in ((LINK_GITHUB, "GitHub"), (LINK_LINKEDIN, "LinkedIn")):
            link = re.search(
                rf'<a href="{re.escape(endereco)}"[^>]*>(.*?)</a>', bloco, re.S
            )
            assert link, nome
            assert 'target="_blank"' in link.group(0)
            assert 'rel="noopener noreferrer"' in link.group(0)
            assert nome in link.group(1)
        curriculo = re.search(
            r'<a href="/media/curriculo/cv[^"]*"[^>]*>(.*?)</a>', bloco, re.S
        )
        assert curriculo
        assert " download" in curriculo.group(0)
        assert "Download CV" in curriculo.group(1)

    @pytest.mark.parametrize(
        ("campo", "some", "grupo_fica"),
        [
            ("link_github", "GitHub", "nav-grupo-redes"),
            ("link_linkedin", "LinkedIn", "nav-grupo-redes"),
            ("curriculo", "Download CV", "nav-grupo-redes"),
        ],
    )
    def test_campo_vazio_tira_so_o_link_dele(
        self, client, campo: str, some: str, grupo_fica: str
    ) -> None:
        """Campo vazio tira o link, nunca vira href="None", e o outro grupo continua."""
        _perfil_completo(**{campo: ""})
        bloco = _extras(_home(client))
        assert some not in bloco
        assert 'href="None"' not in bloco
        assert f'id="{grupo_fica}"' in bloco

    @pytest.mark.parametrize(
        ("fica", "rotulo", "grupo"),
        [
            ("link_github", "GitHub", "nav-grupo-redes"),
            ("link_linkedin", "LinkedIn", "nav-grupo-redes"),
            ("curriculo", "Download CV", "nav-grupo-curriculo"),
        ],
    )
    def test_um_campo_so_basta_para_o_bloco(
        self, client, fica: str, rotulo: str, grupo: str
    ) -> None:
        """Cada um dos três campos, sozinho, já mostra o bloco com o link dele."""
        vazios = {
            campo: ""
            for campo in ("link_github", "link_linkedin", "curriculo")
            if campo != fica
        }
        _perfil_completo(**vazios)
        bloco = _extras(_home(client))
        assert f'id="{grupo}"' in bloco
        assert rotulo in bloco
        assert len(re.findall(r'class="nav__extra"', bloco)) == 1

    def test_grupo_sem_link_some(self, client) -> None:
        """Sem GitHub e LinkedIn some "Redes Sociais"; sem currículo some "Currículo"."""
        _perfil_completo(link_github="", link_linkedin="")
        bloco = _extras(_home(client))
        assert "nav-grupo-redes" not in bloco
        assert "nav-grupo-curriculo" in bloco

        Perfil.objects.all().delete()
        _perfil_completo(curriculo="")
        bloco = _extras(_home(client))
        assert "nav-grupo-curriculo" not in bloco
        assert "nav-grupo-redes" in bloco

    def test_sem_os_tres_campos_o_bloco_some(self, client) -> None:
        """Sem GitHub, LinkedIn nem currículo, o painel não tem o bloco."""
        _perfil()
        html = _home(client)
        assert 'class="nav__extras"' not in html
        assert "nav__grupo" not in html

    def test_rotulos_usam_a_mesma_classe(self, client) -> None:
        """Os dois rótulos são <p class="nav__grupo">, sem nível de título (ADR-13)."""
        _perfil_completo()
        bloco = _extras(_home(client))
        assert (
            len(re.findall(r'<p class="nav__grupo" id="nav-grupo-[a-z]+">', bloco)) == 2
        )
        assert "<h" not in bloco

    def test_botao_da_barra_e_o_unico_controle(self, client) -> None:
        """Sem botão de fechar no painel; o da barra leva os dois ícones (ADR-12)."""
        _perfil()
        html = _home(client)
        assert "nav-close" not in html and "nav__close" not in html
        botao = re.search(r'<button[^>]*id="nav-toggle".*?</button>', html, re.S)
        assert botao
        assert 'aria-controls="nav-menu"' in botao.group(0)
        assert 'class="nav__icone-abrir"' in botao.group(0)
        assert 'class="nav__icone-fechar"' in botao.group(0)
        # O véu fica fora do painel e do botão: o "clique fora" do main.js o cobre
        assert html.index('class="nav__veu"') > html.index('id="nav-menu"')
        assert html.index('class="nav__veu"') < html.index('id="nav-toggle"')

    def test_painel_comeca_abaixo_da_barra_e_rola_por_dentro(self) -> None:
        """O painel parte de baixo da barra, com altura declarada, e rola por dentro (RF-25, RF-26)."""
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        regra = _regra(menu, ".nav__menu")
        assert "top: var(--header-height)" in regra
        assert "height: calc(100dvh - var(--header-height))" in regra
        assert "overflow-y: auto" in regra
        assert "bottom:" not in regra

    def test_painel_desliza_por_transform(self) -> None:
        """Abre por transform, sem animar right, left nem width; sombra só aberto (RF-27)."""
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        regra = _regra(menu, ".nav__menu")
        assert "transform: translateX(100%)" in regra
        assert "transition: transform var(--transition-slow)" in regra
        assert "box-shadow" not in regra
        aberto = _regra(menu, ".nav__menu.show")
        assert "transform: none" in aberto and "box-shadow" in aberto
        assert not re.search(r"transition:[^;]*\b(right|left|width)\b", menu)

    def test_veu_so_no_celular_e_com_altura_declarada(self) -> None:
        """O véu e o bloco somem acima de 768 px; o véu declara top e altura (ADR-14)."""
        assert "display: none" in _regra(CSS, ".nav__veu,\n.nav__extras")
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        veu = _regra(menu, ".nav__veu")
        assert "top: var(--header-height)" in veu
        assert "height: calc(100dvh - var(--header-height))" in veu
        assert "bottom:" not in veu and "inset" not in veu
        assert "visibility: visible" in _regra(menu, ".nav__menu.show ~ .nav__veu")

    def test_rotulos_tem_um_tamanho_e_links_tem_44_px(self) -> None:
        """.nav__grupo tem um font-size só, e cada link do bloco chega a 44 px (RF-26)."""
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        grupo = _regra(menu, ".nav__grupo")
        assert grupo.count("font-size") == 1
        assert "text-transform: uppercase" in grupo
        assert len(re.findall(r"(?m)^\s*\.nav__grupo \{", CSS)) == 1
        assert "min-height: 2.75rem" in _regra(menu, ".nav__extra")

    def test_contraste_do_bloco(self) -> None:
        """Rótulos e links passam de 4,5:1 no painel e ficam abaixo dos links de navegação."""
        cores = _tokens()
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        for seletor in (".nav__grupo", ".nav__extra"):
            assert "color: var(--color-gray-400)" in _regra(menu, seletor)
        assert "color: var(--color-gray-300)" in _regra(CSS, ".nav__link")
        fundo = cores["color-bg-secondary"]
        assert _contraste(cores["color-gray-400"], fundo) >= CONTRASTE_MINIMO
        assert _luminancia(cores["color-gray-400"]) < _luminancia(
            cores["color-gray-300"]
        )

    def test_icone_do_botao_segue_o_estado(self) -> None:
        """Com aria-expanded verdadeiro some o hambúrguer; com falso, o X."""
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        assert "display: none" in _regra(
            menu,
            ".nav__toggle[aria-expanded='true'] .nav__icone-abrir,\n"
            "    .nav__toggle[aria-expanded='false'] .nav__icone-fechar",
        )

    def test_javascript_alterna_e_troca_o_nome(self) -> None:
        """O clique alterna abrir e fechar; o nome do botão acompanha o estado."""
        abrir = JS[JS.index("function abrirMenu(") : JS.index("function fecharMenu(")]
        fechar = JS[
            JS.index("function fecharMenu(") : JS.index("function iniciarMenu(")
        ]
        assert "setAttribute('aria-label', 'Fechar menu')" in abrir
        assert "setAttribute('aria-label', 'Abrir menu')" in fechar
        iniciar = JS[JS.index("function iniciarMenu(") :]
        alternar = iniciar[: iniciar.index("navLinks.forEach")]
        assert "if (menuEstaAberto())" in alternar
        assert "fecharMenu({ devolverFoco: true })" in alternar
        assert "abrirMenu()" in alternar
        assert "navClose" not in JS


# ---------------------------------------------------------------------------
# RF-05 — Contraste do texto
# ---------------------------------------------------------------------------


class TestContraste:
    def test_texto_de_apoio_passa_em_todos_os_fundos(self) -> None:
        """--color-gray-400 tem 4,5:1 ou mais sobre os quatro fundos escuros."""
        cores = _tokens()
        for fundo in (
            "color-bg-primary",
            "color-bg-secondary",
            "color-bg-tertiary",
            "color-bg-card",
        ):
            razao = _contraste(cores["color-gray-400"], cores[fundo])
            assert razao >= CONTRASTE_MINIMO, (fundo, round(razao, 2))

    def test_copyright_e_placeholder_usam_o_token_legivel(self) -> None:
        """O copyright (era 2,18:1) e o texto de exemplo dos campos usam gray-400."""
        assert "var(--color-gray-400)" in _regra(CSS, ".footer__copyright")
        placeholder = _regra(
            CSS, ".form__input::placeholder,\n.form__textarea::placeholder"
        )
        assert "var(--color-gray-400)" in placeholder

    def test_nenhum_texto_usa_o_token_gray_500(self) -> None:
        """gray-500 (2,2:1) só serve de borda: nenhuma regra de cor de texto o usa."""
        usos = re.findall(r"(?m)^\s*color:\s*var\(--color-gray-500\)", CSS)
        assert usos == []


# ---------------------------------------------------------------------------
# RF-06 — Avisos acessíveis
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAvisos:
    def test_texto_branco_passa_em_cada_tipo_de_aviso(self) -> None:
        """Texto claro sobre sucesso, erro e informação tem 4,5:1 ou mais."""
        cores = _tokens()
        for fundo in ("color-success", "color-error", "color-info"):
            razao = _contraste(cores["color-white"], cores[fundo])
            assert razao >= CONTRASTE_MINIMO, (fundo, round(razao, 2))

    def test_javascript_nao_define_cores_nem_estilo_do_aviso(self) -> None:
        """As cores saíram do JS: o visual do aviso mora no CSS."""
        assert "style.cssText" not in JS
        assert "#10b981" not in JS and "#ef4444" not in JS

    def test_aviso_de_erro_e_anunciado_e_fechavel(self) -> None:
        """O erro leva role=alert; o botão de fechar tem nome e o contêiner é role=status."""
        assert "'role', 'alert'" in JS
        assert "'aria-label', 'Fechar aviso'" in JS
        assert "'role', 'status'" in JS

    def test_botao_de_fechar_tem_44_px(self) -> None:
        """A área do × tem 2,75rem (44 px); antes eram 9 x 16 px."""
        regra = _regra(CSS, ".notification__close")
        assert "width: 2.75rem" in regra and "height: 2.75rem" in regra

    def test_aviso_de_erro_do_servidor_e_uma_regiao_viva(self, client) -> None:
        """No fluxo HTML o aviso vem dentro de uma região role=status."""
        html = client.post(reverse("home"), {**ENVIO_VALIDO, "email": "x"}).content
        assert 'class="notifications" role="status"' in html.decode("utf-8")

    def test_regiao_viva_ja_existe_antes_do_primeiro_aviso(self, client) -> None:
        """A região vem vazia no HTML: criada junto com o aviso, o NVDA não a anunciava."""
        html = _home(client)
        assert re.search(r'class="notifications" role="status">\s*</div>', html)

    def test_xis_do_botao_de_fechar_fica_fora_do_anuncio(self) -> None:
        """O "×" é aria-hidden; o nome do botão vem do aria-label."""
        assert "xis.setAttribute('aria-hidden', 'true')" in JS

    def test_botao_de_fechar_fica_no_canto_superior(self) -> None:
        """No aviso de várias linhas, o × fica no topo, não no meio da caixa."""
        assert "align-self: flex-start" in _regra(CSS, ".notification__close")
        assert "fechar.setAttribute('aria-label', 'Fechar aviso')" in JS


# ---------------------------------------------------------------------------
# RF-08 — Movimento reduzido
# ---------------------------------------------------------------------------


class TestMovimentoReduzido:
    def test_css_tem_o_bloco_de_movimento_reduzido(self) -> None:
        """O bloco prefers-reduced-motion desliga rolagem suave e animações contínuas."""
        bloco = _bloco(CSS, "@media (prefers-reduced-motion: reduce)")
        assert "scroll-behavior: auto" in bloco
        assert "transition-duration: 0.01ms !important" in bloco
        assert "opacity: 1" in _regra(bloco, ".reveal")

    def test_bloco_de_movimento_reduzido_e_o_ultimo_do_arquivo(self) -> None:
        """Vem por último para vencer as regras de hover e de animação acima."""
        assert CSS.rindex("@media (prefers-reduced-motion: reduce)") > CSS.rindex(
            "@keyframes"
        )
        assert CSS.rindex("@media (prefers-reduced-motion: reduce)") > CSS.rindex(
            "@media (pointer: coarse)"
        )
        assert CSS.rindex("@media (prefers-reduced-motion: reduce)") > CSS.rindex(
            "@media (forced-colors: active)"
        )

    def test_rolagem_do_javascript_pergunta_o_criterio(self) -> None:
        """Nenhum behavior: 'smooth' fixo; tudo passa por comportamentoDeRolagem()."""
        assert "(prefers-reduced-motion: reduce)" in JS
        assert "behavior: 'smooth'" not in JS
        assert "behavior: comportamentoDeRolagem()" in JS


# ---------------------------------------------------------------------------
# RF-09 — Foto padrão do perfil
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_foto_padrao_do_perfil_existe(client) -> None:
    """Sem foto, o template aponta para um arquivo que existe (antes: 404)."""
    _perfil()
    html = _home(client)
    assert "icons/default_perfil.webp" in html
    assert "avatar_padrao" not in html
    assert finders.find("icons/default_perfil.webp")


class TestImagensPadrao:
    def test_foto_padrao_tem_a_proporcao_da_tela(self) -> None:
        """A foto de reserva é 4:5, a proporção do .about__image (antes: 928 x 1152)."""
        with Image.open(RAIZ / "static/icons/default_perfil.webp") as imagem:
            assert imagem.width * 5 == imagem.height * 4

    def test_capa_padrao_tem_a_proporcao_do_cartao(self) -> None:
        """A capa de reserva é 16:10, a do .project-card__image (antes: 1408 x 768)."""
        with Image.open(RAIZ / "static/icons/default_projeto.webp") as imagem:
            assert imagem.width * 10 == imagem.height * 16

    def test_imagens_padrao_sao_leves(self) -> None:
        """As duas pesam menos de 150 KiB (a capa tinha 622 KiB, com texto desenhado)."""
        for nome in ("default_perfil.webp", "default_projeto.webp"):
            assert (RAIZ / "static/icons" / nome).stat().st_size < 150 * 1024


# ---------------------------------------------------------------------------
# RF-10 — Link do GitHub opcional e com nome próprio
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLinkDoProjeto:
    def test_projeto_sem_link_nao_gera_href_none(self, client) -> None:
        """Sem repositório, o botão some e não sobra href="None"."""
        _perfil()
        Projeto.objects.create(titulo="Sem Repo", descricao="Descrição")
        html = _home(client)
        assert 'href="None"' not in html
        assert "project-card__acoes" not in html

    def test_cada_link_tem_nome_proprio(self, client) -> None:
        """O link do código ganha o nome do projeto para o leitor de tela (spec 008, RF-09)."""
        _perfil()
        Projeto.objects.create(
            titulo="Loja", descricao="Descrição", link_github="https://github.com/a/b"
        )
        html = _home(client)
        assert 'Código<span class="sr-only">: Loja</span>' in html


# ---------------------------------------------------------------------------
# RF-11 — O nome acessível começa pelo texto visível
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_nomes_acessiveis_comecam_pelo_texto_visivel(client) -> None:
    """O logo tem aria-label que começa pelo texto que aparece (o "Explorar" saiu na spec 008)."""
    _perfil(nome="Ana Dev")
    html = _home(client)
    assert 'aria-label="Ana Dev, voltar ao início"' in html


# ---------------------------------------------------------------------------
# RF-12 — Títulos sem pulo de nível
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rodape_nao_usa_h4(client) -> None:
    """Os títulos do rodapé são h2 (antes h4 logo depois de h2)."""
    _perfil(link_github="https://github.com/ana")
    html = _home(client)
    rodape = html[html.index('<footer class="footer">') :]
    assert "<h4" not in rodape
    assert html.count('<h2 class="footer__title">') == 2


# ---------------------------------------------------------------------------
# RF-13 — Filtros com estado e campos com autocomplete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFiltrosECampos:
    def test_filtros_declaram_aria_pressed(self, client) -> None:
        """O filtro "Todos" nasce pressionado; os demais, não."""
        _perfil()
        CategoriaProjeto.objects.create(nome="Web", slug="web")
        html = _home(client)
        assert re.search(r'data-filter="all"[^>]*aria-pressed="true"', html)
        assert re.search(r'data-filter="web"[^>]*aria-pressed="false"', html)
        assert 'id="projects-status"' in html

    def test_javascript_atualiza_o_estado_e_o_anuncio(self) -> None:
        """O JS alterna aria-pressed e escreve a contagem na região viva."""
        assert "setAttribute('aria-pressed', 'true')" in JS
        assert "projectsStatus.textContent" in JS

    def test_campos_pedem_preenchimento_automatico(self, client) -> None:
        """Nome e e-mail declaram o autocomplete certo (WCAG 1.3.5)."""
        _perfil()
        html = _home(client)
        assert re.search(r'name="nome"[^>]*autocomplete="name"', html)
        assert re.search(r'name="email"[^>]*autocomplete="email"', html)


# ---------------------------------------------------------------------------
# RF-14 — Sem texto provisório: o contato sai do perfil (o rodapé, spec 008)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestContatoERodape:
    def test_texto_do_link_sai_do_endereco_do_perfil(self, client) -> None:
        """O cartão mostra o endereço do perfil, não "/in/seu_usuario"."""
        # Os dois endereços passam por "https://" + "www." e "http://" + "www.":
        # cada corte do template tem um caso que depende dele.
        _perfil(
            link_linkedin="https://www.linkedin.com/in/ana",
            link_github="http://www.github.com/ana",
        )
        html = _home(client)
        assert ">linkedin.com/in/ana</a>" in html
        assert ">github.com/ana</a>" in html
        assert "seu_usuario" not in html

    def test_links_externos_do_contato_tem_noopener(self, client) -> None:
        """Os dois links do contato abrem em nova aba e levam rel=noopener."""
        _perfil(
            link_linkedin="https://www.linkedin.com/in/a",
            link_github="https://github.com/a",
        )
        html = _home(client)
        inicio = html.index('id="contact"')
        contato = html[inicio : html.index("</section>", inicio)]
        # A lista tem de ter os dois: um laço sobre uma lista vazia não confere nada.
        externos = re.findall(r'<a [^>]*target="_blank"[^>]*>', contato)
        assert len(externos) == 2
        for tag in externos:
            assert 'rel="noopener"' in tag

    def test_cartao_do_contato_some_sem_o_link(self, client) -> None:
        """Perfil sem LinkedIn não mostra o cartão do LinkedIn; com ele, mostra."""
        _perfil()
        assert 'contact__card-title">LinkedIn' not in _home(client)
        Perfil.objects.update(link_linkedin="https://www.linkedin.com/in/ana")
        assert 'contact__card-title">LinkedIn' in _home(client)

    def test_logo_do_rodape_leva_ao_topo(self, client) -> None:
        """O logo do rodapé aponta para #home, não para href="#"."""
        _perfil()
        html = _home(client)
        assert '<a href="#home" class="footer__logo">' in html
        assert 'href="#"' not in html


# ---------------------------------------------------------------------------
# RF-15 — Transições listadas e altura dinâmica
# ---------------------------------------------------------------------------


class TestTransicoesEAltura:
    def test_nenhuma_transicao_all(self) -> None:
        """Toda transição lista as propriedades (antes: 12 transition: all)."""
        assert "transition: all" not in CSS

    def test_menu_usa_unidade_dinamica(self) -> None:
        """O painel do menu usa 100dvh, com 100vh de reserva (o hero, spec 008, ADR-10)."""
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        regra = _regra(menu, ".nav__menu")
        assert regra.index("height: calc(100vh") < regra.index("height: calc(100dvh")


# ---------------------------------------------------------------------------
# RF-16 — Botões com a mesma altura
# ---------------------------------------------------------------------------


class TestAlturaDosBotoes:
    def test_botao_base_tem_borda_transparente(self) -> None:
        """.btn tem borda de 2px, então o primário e o secundário medem igual."""
        assert "border: 2px solid transparent" in _regra(CSS, ".btn")

    def test_secundario_so_troca_a_cor_da_borda(self) -> None:
        """.btn--secondary não redefine a espessura (usa border-color)."""
        regra = _regra(CSS, ".btn--secondary")
        assert "border-color" in regra
        assert "border: 2px" not in regra


# ---------------------------------------------------------------------------
# RF-17 — Fontes hospedadas no projeto
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFontesLocais:
    def test_pagina_nao_chama_o_google_fonts(self, client) -> None:
        """Nenhuma referência ao Google Fonts no HTML nem no CSS."""
        _perfil()
        html = _home(client)
        fontes_css = (RAIZ / "static/css/fontes.css").read_text(encoding="utf-8")
        for texto in (html, CSS, fontes_css):
            assert "fonts.googleapis.com" not in texto
            assert "fonts.gstatic.com" not in texto

    def test_arquivos_de_fonte_e_licencas_existem(self) -> None:
        """Cada @font-face aponta para um arquivo que existe, com a licença OFL ao lado."""
        fontes_css = (RAIZ / "static/css/fontes.css").read_text(encoding="utf-8")
        arquivos = re.findall(r"url\('\.\./fonts/([^']+)'\)", fontes_css)
        assert len(arquivos) == 2
        for nome in arquivos:
            assert (RAIZ / "static/fonts" / nome).is_file()
        assert (RAIZ / "static/fonts/OFL-inter.txt").is_file()
        assert (RAIZ / "static/fonts/OFL-jetbrains-mono.txt").is_file()

    def test_font_face_usa_swap(self) -> None:
        """Os dois @font-face usam font-display: swap (texto visível enquanto carrega)."""
        fontes_css = (RAIZ / "static/css/fontes.css").read_text(encoding="utf-8")
        assert fontes_css.count("font-display: swap;") == 2

    def test_home_carrega_fontes_css_e_faz_preload_da_inter(self, client) -> None:
        """O <head> traz o fontes.css e o preload do arquivo da Inter."""
        _perfil()
        html = _home(client)
        assert "css/fontes.css" in html
        assert 'rel="preload"' in html and "inter-latin-variavel.woff2" in html

    def test_csp_nao_libera_mais_o_google(self, settings) -> None:
        """Os hosts do Google saíram de style-src e font-src."""
        diretivas = settings.CONTENT_SECURITY_POLICY["DIRECTIVES"]
        for diretiva in ("style-src", "font-src"):
            assert all(
                "google" not in h and "gstatic" not in h for h in diretivas[diretiva]
            )


# ---------------------------------------------------------------------------
# RF-18 — Alvos de toque
# ---------------------------------------------------------------------------


class TestAlvosDeToque:
    def test_controles_pequenos_chegam_a_44_px_em_tela_de_toque(self) -> None:
        """Com pointer: coarse, filtros e links do rodapé e do contato têm 44 px."""
        bloco = _bloco(CSS, "@media (pointer: coarse)")
        assert "min-height: 2.75rem" in _regra(bloco, ".filter-btn")
        assert "min-height: 2.75rem" in _regra(bloco, ".footer__link")
        assert "padding-block: 0.75rem" in _regra(bloco, ".contact__card-link")
        assert "width: 2.75rem" in _regra(bloco, ".social__link")

    def test_botoes_do_menu_do_celular_tem_44_px(self) -> None:
        """O botão do menu tem 2,75rem; os links do painel, padding vertical."""
        menu = _bloco(CSS, "@media (max-width: 768px) {\n    .nav__menu")
        assert "width: 2.75rem" in _regra(menu, ".nav__toggle")
        assert "padding-block: 0.5rem" in _regra(menu, ".nav__link")


# ---------------------------------------------------------------------------
# RF-19 — Páginas de erro do projeto
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPaginasDeErro:
    def test_404_usa_a_pagina_do_projeto(self, client) -> None:
        """Endereço inexistente mostra a página em português, não a do Django."""
        resposta = client.get("/nao-existe/")
        html = resposta.content.decode("utf-8")
        assert resposta.status_code == 404
        assert 'lang="pt-BR"' in html and "Página não encontrada" in html
        assert 'name="viewport"' in html and "<main" in html and html.count("<h1") == 1
        assert 'name="robots" content="noindex"' in html

    def test_403_usa_a_pagina_do_projeto(self) -> None:
        """O handler de 403 renderiza o 403.html do projeto."""
        resposta = permission_denied(RequestFactory().get("/"), Exception())
        html = resposta.content.decode("utf-8")
        assert resposta.status_code == 403
        assert "Ação não permitida" in html and 'lang="pt-BR"' in html

    def test_500_nao_toca_no_banco(self, django_assert_num_queries) -> None:
        """O 500 é renderizado sem consulta ao banco, sessão ou contexto."""
        with django_assert_num_queries(0):
            resposta = server_error(RequestFactory().get("/"))
        html = resposta.content.decode("utf-8")
        assert resposta.status_code == 500
        assert "Algo deu errado" in html and "Voltar para a página inicial" in html

    def test_400_de_host_recusado_usa_a_pagina_do_projeto(
        self, client, settings
    ) -> None:
        """Host fora do ALLOWED_HOSTS mostra a página em português, não "Bad Request (400)"."""
        settings.ALLOWED_HOSTS = ["testserver"]
        resposta = client.get("/", HTTP_HOST="outro-host.example")
        html = resposta.content.decode("utf-8")
        assert resposta.status_code == 400
        assert "Pedido inválido" in html and 'lang="pt-BR"' in html
        assert 'name="robots" content="noindex"' in html

    def test_falha_de_csrf_usa_a_pagina_do_projeto(self) -> None:
        """POST sem token CSRF mostra o 403_csrf.html, não a página do Django em inglês."""
        resposta = Client(enforce_csrf_checks=True).post("/", {"nome": "Ana"})
        html = resposta.content.decode("utf-8")
        assert resposta.status_code == 403
        assert "Envio não confirmado" in html and 'lang="pt-BR"' in html
        assert "Forbidden" not in html and "CSRF verification failed" not in html

    def test_paginas_de_erro_nao_tem_javascript_nem_base(self) -> None:
        """O erro.html é independente: não herda o base.html e não carrega script."""
        texto = (RAIZ / "templates/erro.html").read_text(encoding="utf-8")
        assert "extends" not in texto and "<script" not in texto
        for nome in ("400", "403", "403_csrf", "404", "500"):
            filho = (RAIZ / f"templates/{nome}.html").read_text(encoding="utf-8")
            assert "{% extends 'erro.html' %}" in filho

    def test_paginas_de_erro_usam_o_favicon_das_iniciais(self) -> None:
        """O erro.html liga o favicon gerado antes da reserva, como a home (spec 008)."""
        texto = (RAIZ / "templates/erro.html").read_text(encoding="utf-8")
        svg = texto.find('type="image/svg+xml" href="/favicon.svg"')
        reserva = texto.find('type="image/webp"')
        assert -1 < svg < reserva


# ---------------------------------------------------------------------------
# RF-20 — Imagem de compartilhamento e ícone da aba
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompartilhamentoEIcone:
    def test_og_image_tem_endereco_absoluto(self, client) -> None:
        """A og:image sai com esquema e host, não só /media/..."""
        foto = SimpleUploadedFile("foto.webp", _webp_minimo(), "image/webp")
        _perfil(foto=foto)
        html = _home(client)
        achado = re.search(r'property="og:image" content="([^"]+)"', html)
        assert achado
        assert achado.group(1).startswith("http://testserver/media/perfil/")

    def test_favicon_declara_o_tipo_certo(self, client) -> None:
        """O <link rel=icon> diz image/webp para um arquivo .webp."""
        _perfil()
        html = _home(client)
        assert re.search(
            r'rel="icon" type="image/webp" href="[^"]*favicon\.webp"', html
        )

    def test_rota_do_favicon_ico_leva_a_um_arquivo_que_existe(self, client) -> None:
        """/favicon.ico redireciona para o favicon.webp (antes: favicon.png, 404)."""
        resposta = client.get("/favicon.ico")
        assert resposta.status_code == 302
        assert resposta["Location"] == "/static/icons/favicon.webp"
        assert finders.find("icons/favicon.webp")

    def test_favicon_e_leve_e_quadrado(self) -> None:
        """O ícone da aba é quadrado e pesa menos de 20 KiB (antes: 1024 x 1024, 516 KiB)."""
        arquivo = RAIZ / "static/icons/favicon.webp"
        assert arquivo.stat().st_size < 20 * 1024
        with Image.open(arquivo) as imagem:
            assert imagem.width == imagem.height <= 512


def _webp_minimo() -> bytes:
    """
    Gera um WebP 1x1 em memória para o upload da foto do perfil.

    Returns:
        bytes: Conteúdo de um arquivo ``.webp`` válido (o ``save()`` do model
            não reconverte WebP).
    """
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), "red").save(buffer, format="WEBP")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# RF-21 — Texto alternativo das capas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_capa_de_projeto_e_decorativa(client) -> None:
    """A capa tem alt vazio: o título ao lado já nomeia o projeto."""
    _perfil()
    Projeto.objects.create(titulo="Loja", descricao="Descrição")
    html = _home(client)
    capa = re.search(r'<img[^>]*class="project-card__img"[^>]*>', html, re.S)
    assert capa
    assert 'alt=""' in capa.group(0)
    assert "Thumbnail" not in html


# ---------------------------------------------------------------------------
# RF-22 — Sem código nem CSS sobrando
# ---------------------------------------------------------------------------


class TestSemCodigoSobrando:
    def test_css_sem_regras_de_classes_inexistentes(self) -> None:
        """As classes .project-card__overlay e __link não existem no HTML nem no CSS."""
        assert "project-card__overlay" not in CSS
        assert "project-card__link" not in CSS

    def test_javascript_sem_funcoes_desligadas(self) -> None:
        """Digitação, parallax, preloader e data-progress (que o template não gera) saíram."""
        for resto in ("data-progress", "initTypingEffect", "initParallax", "preloader"):
            assert resto not in JS


# ---------------------------------------------------------------------------
# RF-23 — Quebra de linha
# ---------------------------------------------------------------------------


def test_titulos_balanceados_e_paragrafos_sem_orfa() -> None:
    """text-wrap: balance nos títulos e pretty nos parágrafos e itens de lista."""
    assert "text-wrap: balance" in _regra(CSS, "h1,\nh2,\nh3,\nh4")
    assert "text-wrap: pretty" in _regra(CSS, "p,\nli")


# ---------------------------------------------------------------------------
# RF-24 — Rodapé alinhado e ícone legível
# ---------------------------------------------------------------------------


class TestRodapeEIcone:
    def test_colunas_do_rodape_alinham_pelo_topo(self) -> None:
        """As três colunas do rodapé começam na mesma altura."""
        assert "align-items: start" in _regra(CSS, ".footer__content")


# ---------------------------------------------------------------------------
# Spec 008, adendo — Cards do mesmo tamanho (RF-32, RF-33, ADR-15)
# ---------------------------------------------------------------------------


class TestCardsDoMesmoTamanho:
    def test_cards_de_habilidade_esticam_ate_a_fileira(self) -> None:
        """Os blocos de categoria da mesma linha ficam com a mesma altura."""
        assert "align-items: stretch" in _regra(CSS, ".skills__container")

    def test_acoes_do_projeto_ficam_no_pe_do_card(self) -> None:
        """Card e conteúdo em coluna flexível; as ações descem com margin-top: auto."""
        card = _regra(CSS, ".project-card")
        assert "display: flex" in card
        assert "flex-direction: column" in card
        assert "flex: 1" in _regra(CSS, ".project-card__content")
        assert "margin-top: auto" in _regra(CSS, ".project-card__acoes")

    def test_card_filtrado_some_mesmo_com_display_flex(self) -> None:
        """O [hidden] dos filtros vence o display: flex do card (senão nada some)."""
        assert "card.hidden = !mostrar" in JS
        assert "display: none" in _regra(CSS, ".project-card[hidden]")

    def test_tags_reservam_duas_linhas(self) -> None:
        """Com uma linha de tags num card e duas no vizinho, o resto segue alinhado."""
        tags = _regra(CSS, ".project-card__tech")
        assert "align-content: flex-start" in tags
        assert "min-height: calc(2 * (var(--fs-xs) * 1.6" in tags


# ---------------------------------------------------------------------------
# Spec 008 — Filtro por chip e alto contraste (RF-13, RNF-02, ADR-07, ADR-08)
# ---------------------------------------------------------------------------


class TestFiltroPorChip:
    def test_filtro_aceita_categoria_ou_tecnologia(self) -> None:
        """FiltrarProjetos recebe os dois e lê o data-tecnologias dos cartões."""
        assert (
            "function filtrarProjetos({ categoria = 'all', tecnologia = null } = {})"
            in JS
        )
        assert "card.getAttribute('data-tecnologias')" in JS

    def test_chip_le_os_atributos_do_template(self) -> None:
        """O chip informa o id e o nome da tecnologia pelos data-*."""
        assert "chip.getAttribute('data-tecnologia')" in JS
        assert "chip.getAttribute('data-nome')" in JS
        assert "iniciarChips();" in JS

    def test_chip_marca_o_estado_e_volta_a_categoria(self) -> None:
        """Um filtro por vez: o chip marca aria-pressed e zera a categoria."""
        aplicar = JS[
            JS.index("function aplicarChip(") : JS.index("function iniciarChips(")
        ]
        assert "chip.setAttribute('aria-pressed', 'true')" in aplicar
        assert "marcarCategoria(todos)" in aplicar

    def test_foco_e_rolagem_seguem_o_filtro(self) -> None:
        """Rola com comportamentoDeRolagem() e foca a linha de estado (ADR-08)."""
        aplicar = JS[
            JS.index("function aplicarChip(") : JS.index("function iniciarChips(")
        ]
        assert "behavior: comportamentoDeRolagem()" in aplicar
        assert "linhaDeEstado.focus({ preventScroll: true })" in aplicar
        assert "linhaDeEstado.hidden = false" in aplicar

    def test_regiao_viva_nao_repete_o_anuncio(self) -> None:
        """No filtro por chip quem anuncia é a linha; a região fica vazia."""
        aplicar = JS[
            JS.index("function aplicarChip(") : JS.index("function iniciarChips(")
        ]
        assert "projectsStatus.textContent = ''" in aplicar

    def test_categoria_desfaz_o_chip(self) -> None:
        """O clique numa categoria desmarca os chips antes de filtrar."""
        filtros = JS[
            JS.index("function iniciarFiltros(") : JS.index("// CHIPS DE HABILIDADE")
        ]
        assert "desmarcarChips();" in filtros

    def test_limpar_filtro_devolve_o_foco_ao_todos(self) -> None:
        """O botão some com a linha: o foco vai para o filtro "Todos"."""
        chips = JS[JS.index("function iniciarChips(") : JS.index("// REVELAR AO ROLAR")]
        assert "querySelector('.projects__limpar')" in chips
        assert "todos.focus()" in chips

    def test_linha_escondida_nao_aparece(self) -> None:
        """O [hidden] vence o display: flex da linha de estado."""
        assert "display: none" in _regra(CSS, ".projects__estado[hidden]")


def test_alto_contraste_mantem_as_bordas() -> None:
    """Em forced-colors, chips, selo, filtros e monograma têm borda; o marcado, Highlight."""
    bloco = _bloco(CSS, "@media (forced-colors: active)")
    seletores = ".chip,\n    .hero__selo,\n    .filter-btn,\n    .logo__monograma"
    assert "border: 1px solid CanvasText" in _regra(bloco, seletores)
    marcado = _regra(bloco, ".chip[aria-pressed='true'],\n    .filter-btn.active")
    assert "background: Highlight" in marcado


def test_chip_tem_40_px_e_borda() -> None:
    """O chip tem 40 px de altura (o vão completa 44) e borda visível (RNF-02)."""
    chip = _regra(CSS, ".chip")
    assert "min-height: 2.5rem" in chip
    assert "border: 1px solid var(--color-gray-500)" in chip


# ---------------------------------------------------------------------------
# Spec 005 — Modo demonstração: aviso fixo, aviso do envio, JS e CSS
# ---------------------------------------------------------------------------


def _sobrepor(cor: str, fundo: str, opacidade: float) -> str:
    """
    Compõe uma cor translúcida sobre um fundo opaco (mistura alfa).

    Args:
        cor (str): Cor de cima, ``#rrggbb``.
        fundo (str): Cor de baixo, ``#rrggbb``.
        opacidade (float): Alfa da cor de cima, de 0 a 1.

    Returns:
        str: A cor que o olho vê, ``#rrggbb``.
    """
    canais = [
        round(
            int(cor[i : i + 2], 16) * opacidade
            + int(fundo[i : i + 2], 16) * (1 - opacidade)
        )
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{c:02x}" for c in canais)


@pytest.mark.django_db
class TestModoDemonstracaoNaInterface:
    def test_aviso_fixo_aparece_com_o_modo_ligado(self, client, settings) -> None:
        """RF-04: o card do formulário avisa e aponta para o repositório."""
        settings.MODO_DEMONSTRACAO = True
        html = _home(client)
        assert 'class="contact__aviso"' in html
        assert "Formulário de demonstração: nenhuma mensagem é enviada." in html
        assert f'href="{settings.URL_REPOSITORIO}"' in html
        assert "Veja como ele funciona no GitHub" in html

    def test_aviso_fixo_vem_antes_do_primeiro_campo(self, client, settings) -> None:
        """RF-04: o aviso fica no topo do formulário, antes do campo Nome."""
        settings.MODO_DEMONSTRACAO = True
        html = _home(client)
        assert html.index("contact__aviso") < html.index('class="form__group"')

    def test_aviso_fixo_some_com_o_modo_desligado(self, client) -> None:
        """RF-04: sem o modo, o aviso não existe no HTML."""
        assert "contact__aviso" not in _home(client)

    def test_post_comum_mostra_aviso_info_com_link(self, client, settings) -> None:
        """RF-05: sem JavaScript, o redirect leva o aviso neutro com o link."""
        settings.MODO_DEMONSTRACAO = True
        resposta = client.post(reverse("home"), ENVIO_VALIDO, follow=True)
        html = resposta.content.decode("utf-8")
        assert "notification notification--info" in html
        assert "notification--demo" not in html  # level_tag, não tags
        assert MENSAGEM_DEMONSTRACAO in html
        assert f'href="{settings.URL_REPOSITORIO}" class="notification__link"' in html
        assert f">{TEXTO_LINK_DEMONSTRACAO}</a>." in html

    def test_javascript_tem_o_ramo_demo_sem_innerhtml(self) -> None:
        """RF-05, ADR-03: status demo vira aviso info; o link sai de createElement."""
        assert "dados.status === 'demo'" in JS
        assert "mostrarNotificacao(dados.message, 'info', dados.link)" in JS
        assert "createElement('a')" in JS
        assert "ancora.textContent = link.texto" in JS
        # Fora dos comentários, o único innerHTML é o do botão de enviar (texto fixo)
        codigo = [
            linha for linha in JS.splitlines() if not linha.strip().startswith("//")
        ]
        assert all("botaoEnviar" in linha for linha in codigo if "innerHTML" in linha)

    def test_aviso_com_link_nao_some_sozinho(self) -> None:
        """RF-05, ADR-05: o temporizador de 6 s pula o aviso com link."""
        assert "if (tipo !== 'error' && !link)" in JS

    def test_javascript_limpa_o_formulario_no_ramo_demo(self) -> None:
        """RF-05: depois do aviso de demonstração, os campos ficam vazios."""
        ramo = JS[JS.index("dados.status === 'demo'") :]
        assert ramo.index("contactForm.reset()") < ramo.index("} else {")

    def test_css_tem_a_variante_info_e_o_link_sublinhado(self) -> None:
        """RF-05: variante informativa própria; o link se distingue sem a cor."""
        assert "var(--color-info)" in _regra(CSS, ".notification--info")
        assert "text-decoration: underline" in _regra(CSS, ".notification__link")

    def test_aviso_longo_nao_ocupa_a_largura_do_desktop(self) -> None:
        """O contêiner dos avisos tem teto de 28rem (antes: a tela inteira a 1280 px)."""
        assert "max-width: min(28rem," in _regra(CSS, ".notifications")

    def test_contraste_do_aviso_do_envio(self) -> None:
        """RNF-02: texto e link brancos sobre o azul do aviso passam do AA."""
        tokens = _tokens()
        razao = _contraste(tokens["color-white"], tokens["color-info"])
        assert razao >= CONTRASTE_MINIMO

    def test_contraste_do_aviso_fixo(self) -> None:
        """RNF-02: texto e link do aviso fixo passam do AA sobre o fundo composto."""
        tokens = _tokens()
        regra = _regra(CSS, ".contact__aviso")
        assert "rgba(0, 212, 255, 0.08)" in regra
        fundo = _sobrepor(tokens["color-accent"], tokens["color-bg-card"], 0.08)
        assert _contraste(tokens["color-gray-100"], fundo) >= CONTRASTE_MINIMO
        assert _contraste(tokens["color-accent"], fundo) >= CONTRASTE_MINIMO
