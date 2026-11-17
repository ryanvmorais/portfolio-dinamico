"""
Models do portfólio: o conteúdo da página e as mensagens de contato.

Tecnologias e categorias classificam os projetos; perfil e habilidades formam
a apresentação (os números da página são contados dos dados, spec 008);
``MensagemContato`` guarda o que chega pelo formulário. As imagens enviadas são convertidas para WebP ao salvar
(``utils.converter_para_webp``).
"""

from typing import Any

from django.core.validators import FileExtensionValidator, MaxLengthValidator
from django.db import models

from .utils import converter_para_webp

# ---------------------------------------------------------------------------
# Tecnologias e categorias de projeto
# ---------------------------------------------------------------------------


class Tecnologia(models.Model):
    """
    Representa as ferramentas (Python, Django, etc).

    Marca os projetos e, ligada a uma ``Habilidade``, conta os projetos que a
    provam e alimenta o filtro por chip da home (spec 008).
    """

    nome = models.CharField(max_length=50)
    ordem = models.PositiveIntegerField(
        default=0, help_text="Quanto menor o número, primeiro ele aparece"
    )

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Tecnologia"
        verbose_name_plural = "Tecnologias"

    def __str__(self) -> str:
        """Returns: str: O nome da tecnologia."""
        return self.nome


class CategoriaProjeto(models.Model):
    """Define os tipos de projeto (Web, Mobile, Data Science)."""

    nome = models.CharField(max_length=50)
    # O Slug é uma versão amigável da URL (ex: 'web-development')
    slug = models.SlugField(
        unique=True, help_text="Nome usado no filtro (ex: web, api, mobile)"
    )

    class Meta:
        verbose_name = "Categoria de Projeto"
        verbose_name_plural = "Categorias de Projetos"

    def __str__(self) -> str:
        """Returns: str: O nome da categoria."""
        return self.nome


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------


class Projeto(models.Model):
    """
    O modelo principal que une Categoria, Texto e Tecnologias.
    Demonstra relacionamentos ForeignKey, ManyToMany e processamento de imagem com Pillow.
    """

    # ForeignKey: Um projeto tem UMA categoria (Um-para-Muitos)
    categoria_projeto = models.ForeignKey(
        CategoriaProjeto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos",
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(
        help_text="Mantenha por volta de 170 caracteres para simetria"
    )
    imagem = models.ImageField(
        upload_to="projetos/",
        null=True,
        blank=True,
        help_text="Upload em JPG ou PNG. O sistema converterá para WebP automaticamente para performance.",
    )

    # ManyToMany: Um projeto usa várias tecnologias, e uma tecnologia está em vários projetos.
    tecnologias = models.ManyToManyField(Tecnologia)

    link_github = models.URLField(blank=True, null=True)
    link_online = models.URLField(
        blank=True,
        null=True,
        verbose_name="Versão no ar",
        help_text=(
            "Endereço onde o projeto pode ser usado; vazio, o cartão não mostra o link."
        ),
    )
    ordem = models.IntegerField(default=0)

    # Estudo de caso: quatro títulos fixos mantêm os cartões comparáveis
    # (ADR-05 da spec 008). O max_length do TextField só limita o formulário
    # do Admin, não o banco.
    problema = models.TextField(
        blank=True,
        max_length=600,
        help_text="Que problema o projeto resolve, e para quem.",
    )
    papel = models.TextField(
        blank=True,
        max_length=600,
        verbose_name="Meu papel",
        help_text="O que você fez: sozinho, em equipe, qual parte.",
    )
    decisao_tecnica = models.TextField(
        blank=True,
        max_length=600,
        verbose_name="Decisão técnica",
        help_text="A escolha que mais pesou e por quê.",
    )
    resultado = models.TextField(
        blank=True,
        max_length=600,
        help_text="O que mudou depois: número, uso real ou o que você aprendeu.",
    )

    class Meta:
        ordering = ["ordem"]
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"

    def __str__(self) -> str:
        """Returns: str: O título do projeto."""
        return self.titulo

    @property
    def tem_estudo_de_caso(self) -> bool:
        """
        Diz se algum dos quatro campos do estudo de caso tem texto.

        Returns:
            bool: ``True`` quando o cartão deve mostrar o "Como foi feito".
        """
        return any(
            campo.strip()
            for campo in (
                self.problema,
                self.papel,
                self.decisao_tecnica,
                self.resultado,
            )
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Sobrescrita do save utilizando a função utilitária global.

        Mantém o DRY (Don't Repeat Yourself) e a performance.

        Args:
            *args (Any): Argumentos posicionais repassados ao ``super().save()``.
            **kwargs (Any): Argumentos nomeados repassados ao ``super().save()``.
        """
        # Chamada da função modularizada em utils.py
        novo_conteudo, novo_nome = converter_para_webp(self.imagem)

        if novo_conteudo and novo_nome:
            self.imagem.save(novo_nome, novo_conteudo, save=False)

        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------


class Perfil(models.Model):
    """
    Armazena todos os dados do desenvolvedor.
    Centraliza informações que mudam pouco (Nome, Bio, Links).
    """

    nome = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100)
    foto = models.ImageField(
        upload_to="perfil/",
        null=True,
        blank=True,
        help_text=(
            "Sua foto de apresentação: retrato vertical 4:5 (ex.: 960 x 1200) com "
            "espaço acima da cabeça, porque o celular a mostra num círculo. Será "
            "convertida para WebP para agilizar o carregamento da Home."
        ),
    )
    bio = models.TextField(blank=True, null=True)
    bio_curta = models.CharField(max_length=255, blank=True, null=True)
    anos_experiencia = models.IntegerField(
        default=0,
        help_text="Aparece no hero e no selo da foto do Sobre; zero esconde o número.",
    )
    email_contato = models.EmailField(max_length=255, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    localizacao = models.CharField(max_length=100, blank=True, null=True)
    status_trabalho = models.CharField(max_length=100, blank=True, null=True)
    formacao = models.CharField(max_length=100, blank=True, null=True)
    # Só PDF: a mídia é servida pelo próprio domínio, com o Content-Type tirado
    # da extensão; um .html ou .svg enviado aqui seria aberto como página.
    curriculo = models.FileField(
        upload_to="curriculo/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["pdf"])],
        help_text="Arquivo PDF.",
    )
    link_linkedin = models.URLField(blank=True, null=True)
    link_github = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self) -> str:
        """Returns: str: O nome do desenvolvedor."""
        return self.nome

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Garante que a foto de perfil seja sempre leve.

        Impacta positivamente na pontuação de performance do site.

        Args:
            *args (Any): Argumentos posicionais repassados ao ``super().save()``.
            **kwargs (Any): Argumentos nomeados repassados ao ``super().save()``.
        """
        novo_conteudo, novo_nome = converter_para_webp(self.foto)

        if novo_conteudo and novo_nome:
            self.foto.save(novo_nome, novo_conteudo, save=False)

        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Habilidades
# ---------------------------------------------------------------------------


class CategoriaHabilidade(models.Model):
    """Organiza habilidades em grupos (Backend, UI/UX, etc)."""

    nome = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Categoria de Habilidade"
        verbose_name_plural = "Categorias de Habilidades"

    def __str__(self) -> str:
        """Returns: str: O nome da categoria de habilidade."""
        return self.nome


class NivelHabilidade(models.TextChoices):
    """
    Os três degraus de domínio de uma habilidade (ADR-02 da spec 008).

    A ordem dos membros é a ordem de exibição na home.

    Attributes:
        DIA_A_DIA (str): O que a pessoa usa hoje.
        JA_USEI (str): O que já usou em algum projeto.
        ESTUDANDO (str): O que está aprendendo.
    """

    DIA_A_DIA = "dia_a_dia", "Uso no dia a dia"
    JA_USEI = "ja_usei", "Já usei em projeto"
    ESTUDANDO = "estudando", "Estudando"


class Habilidade(models.Model):
    """
    Habilidades individuais ligadas a uma categoria.

    A ligação opcional com uma ``Tecnologia`` conta os projetos que provam a
    habilidade (ADR-01 da spec 008).
    """

    categoria = models.ForeignKey(
        CategoriaHabilidade, on_delete=models.CASCADE, related_name="habilidades"
    )
    nome = models.CharField(max_length=50)
    nivel = models.CharField(
        max_length=10,
        choices=NivelHabilidade,
        default=NivelHabilidade.DIA_A_DIA,
        help_text="Agrupa a habilidade na home; nível sem habilidade não aparece.",
    )
    tecnologia = models.ForeignKey(
        Tecnologia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="habilidades",
        help_text=(
            "A tecnologia dos projetos que provam esta habilidade; ligada, o chip "
            "mostra quantos projetos a usam e filtra a lista."
        ),
    )

    def __str__(self) -> str:
        """Returns: str: Formato "nome (categoria)"."""
        return f"{self.nome} ({self.categoria.nome})"


# ---------------------------------------------------------------------------
# Mensagens de contato
# ---------------------------------------------------------------------------


class MensagemContato(models.Model):
    """Registra as tentativas de contato feitas pelo site."""

    nome = models.CharField(max_length=100)
    email = models.EmailField()
    assunto = models.CharField(max_length=200)
    mensagem = models.TextField(validators=[MaxLengthValidator(5000)])
    data_envio = models.DateTimeField(
        auto_now_add=True
    )  # Data gerada automaticamente no envio
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ["-data_envio"]
        verbose_name = "Mensagem de Contato"
        verbose_name_plural = "Mensagens de Contato"

    def __str__(self) -> str:
        """Returns: str: Formato "nome - assunto"."""
        return f"{self.nome} - {self.assunto}"
