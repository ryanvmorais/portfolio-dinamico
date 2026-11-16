"""
Testes da home, do formulário de contato e da conversão de imagem.

Cobrem o status e o número de consultas da página, a segurança do envio
(XSS, honeypot, limite por IP, falha de e-mail) e a conversão para WebP no
``save()`` dos models.

Estratégia de isolamento: nenhuma chamada de rede real é feita durante a
suíte, e nenhum teste depende do conteúdo do `.env` local. `settings.EMAIL_BACKEND`
é trocado para o backend em memória do Django e `settings.EMAIL_HOST_USER` é
fixado num valor de teste (`disable_real_email`, abaixo) — sem isso, os testes
que passam pelo fluxo de POST do formulário de contato disparariam
`send_mail()` contra o SMTP real do Gmail configurado em `settings.py` usando
a credencial real do `.env` de quem estiver rodando a suíte, tornando os
testes lentos, dependentes de rede, capazes de enviar e-mails de verdade, e
dependentes de uma variável de ambiente que não existe em CI. A falha de
envio (`test_contato_erro_envio_email`) mocka `views.send_mail` diretamente,
no ponto de uso. O modo demonstração (spec 005) começa desligado em cada teste
(`modo_demonstracao_desligado`), e a leitura das chaves do `settings.py` roda
numa cópia avulsa do módulo, com o ambiente controlado (`_carregar_settings`).
"""

import importlib.util
import io
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import dotenv
import pytest
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from app_portfolio.models import MensagemContato, Perfil, Projeto
from app_portfolio.views import (
    MENSAGEM_DADOS_INVALIDOS,
    MENSAGEM_DEMONSTRACAO,
    MENSAGEM_ENVIADO,
    TEXTO_LINK_DEMONSTRACAO,
)

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

    Troca `EMAIL_BACKEND` para o backend em memória do Django — sem isso,
    `views.home()` chamaria `send_mail()` contra o SMTP real do Gmail
    (host/porta fixos em `settings.py`) a cada POST de contato bem-sucedido.

    Também fixa `EMAIL_HOST_USER` num valor de teste: sem isso, a suíte
    herdaria o valor de `EMAIL_USER` do `.env` local (via `load_dotenv` em
    `settings.py`). Isso mascarava um bug — a suíte só passava na máquina de
    quem tinha um `.env` com credencial real preenchida, e falhava em CI (sem
    `.env`, `EMAIL_HOST_USER=None`), onde `send_mail()` com remetente/
    destinatário `None` não gera entrada em `mail.outbox`.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.EMAIL_HOST_USER = "contato-teste@example.com"


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


def _uploaded_png(nome: str = "teste.png") -> SimpleUploadedFile:
    """
    Gera um PNG 1x1 válido em memória para testar upload de imagem.

    Evita depender de um arquivo fixture versionado no repositório.

    Args:
        nome (str, optional): Nome do arquivo simulado. Padrão: "teste.png".

    Returns:
        SimpleUploadedFile: Arquivo pronto para atribuir a um ImageField.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), color="red").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(nome, buffer.read(), content_type="image/png")


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
    for nome in ("DEBUG", "MODO_DEMONSTRACAO", "EMAIL_USER", "EMAIL_PASS"):
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

    def test_home_query_count(self, client, django_assert_max_num_queries) -> None:
        """
        Garante que a página inicial não ultrapasse 10 consultas ao banco.

        Um select_related/prefetch_related a menos na view faria o número
        crescer com a quantidade de projetos (N+1).
        """
        with django_assert_max_num_queries(10):
            client.get(reverse("home"))

    def test_estaticos_usam_o_storage_comprimido_do_whitenoise(self, settings) -> None:
        """O storage dos estáticos vem de STORAGES (o STATICFILES_STORAGE é ignorado)."""
        backend = settings.STORAGES["staticfiles"]["BACKEND"]
        assert backend == "whitenoise.storage.CompressedStaticFilesStorage"
        assert settings.STORAGES["default"]["BACKEND"].endswith("FileSystemStorage")


# ---------------------------------------------------------------------------
# Configuração do modo demonstração e do e-mail (spec 005)
# ---------------------------------------------------------------------------


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
        assert modulo.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
        assert modulo.EMAIL_HOST_USER == "contato@example.com"
        assert "contato@example.com" in modulo.DEFAULT_FROM_EMAIL

    def test_smtp_em_desenvolvimento_com_email_user(self, monkeypatch) -> None:
        """Com EMAIL_USER preenchido, o desenvolvimento usa o SMTP de verdade."""
        modulo = _carregar_settings(
            monkeypatch, DEBUG="True", EMAIL_USER="conta@example.com"
        )
        assert modulo.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        assert modulo.EMAIL_HOST_USER == "conta@example.com"

    def test_smtp_em_producao_sem_email_user(self, monkeypatch) -> None:
        """Em produção, EMAIL_USER vazio segue no SMTP: o envio falha à vista."""
        modulo = _carregar_settings(monkeypatch, DEBUG="False")
        assert modulo.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        assert modulo.EMAIL_HOST_USER is None


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

        msg = MensagemContato.objects.last()
        assert msg is not None
        assert "<script>" not in msg.mensagem  # O script deve ter sido removido

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

        client.post(url, data, follow=True)  # Primeiro envio: Sucesso
        response = client.post(url, data, follow=True)  # Segundo envio: Bloqueio

        conteudo = response.content.decode("utf-8")
        assert "recentemente" in conteudo or "aguarde" in conteudo

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
        """Um envio válido deve gerar exatamente um e-mail na caixa de saída."""
        url = reverse("home")
        data = {
            "nome": "U",
            "email": "u@t.com",
            "assunto": "O",
            "mensagem": "M",
            "honeypot": "",
        }

        client.post(url, data, follow=True)

        assert len(mail.outbox) == 1
        assert "O" in mail.outbox[0].subject

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

    def test_contato_erro_envio_email(self, client) -> None:
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
        assert response.json()["status"] == "error"

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
# Conversão de imagem para WebP
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConverterParaWebp:
    def test_save_converte_imagem_para_webp(self) -> None:
        """Upload de PNG é convertido para .webp na sobrescrita de save() do model."""
        projeto = Projeto.objects.create(
            titulo="Projeto Teste", descricao="Desc", imagem=_uploaded_png()
        )
        assert projeto.imagem.name.endswith(".webp")

    def test_save_sem_imagem_nao_falha(self) -> None:
        """Projeto sem imagem (campo opcional) salva normalmente, sem conversão."""
        projeto = Projeto.objects.create(titulo="Sem Imagem", descricao="Desc")
        assert not projeto.imagem
