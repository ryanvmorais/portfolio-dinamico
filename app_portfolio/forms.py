"""
Formulário de contato da home.

Um ``ModelForm`` sobre ``MensagemContato``: os campos e as validações vêm do
model, então mudar o model atualiza o formulário sem duplicar regra.
"""

from django import forms

from .models import MensagemContato


class MensagemContatoForm(forms.ModelForm):
    """
    Formulário responsável por capturar mensagens na Home.

    Herda as regras de validação definidas no modelo MensagemContato.
    """

    class Meta:
        model = MensagemContato

        # Lista explícita em vez de "__all__": um campo novo no model (como a
        # data de envio) não vira campo editável pelo visitante sem querer.
        fields = ["nome", "email", "assunto", "mensagem"]
