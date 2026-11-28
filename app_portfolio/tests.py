"""
Testes da home, do formulário de contato e da conversão de imagem.

Cobrem o status e o número de consultas da página, a segurança do envio
(XSS, honeypot, limite por IP e a reserva atômica dele no cache, falha de
e-mail), os cabeçalhos de segurança, o tipo do arquivo do currículo e a
conversão para WebP no ``save()`` dos models.

Estratégia de isolamento: nenhuma chamada de rede real é feita durante a
suíte, e nenhum teste depende do conteúdo do `.env` local. O mailer `default`
do `settings.MAILERS` é trocado para o backend em memória do Django e
`settings.ENDERECO_CONTATO` é fixado num valor de teste (`disable_real_email`,
abaixo) — sem isso, os testes que passam pelo fluxo de POST do formulário de
contato disparariam `send_mail()` contra o SMTP real do Gmail configurado em
`settings.py` usando a credencial real do `.env` de quem estiver rodando a
suíte, tornando os testes lentos, dependentes de rede, capazes de enviar
e-mails de verdade, e dependentes de uma variável de ambiente que não existe
em CI. A falha de envio (`test_contato_erro_envio_email`) mocka
`views.send_mail` diretamente, no ponto de uso. O modo demonstração (spec
005) começa desligado em cada teste (`modo_demonstracao_desligado`), e a
leitura das chaves do `settings.py` roda numa cópia avulsa do módulo, com o
ambiente controlado (`_carregar_settings`).
"""

import importlib.util
import io
import json
import shutil
import threading
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import dotenv
import pytest
from django.core import mail
from django.core.cache import cache, caches
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, models
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import clear_url_caches, reverse
from PIL import Image

from app_portfolio.cache import CacheArquivoAtomico
from app_portfolio.middleware import PermissionsPolicyMiddleware
from app_portfolio.models import (
    CategoriaHabilidade,
    CategoriaProjeto,
    Habilidade,
    MensagemContato,
    NivelHabilidade,
    Perfil,
    Projeto,
    Tecnologia,
)
from app_portfolio.utils import imagem_ja_gravada
from app_portfolio.views import (
    MENSAGEM_DADOS_INVALIDOS,
    MENSAGEM_DEMONSTRACAO,
    MENSAGEM_ENVIADO,
    MENSAGEM_FALHA_ENVIO,
    MENSAGEM_LIMITE_ENVIO,
    TEXTO_LINK_DEMONSTRACAO,
)

if TYPE_CHECKING:
    # Só existe nos stubs: é a resposta do test client, com ``templates``.
    from django.test.client import _MonkeyPatchedWSGIResponse

# ---------------------------------------------------------------------------
# Fixtures de ambiente
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_cache():
    """Garante que o cache esteja limpo antes de cada teste de Rate Limit."""
    cache.clear()


@pytest.fixture(autouse=True)
def disable_ssl_redirect(settings):
    """
    Impedimos o redirecionamento HTTPS durante os testes para evitar
    erros de conexão no ambiente de teste controlado.
    """
    settings.SECURE_SSL_REDIRECT = False


@pytest.fixture(autouse=True)
def disable_real_email(settings):
    """
    Isola a suíte de qualquer credencial/estado de e-mail real.

    Troca o mailer `default` para o backend em memória do Django — sem isso,
    `views.home()` chamaria `send_mail()` contra o SMTP real do Gmail
    (host/porta fixos em `settings.py`) a cada POST de contato bem-sucedido.
    O test runner já faz essa troca; a fixture a deixa explícita.

    Também fixa `ENDERECO_CONTATO` num valor de teste: sem isso, a suíte
    herdaria o valor de `EMAIL_USER` do `.env` local (via `load_dotenv` em
    `settings.py`). Isso mascarava um bug — a suíte só passava na máquina de
    quem tinha um `.env` com credencial real preenchida, e falhava em CI (sem
    `.env`, `ENDERECO_CONTATO=None`), onde `send_mail()` com remetente/
    destinatário `None` não gera entrada em `mail.outbox`.
    """
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.ENDERECO_CONTATO = "contato-teste@example.com"


@pytest.fixture(autouse=True)
def modo_demonstracao_desligado(settings):
    """
    Parte de cada teste com o modo demonstração desligado (spec 005).

    O valor vem do `.env` local: quem roda a suíte com `MODO_DEMONSTRACAO=True`
    veria os testes do fluxo normal falharem. Os testes do modo o ligam pela
    fixture `settings`.
    """
    settings.MODO_DEMONSTRACAO = False


@pytest.fixture(autouse=True)
def media_root_tmp(settings, tmp_path):
    """
    Redireciona MEDIA_ROOT para um diretório temporário durante os testes.

    Sem isso, os testes de upload de imagem (`TestConverterParaWebp`)
    gravariam arquivos reais na pasta `media/` do projeto a cada execução.
    """
    settings.MEDIA_ROOT = str(tmp_path)


def _uploaded_png(nome: str = "teste.png", modo: str = "RGB") -> SimpleUploadedFile:
    """
    Gera um PNG 1x1 válido em memória para testar upload de imagem.

    Evita depender de um arquivo fixture versionado no repositório.

    Args:
        nome (str, optional): Nome do arquivo simulado. Padrão: "teste.png".
        modo (str, optional): Modo do Pillow; ``"RGBA"`` gera um pixel
            semitransparente. Padrão: "RGB".

    Returns:
        SimpleUploadedFile: Arquivo pronto para atribuir a um ImageField.
    """
    buffer = io.BytesIO()
    cor = (255, 0, 0, 128) if modo == "RGBA" else (255, 0, 0)
    Image.new(modo, (1, 1), color=cor).save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(nome, buffer.read(), content_type="image/png")


def _uploaded_webp(nome: str = "teste.webp") -> SimpleUploadedFile:
    """
    Gera um WebP 1x1 válido em memória, para o caso que não é reconvertido.

    Args:
        nome (str, optional): Nome do arquivo simulado. Padrão: "teste.webp".

    Returns:
        SimpleUploadedFile: Arquivo pronto para atribuir a um ImageField.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), color="blue").save(buffer, format="WEBP")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/webp")


def _formato_e_modo(arquivo: Any) -> tuple[str | None, str]:
    """
    Abre a imagem gravada num ImageField e devolve o formato real e o modo.

    O nome terminar em ``.webp`` não prova a conversão: o conteúdo pode ser outro.

    Args:
        arquivo (Any): O ``ImageFieldFile`` do model salvo.

    Returns:
        tuple[str | None, str]: O formato que o Pillow leu e o modo de cor.
    """
    with arquivo.open("rb") as aberto, Image.open(aberto) as imagem:
        return imagem.format, imagem.mode


def _dados_minimos(modelo: Any) -> dict[str, str]:
    """
    Campos obrigatórios de um Projeto ou de um Perfil.

    Args:
        modelo (Any): ``Projeto`` ou ``Perfil``.

    Returns:
        dict[str, str]: Os campos para criar o registro.
    """
    if modelo is Projeto:
        return {"titulo": "Semeado", "descricao": "Desc"}
    return {"nome": "Ana", "cargo": "Dev"}


def _arquivos_em(pasta: Path) -> list[str]:
    """
    Lista os arquivos de uma pasta do storage, em ordem.

    Args:
        pasta (Path): A pasta dentro do ``MEDIA_ROOT``.

    Returns:
        list[str]: Os nomes dos arquivos; vazia se a pasta não existe.
    """
    return sorted(p.name for p in pasta.iterdir()) if pasta.is_dir() else []


# Caminho do arquivo, não do módulo: a cópia avulsa é carregada direto do disco,
# sem passar pelo ``portfolio.settings`` que o Django já tem em uso.
_ARQUIVO_SETTINGS = Path(__file__).resolve().parent.parent / "portfolio" / "settings.py"


def _carregar_settings(monkeypatch: pytest.MonkeyPatch, **ambiente: str) -> ModuleType:
    """
    Executa uma cópia avulsa do ``settings.py`` com o ambiente pedido.

    A cópia não entra em ``sys.modules``: o ``django.conf.settings`` em uso e o
    módulo ``portfolio.settings`` seguem intactos. O ``load_dotenv`` vira no-op
    para o ``.env`` local não interferir, e as variáveis que o teste não passa
    saem do ambiente.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture do pytest que desfaz as
            trocas de ambiente no fim do teste.
        **ambiente (str): Variáveis de ambiente da execução (``SECRET_KEY``
            entra sempre, com um valor de teste).

    Returns:
        ModuleType: O módulo carregado, com as configurações calculadas.
    """
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    for nome in (
        "DEBUG",
        "MODO_DEMONSTRACAO",
        "EMAIL_USER",
        "EMAIL_PASS",
        "ALLOWED_HOSTS",
        "DIRETORIO_DADOS",
        "URL_PUBLICA",
        "ADMIN_URL",
    ):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("SECRET_KEY", "chave-de-teste")
    for nome, valor in ambiente.items():
        monkeypatch.setenv(nome, valor)

    spec = importlib.util.spec_from_file_location("settings_avulso", _ARQUIVO_SETTINGS)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ---------------------------------------------------------------------------
# Página e desempenho
# ---------------------------------------------------------------------------


@pytest.mark.django_db  # Permite que o teste acesse o banco de dados
class TestPortfolioCore:
    def test_home_status_code(self, client) -> None:
        """Verifica se a página inicial está carregando (Status 200)."""
        url = reverse("home")
        response = client.get(url)
        assert response.status_code == 200

    def test_perfil_creation(self) -> None:
        """Valida se o modelo de Perfil está aceitando inserções corretamente."""
        Perfil.objects.create(nome="Dev Teste", cargo="Sênior")
        assert Perfil.objects.count() == 1

    @staticmethod
    def _semear_vitrine(projetos: int) -> None:
        """
        Cria projetos e habilidades com tudo o que o template lê de outra tabela.

        Cada projeto tem categoria e duas tecnologias; cada categoria de habilidade
        tem uma habilidade ligada a uma tecnologia. Com o banco vazio, um
        ``select_related`` ou ``prefetch_related`` a menos não aparece na contagem.

        Args:
            projetos (int): Quantos projetos (e categorias de habilidade) criar,
                além dos que já existem.
        """
        inicio = Projeto.objects.count()
        for indice in range(inicio, inicio + projetos):
            categoria = CategoriaProjeto.objects.create(
                nome=f"Categoria {indice}", slug=f"categoria-{indice}"
            )
            tecnologias = [
                Tecnologia.objects.create(nome=f"Tecnologia {indice}-{lado}")
                for lado in ("a", "b")
            ]
            projeto = Projeto.objects.create(
                titulo=f"Projeto {indice}",
                descricao="Descrição",
                categoria_projeto=categoria,
            )
            projeto.tecnologias.set(tecnologias)
            grupo = CategoriaHabilidade.objects.create(nome=f"Grupo {indice}")
            Habilidade.objects.create(
                categoria=grupo,
                nome=f"Habilidade {indice}",
                nivel=NivelHabilidade.DIA_A_DIA,
                tecnologia=tecnologias[0],
            )

    @staticmethod
    def _consultas_da_home(client: Client) -> int:
        """
        Conta as consultas ao banco de um GET da home.

        Args:
            client (django.test.Client): Cliente de teste do Django.

        Returns:
            int: Quantas consultas a página fez.
        """
        with CaptureQueriesContext(connection) as consultas:
            assert client.get(reverse("home")).status_code == 200
        return len(consultas)

    def test_home_query_count(self, client) -> None:
        """
        O número de consultas da home não cresce com os projetos (sem N+1).

        Um select_related/prefetch_related a menos na view faria cada projeto, ou
        cada habilidade, custar uma consulta a mais.
        """
        self._semear_vitrine(1)
        com_um = self._consultas_da_home(client)
        self._semear_vitrine(3)
        assert Projeto.objects.count() == 4

        assert (com_um, self._consultas_da_home(client)) == (6, 6)

    def test_estaticos_usam_o_storage_comprimido_do_whitenoise(self, settings) -> None:
        """O storage dos estáticos vem de STORAGES (o STATICFILES_STORAGE é ignorado)."""
        backend = settings.STORAGES["staticfiles"]["BACKEND"]
        assert backend == "whitenoise.storage.CompressedStaticFilesStorage"
        assert settings.STORAGES["default"]["BACKEND"].endswith("FileSystemStorage")

    def test_home_envia_a_csp(self, client) -> None:
        """
        A resposta traz o cabeçalho CSP, com script só do próprio site.

        Ler o settings não basta: o django-csp 4 ignora os nomes antigos CSP_*,
        e o cabeçalho sumiu sem que nenhum teste de configuração acusasse.
        """
        csp = client.get(reverse("home"))["Content-Security-Policy"]
        diretivas = dict(
            (partes[0], partes[1:])
            for partes in (d.split() for d in csp.split(";") if d.strip())
        )
        # O dicionário inteiro: uma diretiva a mais (connect-src *) também é falha.
        # base-uri, form-action e frame-ancestors não herdam o default-src.
        assert diretivas == {
            "default-src": ["'self'"],
            "script-src": ["'self'"],
            "font-src": ["'self'"],
            "style-src": ["'self'"],
            "img-src": ["'self'", "data:", "https:"],
            "base-uri": ["'none'"],
            "form-action": ["'self'"],
            "object-src": ["'none'"],
            "frame-ancestors": ["'none'"],
        }

    def test_home_envia_permissions_policy(self, client) -> None:
        """A resposta nega os recursos do aparelho que o site não usa."""
        response = client.get(reverse("home"))
        # Escrito aqui, não importado do middleware: um recurso tirado da constante
        # sairia do valor esperado junto.
        assert response["Permissions-Policy"] == (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

    def test_permissions_policy_mantem_o_valor_da_view(self) -> None:
        """Uma view que já definiu o cabeçalho fica com o valor dela."""

        def view(request: HttpRequest) -> HttpResponse:
            """Responde com o cabeçalho já definido pela própria view."""
            resposta = HttpResponse()
            resposta["Permissions-Policy"] = "camera=(self)"
            return resposta

        resposta = PermissionsPolicyMiddleware(view)(RequestFactory().get("/"))
        assert resposta["Permissions-Policy"] == "camera=(self)"

    def test_home_envia_os_cabecalhos_do_navegador(self, client) -> None:
        """Página não enquadrável e tipo de conteúdo sem adivinhação."""
        response = client.get(reverse("home"))
        assert response["X-Frame-Options"] == "DENY"
        assert response["X-Content-Type-Options"] == "nosniff"


# ---------------------------------------------------------------------------
# Configuração do modo demonstração e do e-mail (spec 005)
# ---------------------------------------------------------------------------


class TestConfiguracaoBasica:
    def test_sem_secret_key_a_subida_falha(self, monkeypatch) -> None:
        """Sem SECRET_KEY o settings levanta o erro, com o caminho do .env conferido."""
        with pytest.raises(ValueError, match=r"SECRET_KEY não foi encontrada.*\.env"):
            _carregar_settings(monkeypatch, SECRET_KEY="")

    def test_debug_desligado_sem_a_chave(self, monkeypatch) -> None:
        """Sem DEBUG no ambiente, o site sobe como produção (falha fechada)."""
        assert _carregar_settings(monkeypatch).DEBUG is False

    @pytest.mark.parametrize(("valor", "esperado"), [("True", True), ("1", False)])
    def test_debug_so_liga_com_true(
        self, monkeypatch, valor: str, esperado: bool
    ) -> None:
        """Só 'true' (sem diferenciar maiúsculas) liga o DEBUG."""
        assert _carregar_settings(monkeypatch, DEBUG=valor).DEBUG is esperado


class TestConfiguracaoModoDemonstracao:
    def test_modo_desligado_sem_a_chave(self, monkeypatch) -> None:
        """Sem MODO_DEMONSTRACAO no ambiente, o modo fica desligado."""
        assert _carregar_settings(monkeypatch).MODO_DEMONSTRACAO is False

    @pytest.mark.parametrize("valor", ["True", "true", "TRUE"])
    def test_modo_ligado_com_true(self, monkeypatch, valor: str) -> None:
        """'true' liga o modo sem diferenciar maiúsculas, como o DEBUG."""
        modulo = _carregar_settings(monkeypatch, MODO_DEMONSTRACAO=valor)
        assert modulo.MODO_DEMONSTRACAO is True

    @pytest.mark.parametrize("valor", ["sim", "1", "False", ""])
    def test_modo_desligado_com_outro_valor(self, monkeypatch, valor: str) -> None:
        """Qualquer valor que não seja 'true' deixa o modo desligado."""
        modulo = _carregar_settings(monkeypatch, MODO_DEMONSTRACAO=valor)
        assert modulo.MODO_DEMONSTRACAO is False

    def test_console_em_desenvolvimento_sem_email_user(self, monkeypatch) -> None:
        """Com DEBUG e sem EMAIL_USER, o e-mail sai no terminal, com remetente fictício."""
        modulo = _carregar_settings(monkeypatch, DEBUG="True")
        assert modulo.MAILERS == {
            "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}
        }
        assert modulo.ENDERECO_CONTATO == "contato@example.com"
        assert modulo.DEFAULT_FROM_EMAIL == "Projeto Portfólio <contato@example.com>"

    def test_smtp_em_desenvolvimento_com_email_user(self, monkeypatch) -> None:
        """Com EMAIL_USER preenchido, o desenvolvimento usa o SMTP de verdade."""
        modulo = _carregar_settings(
            monkeypatch,
            DEBUG="True",
            EMAIL_USER="conta@example.com",
            EMAIL_PASS="senha-de-app",
        )
        mailer = modulo.MAILERS["default"]
        assert mailer["BACKEND"] == "django.core.mail.backends.smtp.EmailBackend"
        assert mailer["OPTIONS"] == {
            "host": "smtp.gmail.com",
            "port": 587,
            "use_tls": True,
            "username": "conta@example.com",
            "password": "senha-de-app",
        }
        assert modulo.ENDERECO_CONTATO == "conta@example.com"
        assert modulo.DEFAULT_FROM_EMAIL == "Projeto Portfólio <conta@example.com>"

    def test_smtp_em_producao_sem_email_user(self, monkeypatch) -> None:
        """Em produção, EMAIL_USER vazio segue no SMTP: o envio falha à vista."""
        modulo = _carregar_settings(monkeypatch, DEBUG="False")
        mailer = modulo.MAILERS["default"]
        assert mailer["BACKEND"] == "django.core.mail.backends.smtp.EmailBackend"
        assert modulo.ENDERECO_CONTATO is None

    def test_settings_sem_os_email_depreciados(self, monkeypatch) -> None:
        """Nenhum EMAIL_* depreciado volta ao settings (o Django 6.1 usa MAILERS)."""
        modulo = _carregar_settings(monkeypatch, DEBUG="False")
        assert [nome for nome in vars(modulo) if nome.startswith("EMAIL_")] == []


# ---------------------------------------------------------------------------
# Configuração de produção: hosts, dados, proxy e log (spec 006)
# ---------------------------------------------------------------------------


class TestConfiguracaoProducao:
    def test_allowed_hosts_sem_espacos_nem_item_vazio(self, monkeypatch) -> None:
        """Espaços e a vírgula no fim saem da lista (RF-04)."""
        modulo = _carregar_settings(
            monkeypatch,
            DEBUG="False",
            ALLOWED_HOSTS="exemplo.com, www.exemplo.com,",
        )
        assert modulo.ALLOWED_HOSTS == ["exemplo.com", "www.exemplo.com"]

    @pytest.mark.parametrize("ambiente", [{}, {"ALLOWED_HOSTS": ""}])
    def test_allowed_hosts_vazio_recusa_todo_host(
        self, monkeypatch, ambiente: dict[str, str]
    ) -> None:
        """Sem a variável, ou com ela vazia, a lista fica vazia: falha fechada."""
        modulo = _carregar_settings(monkeypatch, DEBUG="False", **ambiente)
        assert modulo.ALLOWED_HOSTS == []

    def test_allowed_hosts_aceita_tudo_em_desenvolvimento(self, monkeypatch) -> None:
        """Com DEBUG, qualquer host passa, como antes."""
        modulo = _carregar_settings(monkeypatch, DEBUG="True")
        assert modulo.ALLOWED_HOSTS == ["*"]

    def test_dados_na_raiz_sem_diretorio_dados(self, monkeypatch) -> None:
        """Sem DIRETORIO_DADOS, banco, mídia e cache ficam onde sempre ficaram."""
        modulo = _carregar_settings(monkeypatch)
        raiz = modulo.BASE_DIR
        assert modulo.DATABASES["default"]["NAME"] == raiz / "db.sqlite3"
        assert modulo.MEDIA_ROOT == raiz / "media"
        assert modulo.CACHES["default"]["LOCATION"] == raiz / "django_cache"

    def test_dados_no_caminho_absoluto(self, monkeypatch, tmp_path: Path) -> None:
        """Um caminho absoluto (o volume da plataforma) recebe os três."""
        modulo = _carregar_settings(monkeypatch, DIRETORIO_DADOS=str(tmp_path))
        assert modulo.DATABASES["default"]["NAME"] == tmp_path / "db.sqlite3"
        assert modulo.MEDIA_ROOT == tmp_path / "media"
        assert modulo.CACHES["default"]["LOCATION"] == tmp_path / "django_cache"

    def test_dados_no_caminho_relativo(self, monkeypatch) -> None:
        """Um caminho relativo parte da raiz do repositório."""
        modulo = _carregar_settings(monkeypatch, DIRETORIO_DADOS="dados")
        pasta = modulo.BASE_DIR / "dados"
        assert modulo.DATABASES["default"]["NAME"] == pasta / "db.sqlite3"
        assert modulo.MEDIA_ROOT == pasta / "media"
        assert modulo.CACHES["default"]["LOCATION"] == pasta / "django_cache"

    def test_https_e_hsts_em_producao(self, monkeypatch) -> None:
        """Com DEBUG=False: redirect e cookies só em HTTPS, e HSTS de um ano."""
        modulo = _carregar_settings(monkeypatch, DEBUG="False")
        assert modulo.SECURE_SSL_REDIRECT is True
        assert modulo.SESSION_COOKIE_SECURE is True
        assert modulo.CSRF_COOKIE_SECURE is True
        assert modulo.SECURE_HSTS_SECONDS == 31536000
        assert modulo.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert modulo.SECURE_HSTS_PRELOAD is True

    def test_proxy_e_log_em_producao(self, monkeypatch) -> None:
        """Com DEBUG=False: cabeçalho do proxy lido e erros na saída de erro (RF-02, RF-07)."""
        modulo = _carregar_settings(monkeypatch, DEBUG="False")
        assert modulo.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        log = modulo.LOGGING
        assert log["disable_existing_loggers"] is False
        assert log["handlers"]["console"]["class"] == "logging.StreamHandler"
        assert log["root"] == {"handlers": ["console"], "level": "WARNING"}
        # O 404 sai como WARNING no django.request; ERROR deixa passar só o 500.
        assert log["loggers"]["django.request"]["level"] == "ERROR"

    def test_sem_proxy_nem_log_em_desenvolvimento(self, monkeypatch) -> None:
        """Com DEBUG=True, nada muda no runserver."""
        modulo = _carregar_settings(monkeypatch, DEBUG="True")
        # O controle positivo é o test_proxy_e_log_em_producao, com os mesmos nomes.
        for nome in ("SECURE_PROXY_SSL_HEADER", "LOGGING", "SECURE_SSL_REDIRECT"):
            assert not hasattr(modulo, nome), nome


# ---------------------------------------------------------------------------
# Caminho do painel administrativo (spec 003)
# ---------------------------------------------------------------------------


class TestCaminhoDoAdmin:
    def test_sem_a_variavel_fica_em_admin(self, monkeypatch) -> None:
        """Ausente, o painel fica no caminho padrão do Django (RF-06)."""
        assert _carregar_settings(monkeypatch).ADMIN_URL_PATH == "admin/"

    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            ("", "admin/"),
            ("  ", "admin/"),
            ("/", "admin/"),
            ("painel-secreto/", "painel-secreto/"),
            ("painel-secreto", "painel-secreto/"),
            ("/painel-secreto/", "painel-secreto/"),
            (" painel-secreto/ ", "painel-secreto/"),
        ],
    )
    def test_normaliza_e_nunca_fica_vazio(
        self, monkeypatch, valor: str, esperado: str
    ) -> None:
        """Vazio poria o painel na raiz, no lugar da página inicial (RF-06)."""
        modulo = _carregar_settings(monkeypatch, ADMIN_URL=valor)
        assert modulo.ADMIN_URL_PATH == esperado

    def test_painel_responde_no_caminho_configurado(self, settings) -> None:
        """
        A rota do painel vem do ADMIN_URL_PATH, sem caminho fixo no urls.py.

        O caminho de teste difere do padrão ``admin/``: com o valor padrão, um
        ``path("admin/", ...)`` fixo também passaria. O ``urls.py`` lê o setting na
        importação, então o módulo é recarregado com o valor trocado e de novo no fim.
        """
        original = settings.ADMIN_URL_PATH
        settings.ADMIN_URL_PATH = "painel-de-teste/"
        rotas = importlib.reload(importlib.import_module("portfolio.urls"))
        clear_url_caches()
        try:
            assert reverse("admin:index") == "/painel-de-teste/"
        finally:
            settings.ADMIN_URL_PATH = original
            importlib.reload(rotas)
            clear_url_caches()


# Domínio público da demo nos testes de proxy. O navegador sempre manda o Host, e
# o proxy o preserva; sem ele, o test client monta "testserver:80", que não bate
# com a origem https://testserver.
_HOST_PUBLICO = "demo.example.com"


@pytest.mark.django_db
class TestHttpsAtrasDoProxy:
    @pytest.fixture(autouse=True)
    def producao_atras_do_proxy(self, settings) -> None:
        """Liga o redirect, os cookies seguros e a leitura do cabeçalho do proxy."""
        settings.ALLOWED_HOSTS = [_HOST_PUBLICO]
        settings.SECURE_SSL_REDIRECT = True
        settings.SESSION_COOKIE_SECURE = True
        settings.CSRF_COOKIE_SECURE = True
        settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    def test_https_pelo_proxy_responde_sem_redirect(self, client) -> None:
        """Com X-Forwarded-Proto: https, a página abre e o cookie CSRF é Secure (RF-02)."""
        response = client.get(
            reverse("home"), HTTP_HOST=_HOST_PUBLICO, HTTP_X_FORWARDED_PROTO="https"
        )
        assert response.status_code == 200
        assert response.cookies["csrftoken"]["secure"] is True

    @pytest.mark.parametrize("cabecalho", [{}, {"HTTP_X_FORWARDED_PROTO": "http"}])
    def test_http_redireciona_para_https(
        self, client, cabecalho: dict[str, str]
    ) -> None:
        """Sem o cabeçalho, ou com http, segue o 301 para HTTPS."""
        response = client.get(reverse("home"), HTTP_HOST=_HOST_PUBLICO, **cabecalho)
        assert response.status_code == 301
        assert response["Location"] == f"https://{_HOST_PUBLICO}/"

    def _post_com_origem(self, origem: str) -> "_MonkeyPatchedWSGIResponse":
        """
        Envia o formulário pelo proxy, com o token CSRF do cookie e a origem dada.

        O formulário vai inválido: a view responde 400 sem gravar nem enviar.

        Args:
            origem (str): Valor do cabeçalho ``Origin``.

        Returns:
            _MonkeyPatchedWSGIResponse: A resposta do POST, com os templates usados.
        """
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(
            reverse("home"), HTTP_HOST=_HOST_PUBLICO, HTTP_X_FORWARDED_PROTO="https"
        )
        token = cliente.cookies["csrftoken"].value
        return cliente.post(
            reverse("home"),
            {"csrfmiddlewaretoken": token, "honeypot": ""},
            HTTP_HOST=_HOST_PUBLICO,
            HTTP_X_FORWARDED_PROTO="https",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ORIGIN=origem,
        )

    def test_post_com_origem_do_site_passa_pelo_csrf(self) -> None:
        """Origin igual a https://<host> passa sem CSRF_TRUSTED_ORIGINS (RF-03, ADR-04)."""
        response = self._post_com_origem(f"https://{_HOST_PUBLICO}")
        assert response.status_code == 400
        assert MensagemContato.objects.count() == 0

    def test_post_com_origem_de_fora_da_403(self) -> None:
        """Origin de outro site: 403, com a página de falha de CSRF."""
        response = self._post_com_origem("https://outro-site.example")
        assert response.status_code == 403
        assert "403_csrf.html" in [t.name for t in response.templates]


# ---------------------------------------------------------------------------
# Segurança do formulário de contato
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSegurancaContato:
    def test_contato_xss_sanitization(self, client) -> None:
        """
        Verifica se a sanitização (Bleach) está removendo tags maliciosas <script>
        antes de salvar a mensagem no banco de dados.
        """
        url = reverse("home")
        data = {
            "nome": "Hacker",
            "email": "hacker@evil.com",
            "assunto": "Ataque",
            "mensagem": '<script>alert("xss")</script>Olá',
            "honeypot": "",
        }
        client.post(url, data, follow=True)

        msg = MensagemContato.objects.get()
        # O texto exato: escapar no lugar de tirar (&lt;script&gt;) também passaria
        # num "<script> not in".
        assert msg.mensagem == 'alert("xss")Olá'

    def test_rate_limit_blocking(self, client) -> None:
        """
        Valida o sistema de bloqueio. O primeiro envio deve passar,
        o segundo (imediato) deve retornar uma mensagem de erro/aguarde.
        """
        url = reverse("home")
        data = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }

        primeira = client.post(url, data, follow=True)  # Primeiro envio: Sucesso
        segunda = client.post(url, data, follow=True)  # Segundo envio: Bloqueio

        assert [a.message for a in primeira.context["messages"]] == [MENSAGEM_ENVIADO]
        assert [a.message for a in segunda.context["messages"]] == [
            MENSAGEM_LIMITE_ENVIO
        ]
        assert segunda.redirect_chain == [(reverse("home"), 302)]
        # O bloqueio para antes de gravar e de enviar: só o primeiro chegou.
        assert MensagemContato.objects.count() == 1
        assert len(mail.outbox) == 1

    def test_reserva_e_por_ip_e_dura_dez_minutos(self, client, monkeypatch) -> None:
        """A vaga reservada leva o IP de quem enviou e vale 600 segundos."""
        add_original = CacheArquivoAtomico.add
        reservas: list[tuple[Any, Any, Any]] = []

        def espiao(
            self: CacheArquivoAtomico,
            key: Any,
            value: Any,
            timeout: Any = DEFAULT_TIMEOUT,
            version: Any = None,
        ) -> bool:
            """Anota a reserva pedida e repassa ao add() de verdade."""
            reservas.append((key, value, timeout))
            return add_original(self, key, value, timeout, version)

        monkeypatch.setattr(CacheArquivoAtomico, "add", espiao)
        cabecalhos = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        dados = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }

        primeiro = client.post(
            reverse("home"), dados, REMOTE_ADDR="10.0.0.1", **cabecalhos
        )
        outro_ip = client.post(
            reverse("home"), dados, REMOTE_ADDR="10.0.0.2", **cabecalhos
        )

        assert reservas == [
            ("contact_limit_10.0.0.1", True, 600),
            ("contact_limit_10.0.0.2", True, 600),
        ]
        assert (primeiro.status_code, outro_ip.status_code) == (200, 200)

    def test_contato_honeypot_bot_protection(self, client) -> None:
        """
        Simula um robô preenchendo o campo 'honeypot' (que deveria estar vazio).
        O sistema deve ignorar o envio e não salvar nada no banco.
        """
        url = reverse("home")
        data = {
            "nome": "Bot",
            "email": "b@b.com",
            "assunto": "S",
            "mensagem": "A",
            "honeypot": "Sou robô",
        }
        response = client.post(url, data)
        assert response.status_code == 302  # Redirecionamento (Ignorado)
        assert MensagemContato.objects.count() == 0  # Nada foi salvo

    def test_contato_envia_email_com_sucesso(self, client) -> None:
        """Um envio válido gera um e-mail, da conta para ela mesma, com os dados."""
        url = reverse("home")
        data = {
            "nome": "Ana",
            "email": "ana@example.com",
            "assunto": "Orçamento",
            "mensagem": "Olá",
            "honeypot": "",
        }

        client.post(url, data, follow=True)

        (email,) = mail.outbox
        assert email.subject == "Novo Contato: Orçamento"
        assert email.body == (
            "Mensagem de: Ana\nE-mail: ana@example.com\n\nConteúdo:\nOlá"
        )
        assert email.from_email == "contato-teste@example.com"
        assert email.to == ["contato-teste@example.com"]

    def test_contato_ajax_sucesso_retorna_json(self, client) -> None:
        """Requisição AJAX bem-sucedida retorna JSON (não redirect) com status 200."""
        url = reverse("home")
        data = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }

        response = client.post(url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_contato_ajax_bloqueio_retorna_429(self, client) -> None:
        """Segundo envio AJAX dentro da janela de rate limit retorna HTTP 429."""
        url = reverse("home")
        data = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

        client.post(url, data, **headers)
        response = client.post(url, data, **headers)

        assert response.status_code == 429
        assert response.json() == {"status": "error", "message": MENSAGEM_LIMITE_ENVIO}
        assert MensagemContato.objects.count() == 1
        assert len(mail.outbox) == 1

    def test_contato_erro_envio_email(self, client, caplog) -> None:
        """Falha no SMTP não derruba a request; AJAX recebe 500 com JSON de erro."""
        url = reverse("home")
        data = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }

        # Mockado no ponto de uso (app_portfolio.views), não em django.core.mail.
        with patch(
            "app_portfolio.views.send_mail", side_effect=Exception("SMTP indisponível")
        ):
            response = client.post(url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        assert response.status_code == 500
        assert response.json() == {"status": "error", "message": MENSAGEM_FALHA_ENVIO}
        # A mensagem já estava no banco, e a falha vai para o log com o traceback.
        assert MensagemContato.objects.count() == 1
        (registro,) = [r for r in caplog.records if r.name == "app_portfolio.views"]
        assert registro.levelname == "ERROR"
        assert registro.getMessage() == "Falha ao enviar e-mail de contato"
        assert registro.exc_info is not None

    def test_contato_erro_envio_email_sem_ajax_mostra_o_aviso(self, client) -> None:
        """Sem JavaScript, a página volta com o aviso de falha, sem redirect."""
        dados = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }
        with patch(
            "app_portfolio.views.send_mail", side_effect=Exception("SMTP indisponível")
        ):
            response = client.post(reverse("home"), dados)

        assert response.status_code == 200
        assert [a.message for a in response.context["messages"]] == [
            MENSAGEM_FALHA_ENVIO
        ]

    def test_contato_ajax_dados_invalidos_retorna_400(self, client) -> None:
        """Formulário inválido (e-mail malformado) via AJAX retorna HTTP 400."""
        url = reverse("home")
        data = {
            "nome": "U",
            "email": "nao-e-email",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }

        response = client.post(url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        assert response.status_code == 400
        assert response.json()["status"] == "error"


# ---------------------------------------------------------------------------
# Reserva atômica do rate limit (cache em arquivo)
# ---------------------------------------------------------------------------


class TestCacheArquivoAtomico:
    def test_settings_usa_cache_atomico(self) -> None:
        """O cache padrão é o backend com trava, não o FileBasedCache puro."""
        # caches[...] devolve o backend; o `cache` importado é um proxy dele.
        assert isinstance(caches["default"], CacheArquivoAtomico)

    def test_add_concorrente_reserva_uma_vez(self, tmp_path: Path) -> None:
        """
        Vinte threads liberadas juntas pedem a mesma chave: só uma reserva.

        Com o add() do FileBasedCache puro, todas veem a chave ausente e
        todas reservam.
        """
        cache_teste = CacheArquivoAtomico(str(tmp_path), {})
        total = 20
        largada = threading.Barrier(total)
        resultados: list[bool] = []

        def reservar() -> None:
            largada.wait()
            resultados.append(cache_teste.add("contact_limit_ip", True, 600))

        threads = [threading.Thread(target=reservar) for _ in range(total)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert resultados.count(True) == 1

    def test_add_depois_de_expirar_reserva_de_novo(self, tmp_path: Path) -> None:
        """Reserva vencida não bloqueia: o add() seguinte volta a gravar."""
        cache_teste = CacheArquivoAtomico(str(tmp_path), {})

        # timeout=0 grava já vencido (o Django converte em validade passada).
        assert cache_teste.add("contact_limit_ip", True, 0) is True
        assert cache_teste.add("contact_limit_ip", True, 600) is True
        assert cache_teste.add("contact_limit_ip", True, 600) is False

    def test_add_recria_a_pasta_apagada(self, tmp_path: Path) -> None:
        """A pasta do cache apagada depois da subida é recriada na reserva."""
        pasta = tmp_path / "cache"
        cache_teste = CacheArquivoAtomico(str(pasta), {})
        shutil.rmtree(pasta, ignore_errors=True)
        assert not pasta.exists()

        assert cache_teste.add("contact_limit_ip", True, 600) is True
        assert cache_teste.get("contact_limit_ip") is True

    def test_add_respeita_a_versao(self, tmp_path: Path) -> None:
        """A versão da chave chega ao add() herdado: outra versão é outra vaga."""
        cache_teste = CacheArquivoAtomico(str(tmp_path), {})

        assert cache_teste.add("contact_limit_ip", "v2", 600, version=2) is True
        assert cache_teste.add("contact_limit_ip", "v1", 600) is True
        assert cache_teste.get("contact_limit_ip", version=2) == "v2"
        assert cache_teste.get("contact_limit_ip") == "v1"


# ---------------------------------------------------------------------------
# Upload do currículo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCurriculo:
    def test_curriculo_recusa_arquivo_que_nao_e_pdf(self) -> None:
        """Um .html no currículo seria servido como página pelo próprio domínio."""
        perfil = Perfil(
            nome="Pessoa",
            cargo="Dev",
            curriculo=SimpleUploadedFile("cv.html", b"<p>oi</p>"),
        )

        with pytest.raises(ValidationError) as erro:
            perfil.full_clean()

        assert "curriculo" in erro.value.message_dict

    def test_curriculo_aceita_pdf(self) -> None:
        perfil = Perfil(
            nome="Pessoa",
            cargo="Dev",
            curriculo=SimpleUploadedFile("cv.pdf", b"%PDF-1.7"),
        )

        perfil.full_clean()


# ---------------------------------------------------------------------------
# Modo demonstração do formulário de contato (spec 005)
# ---------------------------------------------------------------------------

# Envio que passa na validação: com o modo ligado, tem de ser aceito sem gravar
# nem enviar nada.
_ENVIO_VALIDO = {
    "nome": "U",
    "email": "u@t.com",
    "assunto": "O",
    "mensagem": "M",
    "honeypot": "",
}


@pytest.mark.django_db
class TestModoDemonstracao:
    @pytest.fixture(autouse=True)
    def modo_ligado(self, settings) -> None:
        """Liga o modo demonstração em todos os testes deste grupo."""
        settings.MODO_DEMONSTRACAO = True

    def test_ajax_valido_responde_demo_sem_gravar_nem_enviar(
        self, client, settings
    ) -> None:
        """AJAX válido: 200 com status demo e o link, sem banco, e-mail nem cache."""
        response = client.post(
            reverse("home"), _ENVIO_VALIDO, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "demo",
            "message": MENSAGEM_DEMONSTRACAO,
            "link": {
                "texto": TEXTO_LINK_DEMONSTRACAO,
                "url": settings.URL_REPOSITORIO,
            },
        }
        assert MensagemContato.objects.count() == 0
        assert mail.outbox == []
        assert cache.get("contact_limit_127.0.0.1") is None

    def test_post_comum_valido_redireciona_com_aviso_info(self, client) -> None:
        """Sem JavaScript: redirect e mensagem info marcada com 'demo'."""
        response = client.post(reverse("home"), _ENVIO_VALIDO, follow=True)

        avisos = list(response.context["messages"])
        assert response.redirect_chain == [(reverse("home"), 302)]
        assert len(avisos) == 1
        assert avisos[0].level_tag == "info"
        assert "demo" in avisos[0].extra_tags
        assert avisos[0].message == MENSAGEM_DEMONSTRACAO
        assert MensagemContato.objects.count() == 0
        assert mail.outbox == []

    def test_honeypot_segue_com_redirect_silencioso(self, client) -> None:
        """Honeypot preenchido: redirect sem aviso, como no fluxo normal."""
        dados = {**_ENVIO_VALIDO, "honeypot": "Sou robô"}
        response = client.post(reverse("home"), dados, follow=True)

        assert list(response.context["messages"]) == []
        assert MENSAGEM_DEMONSTRACAO not in response.content.decode("utf-8")

    def test_formulario_invalido_segue_com_400(self, client) -> None:
        """Validação continua valendo: e-mail malformado responde 400 no AJAX."""
        dados = {**_ENVIO_VALIDO, "email": "nao-e-email"}
        response = client.post(
            reverse("home"), dados, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        assert response.status_code == 400
        assert response.json() == {
            "status": "error",
            "message": MENSAGEM_DADOS_INVALIDOS,
        }

    def test_dois_envios_seguidos_respondem_demo(self, client) -> None:
        """Sem rate limit no modo: o visitante pode testar de novo na hora."""
        cabecalho = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        primeira = client.post(reverse("home"), _ENVIO_VALIDO, **cabecalho)
        segunda = client.post(reverse("home"), _ENVIO_VALIDO, **cabecalho)

        assert primeira.json()["status"] == "demo"
        assert segunda.json()["status"] == "demo"

    def test_modo_desligado_grava_e_envia(self, client, settings) -> None:
        """Com o modo desligado, o envio grava, manda o e-mail e responde success."""
        settings.MODO_DEMONSTRACAO = False
        response = client.post(
            reverse("home"), _ENVIO_VALIDO, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        assert response.json() == {"status": "success", "message": MENSAGEM_ENVIADO}
        assert MensagemContato.objects.count() == 1
        assert len(mail.outbox) == 1


# ---------------------------------------------------------------------------
# Mídia servida com DEBUG=False (spec 006)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestServirMidia:
    @pytest.fixture(autouse=True)
    def pasta_de_midia(self, settings, tmp_path: Path) -> Path:
        """
        Põe uma imagem e uma subpasta no ``MEDIA_ROOT`` temporário.

        Args:
            settings: Fixture do pytest-django.
            tmp_path (Path): Pasta temporária do teste.

        Returns:
            Path: A pasta de mídia, com ``foto.webp`` e ``projetos/``.
        """
        midia = tmp_path / "midia"
        (midia / "projetos").mkdir(parents=True)
        (midia / "foto.webp").write_bytes(b"RIFF0000WEBP")
        settings.MEDIA_ROOT = midia
        return midia

    def test_arquivo_existente(self, client) -> None:
        """200 com o tipo do arquivo, nosniff e cache de um dia (RF-06)."""
        response = client.get("/media/foto.webp")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/webp"
        assert response["X-Content-Type-Options"] == "nosniff"
        diretivas = sorted(d.strip() for d in response["Cache-Control"].split(","))
        assert diretivas == ["max-age=86400", "public"]
        assert b"".join(response.streaming_content) == b"RIFF0000WEBP"

    @pytest.mark.parametrize(
        "caminho",
        ["/media/nao-existe.webp", "/media/projetos/", "/media/../segredo.txt"],
    )
    def test_inexistente_pasta_e_fuga_dao_404(
        self, client, caminho: str, pasta_de_midia: Path
    ) -> None:
        """Arquivo que falta, pasta e ../ respondem 404 com a página de erro."""
        # O alvo do ../ existe, logo acima do MEDIA_ROOT: o 404 vem da recusa da
        # fuga, não de o arquivo faltar.
        (pasta_de_midia.parent / "segredo.txt").write_text("fora da mídia")
        response = client.get(caminho)
        assert response.status_code == 404
        assert "404.html" in [t.name for t in response.templates]

    def test_post_da_405(self, client) -> None:
        """Só GET e HEAD: o resto recebe 405."""
        assert client.post("/media/foto.webp").status_code == 405


# ---------------------------------------------------------------------------
# Receita de build da plataforma (spec 006)
# ---------------------------------------------------------------------------


class TestReceitaDeBuild:
    @pytest.fixture
    def receita(self) -> dict[str, Any]:
        """
        Lê o ``railpack.json`` da raiz do repositório.

        Returns:
            dict[str, Any]: O arquivo como JSON.
        """
        caminho = Path(__file__).resolve().parent.parent / "railpack.json"
        conteudo: dict[str, Any] = json.loads(caminho.read_text(encoding="utf-8"))
        return conteudo

    def test_build_instala_pelo_lock_e_coleta_estaticos(self, receita) -> None:
        """O build confere o lock, instala o extra prod e roda o collectstatic (RF-01)."""
        comandos = receita["steps"]["build"]["commands"]
        assert comandos[0] == "uv sync --locked --no-dev --extra prod"
        assert any("collectstatic --noinput" in comando for comando in comandos)

    def test_start_migra_antes_do_gunicorn_na_porta(self, receita) -> None:
        """O migrate roda antes do gunicorn, ligado por &&, na porta de PORT."""
        start = receita["deploy"]["startCommand"]
        assert start.index("migrate --noinput") < start.index("&& gunicorn")
        assert "--bind 0.0.0.0:${PORT:-8000}" in start


# ---------------------------------------------------------------------------
# Conversão de imagem para WebP
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConverterParaWebp:
    def test_save_converte_imagem_para_webp(self) -> None:
        """Upload de PNG é convertido para .webp na sobrescrita de save() do model."""
        projeto = Projeto.objects.create(
            titulo="Projeto Teste", descricao="Desc", imagem=_uploaded_png()
        )
        assert projeto.imagem.name == "projetos/teste.webp"
        assert _formato_e_modo(projeto.imagem) == ("WEBP", "RGB")

    def test_save_preserva_a_transparencia(self) -> None:
        """PNG com canal alfa vira WebP com alfa (RGBA), não RGB com fundo preto."""
        projeto = Projeto.objects.create(
            titulo="Com alfa", descricao="Desc", imagem=_uploaded_png(modo="RGBA")
        )
        assert _formato_e_modo(projeto.imagem) == ("WEBP", "RGBA")

    def test_save_nao_reconverte_webp(self) -> None:
        """Um WebP enviado é gravado como veio, sem perder qualidade ao recomprimir."""
        enviado = _uploaded_webp()
        projeto = Projeto.objects.create(
            titulo="Já WebP", descricao="Desc", imagem=enviado
        )
        with projeto.imagem.open("rb") as gravado:
            assert gravado.read() == enviado.open().read()

    def test_save_do_perfil_converte_a_foto(self) -> None:
        """A foto do Perfil passa pela mesma conversão do projeto."""
        perfil = Perfil.objects.create(
            nome="Ana", cargo="Dev", foto=_uploaded_png("foto.png")
        )
        assert perfil.foto.name.endswith(".webp")
        assert _formato_e_modo(perfil.foto) == ("WEBP", "RGB")

    @pytest.mark.parametrize(
        ("modelo", "campo", "pasta"),
        [(Projeto, "imagem", "projetos"), (Perfil, "foto", "perfil")],
    )
    def test_imagem_ja_gravada_fica_na_pasta_do_upload_to(
        self, modelo: Any, campo: str, pasta: str
    ) -> None:
        """
        A imagem já gravada não ganha a pasta do ``upload_to`` duas vezes.

        O nome da imagem gravada por ``FieldFile.save()`` já traz o ``upload_to``; a
        conversão o passa de novo ao storage, que acrescenta a pasta outra vez se o nome
        não for só o do arquivo.
        """
        dados = (
            {"titulo": "Semeado", "descricao": "Desc"}
            if modelo is Projeto
            else {"nome": "Ana", "cargo": "Dev"}
        )
        registro = modelo(**dados)
        arquivo = getattr(registro, campo)
        arquivo.save("semeado.png", _uploaded_png("semeado.png"))

        assert getattr(registro, campo).name == f"{pasta}/semeado.webp"
        assert _formato_e_modo(getattr(registro, campo)) == ("WEBP", "RGB")

    @pytest.mark.parametrize(
        ("modelo", "campo", "pasta"),
        [(Projeto, "imagem", "projetos"), (Perfil, "foto", "perfil")],
    )
    def test_imagem_ja_gravada_nao_deixa_o_original(
        self, modelo: Any, campo: str, pasta: str, settings
    ) -> None:
        """Convertida a imagem já gravada, só o WebP fica na pasta do storage."""
        registro = modelo(**_dados_minimos(modelo))
        getattr(registro, campo).save("semeado.png", _uploaded_png("semeado.png"))

        assert _arquivos_em(Path(settings.MEDIA_ROOT) / pasta) == ["semeado.webp"]

    def test_webp_salvo_de_novo_nao_apaga_nada(self, settings) -> None:
        """Controle: sem conversão, salvar de novo deixa a foto onde estava."""
        perfil = Perfil.objects.create(nome="Ana", cargo="Dev", foto=_uploaded_webp())
        perfil.refresh_from_db()

        perfil.save()

        assert perfil.foto.name == "perfil/teste.webp"
        assert _arquivos_em(Path(settings.MEDIA_ROOT) / "perfil") == ["teste.webp"]

    def test_falha_ao_gravar_no_banco_mantem_o_original(
        self, settings, monkeypatch
    ) -> None:
        """
        O original só sai depois do registro gravado no banco.

        Se a gravação falha, o banco segue apontando para o original: apagá-lo antes
        deixaria o registro com uma imagem que não existe mais.
        """
        projeto = Projeto.objects.create(titulo="Semeado", descricao="Desc")
        Projeto.objects.filter(pk=projeto.pk).update(imagem="projetos/antiga.png")
        pasta = Path(settings.MEDIA_ROOT) / "projetos"
        pasta.mkdir(parents=True)
        (pasta / "antiga.png").write_bytes(_uploaded_png().read())
        projeto.refresh_from_db()

        def falhar(*args: Any, **kwargs: Any) -> None:
            """Simula a falha na gravação do registro."""
            raise DatabaseError("banco indisponível")

        monkeypatch.setattr(models.Model, "save", falhar)
        with pytest.raises(DatabaseError, match="banco indisponível"):
            projeto.save()

        # O WebP novo sobra (o storage já o gravou); o original fica no lugar.
        assert "antiga.png" in _arquivos_em(pasta)

    def test_save_sem_imagem_nao_falha(self) -> None:
        """Projeto sem imagem (campo opcional) salva normalmente, sem conversão."""
        projeto = Projeto.objects.create(titulo="Sem Imagem", descricao="Desc")
        assert not projeto.imagem

    def test_imagem_ja_gravada_so_com_arquivo_no_storage(self) -> None:
        """Campo vazio e envio ainda não gravado não contam; imagem gravada conta."""
        vazio = Projeto(titulo="Vazio", descricao="Desc")
        enviado = Projeto(titulo="Enviado", descricao="Desc", imagem=_uploaded_png())
        gravado = Projeto.objects.create(
            titulo="Gravado", descricao="Desc", imagem=_uploaded_png()
        )
        gravado.refresh_from_db()

        assert [
            imagem_ja_gravada(registro.imagem) for registro in (vazio, enviado, gravado)
        ] == [False, False, True]


# ---------------------------------------------------------------------------
# Nome de cada registro no Admin
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_str_de_cada_model() -> None:
    """O Admin lista cada registro pelo texto do ``__str__``."""
    tecnologia = Tecnologia.objects.create(nome="Python")
    categoria_projeto = CategoriaProjeto.objects.create(nome="Web", slug="web")
    projeto = Projeto.objects.create(titulo="Portfólio", descricao="Desc")
    perfil = Perfil.objects.create(nome="Ana", cargo="Dev")
    grupo = CategoriaHabilidade.objects.create(nome="Back-end")
    habilidade = Habilidade.objects.create(categoria=grupo, nome="Django")
    mensagem = MensagemContato.objects.create(
        nome="Bia", email="bia@example.com", assunto="Oi", mensagem="Olá"
    )

    assert [
        str(registro)
        for registro in (
            tecnologia,
            categoria_projeto,
            projeto,
            perfil,
            grupo,
            habilidade,
            mensagem,
        )
    ] == [
        "Python",
        "Web",
        "Portfólio",
        "Ana",
        "Back-end",
        "Django (Back-end)",
        "Bia - Oi",
    ]
