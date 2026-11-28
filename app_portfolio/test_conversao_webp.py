"""
Testes de que a conversão para WebP fecha o arquivo que abre para ler.

O ``converter_para_webp`` abre o arquivo do ImageField para descobrir o formato.
Quando a imagem já está gravada no storage (o ``save()`` que um ``FieldFile.save()``
dispara, como no comando de demonstração, ou o Perfil salvo de novo no Admin com a
mesma foto), o arquivo aberto ficava sem dono e só fechava na coleta de lixo, com um
``ResourceWarning``.

Estratégia de isolamento: o ``MEDIA_ROOT`` vai para a pasta temporária do teste. Os
avisos são gravados por ``warnings.catch_warnings`` com o ``gc.collect()`` antes da
conferência, e um controle positivo confirma que a gravação acusa um arquivo
esquecido.
"""

import gc
import io
import warnings
from collections.abc import Callable
from pathlib import Path

import pytest
from django.conf import LazySettings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from app_portfolio.models import Perfil, Projeto

# ---------------------------------------------------------------------------
# Fixtures e auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def media_root_tmp(settings: LazySettings, tmp_path: Path) -> None:
    """
    Grava as imagens na pasta temporária, nunca na ``media/`` do projeto.

    Args:
        settings (LazySettings): Fixture do pytest-django.
        tmp_path (Path): Pasta temporária do teste.
    """
    settings.MEDIA_ROOT = str(tmp_path)


def _png() -> bytes:
    """
    Gera um PNG 1x1 em memória.

    Returns:
        bytes: O conteúdo do arquivo.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


def _avisos_de_recurso(acao: Callable[[], object]) -> list[str]:
    """
    Roda a ação e devolve os ``ResourceWarning`` que ela deixou.

    Args:
        acao (Callable[[], object]): O que rodar.

    Returns:
        list[str]: A mensagem de cada aviso, como ``unclosed file <...>``.
    """
    # O que um teste anterior largou é coletado antes, fora da gravação.
    gc.collect()
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always", ResourceWarning)
        acao()
        gc.collect()
    return [str(a.message) for a in avisos if issubclass(a.category, ResourceWarning)]


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_o_registro_acusa_um_arquivo_esquecido(tmp_path: Path) -> None:
    """Controle positivo: um arquivo aberto e largado aparece na lista."""
    caminho = tmp_path / "esquecido.txt"
    caminho.write_text("x", encoding="utf-8")

    def esquecer() -> None:
        caminho.open("rb")

    assert len(_avisos_de_recurso(esquecer)) == 1


@pytest.mark.django_db
def test_imagem_ja_gravada_fecha_o_arquivo_na_conversao() -> None:
    """O ``FieldFile.save()`` grava o PNG, e a conversão não o larga aberto."""
    projeto = Projeto(titulo="Semeado", descricao="Desc")

    avisos = _avisos_de_recurso(
        lambda: projeto.imagem.save("semeado.png", ContentFile(_png()))
    )

    assert avisos == []
    # A conversão rodou de fato: sem ela não haveria arquivo a fechar.
    assert projeto.imagem.name == "projetos/semeado.webp"


@pytest.mark.django_db
def test_foto_webp_salva_de_novo_fecha_o_arquivo() -> None:
    """Salvar o Perfil com a foto de antes lê o formato e fecha o arquivo."""
    upload = SimpleUploadedFile("foto.png", _png(), content_type="image/png")
    perfil = Perfil.objects.create(nome="Ana", cargo="Dev", foto=upload)
    perfil.refresh_from_db()
    nome = perfil.foto.name or ""
    assert nome.endswith(".webp")
    # Controle: a foto gravada ainda não foi aberta por ninguém.
    assert perfil.foto.closed

    perfil.save()

    # O arquivo aberto fica preso à instância, então o aviso só sairia quando ela
    # fosse coletada: o estado do arquivo é conferido direto.
    assert perfil.foto.closed
    assert perfil.foto.name == nome
