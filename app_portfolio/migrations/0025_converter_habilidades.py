"""
Converte o progresso de 0 a 100 das habilidades em nível e liga cada uma à
tecnologia de mesmo nome (spec 008, RF-20 e ADR-03).

Roda entre a ``0024``, que cria ``nivel`` e ``tecnologia``, e a ``0026``, que
remove o ``progresso``: o valor antigo ainda existe quando esta migração o lê.
O caminho de volta grava um progresso aproximado por nível (90, 65 e 30).
"""

from typing import Any

from django.db import migrations

# Limites da conversão (RF-20): 80 ou mais é uso diário; de 50 a 79, já usado
# em projeto; abaixo de 50, ainda em estudo.
LIMITE_DIA_A_DIA = 80
LIMITE_JA_USEI = 50

# Progresso gravado na volta: o meio de cada faixa, porque o valor exato se
# perdeu na ida.
PROGRESSO_POR_NIVEL = {"dia_a_dia": 90, "ja_usei": 65, "estudando": 30}


def nivel_pelo_progresso(progresso: int) -> str:
    """
    Traduz o progresso antigo no nível de três degraus.

    Args:
        progresso (int): O valor de 0 a 100 do campo antigo.

    Returns:
        str: ``"dia_a_dia"``, ``"ja_usei"`` ou ``"estudando"``.
    """
    if progresso >= LIMITE_DIA_A_DIA:
        return "dia_a_dia"
    if progresso >= LIMITE_JA_USEI:
        return "ja_usei"
    return "estudando"


def converter_habilidades(apps: Any, schema_editor: Any) -> None:
    """
    Preenche ``nivel`` e ``tecnologia`` de cada habilidade existente.

    A tecnologia é a de mesmo nome, sem diferença de maiúsculas; com duas de
    mesmo nome, vale a primeira por ``ordem``. A que não casar fica sem ligação
    até ser ligada no Admin.

    Args:
        apps (Any): O registro de modelos históricos da migração.
        schema_editor (Any): O editor de esquema do banco (não usado).
    """
    Habilidade = apps.get_model("app_portfolio", "Habilidade")
    Tecnologia = apps.get_model("app_portfolio", "Tecnologia")

    for habilidade in Habilidade.objects.all():
        habilidade.nivel = nivel_pelo_progresso(habilidade.progresso)
        habilidade.tecnologia = (
            Tecnologia.objects.filter(nome__iexact=habilidade.nome)
            .order_by("ordem", "pk")
            .first()
        )
        habilidade.save(update_fields=["nivel", "tecnologia"])


def desfazer_conversao(apps: Any, schema_editor: Any) -> None:
    """
    Devolve um progresso aproximado a partir do nível (caminho de volta).

    Args:
        apps (Any): O registro de modelos históricos da migração.
        schema_editor (Any): O editor de esquema do banco (não usado).
    """
    Habilidade = apps.get_model("app_portfolio", "Habilidade")

    for habilidade in Habilidade.objects.all():
        habilidade.progresso = PROGRESSO_POR_NIVEL.get(habilidade.nivel, 30)
        habilidade.save(update_fields=["progresso"])


class Migration(migrations.Migration):
    """Converte progresso em nível e liga habilidade à tecnologia."""

    dependencies = [
        ("app_portfolio", "0024_campos_do_redesenho"),
    ]

    operations = [
        migrations.RunPython(converter_habilidades, desfazer_conversao),
    ]
