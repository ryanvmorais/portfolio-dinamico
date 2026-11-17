"""
Painel administrativo do portfólio.

Todo o conteúdo do site (perfil, projetos, tecnologias e habilidades) é
editado aqui, sem deploy. As mensagens de contato entram
somente leitura: o painel serve para lê-las, não para alterá-las.
"""

from django.contrib import admin

from .models import (
    CategoriaHabilidade,
    CategoriaProjeto,
    Habilidade,
    MensagemContato,
    Perfil,
    Projeto,
    Tecnologia,
)

# ---------------------------------------------------------------------------
# Conteúdo da vitrine
# ---------------------------------------------------------------------------


@admin.register(Tecnologia)
class TecnologiaAdmin(admin.ModelAdmin):
    """Gerencia as tecnologias dos projetos, que as habilidades ligam (spec 008)."""

    list_display = ("nome", "ordem")
    list_editable = ("ordem",)  # Permite editar sem abrir o item
    # Também habilita a busca do autocomplete_fields do HabilidadeInline.
    search_fields = ("nome",)


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    """Configura a vitrine de projetos com filtros por tecnologia."""

    list_display = ("titulo", "categoria_projeto", "ordem")
    list_editable = ("ordem",)
    list_filter = ("categoria_projeto", "tecnologias")
    search_fields = ("titulo", "descricao")

    # Organiza o formulário em blocos visuais (Fieldsets)
    fieldsets = (
        (
            "Informações do Projeto",
            {"fields": ("titulo", "descricao", "categoria_projeto", "imagem", "ordem")},
        ),
        ("Tecnologias Utilizadas", {"fields": ("tecnologias",)}),
        ("Links e Repositórios", {"fields": ("link_github", "link_online")}),
        (
            "Estudo de caso",
            {
                # Recolhido: os quatro campos são opcionais, e o cartão só
                # mostra o "Como foi feito" quando algum tem texto.
                "classes": ("collapse",),
                "fields": ("problema", "papel", "decisao_tecnica", "resultado"),
            },
        ),
    )

    # Interface amigável para selecionar múltiplas tecnologias (Many-to-Many)
    filter_horizontal = ("tecnologias",)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    """Centraliza as informações do dono do portfólio."""

    list_display = ("nome", "cargo", "status_trabalho")

    fieldsets = (
        (
            "Informações Básicas",
            {"fields": ("nome", "cargo", "bio_curta", "foto", "curriculo")},
        ),
        ("Sobre Mim", {"fields": ("bio", "anos_experiencia")}),
        (
            "Detalhes de Contato e Formação",
            {
                "fields": (
                    "email_contato",
                    "localizacao",
                    "status_trabalho",
                    "formacao",
                    "link_linkedin",
                    "link_github",
                )
            },
        ),
    )


# ---------------------------------------------------------------------------
# Mensagens de contato
# ---------------------------------------------------------------------------


@admin.register(MensagemContato)
class MensagemContatoAdmin(admin.ModelAdmin):
    """
    Gerencia os contatos recebidos.

    Todos os campos são somente leitura: a mensagem fica como o visitante a
    enviou.
    """

    list_display = ("nome", "email", "assunto", "data_envio")
    list_display_links = ("nome", "email")

    ordering = ("-data_envio",)  # Mostra as mensagens mais recentes primeiro
    list_filter = ("data_envio",)

    readonly_fields = ("nome", "email", "assunto", "mensagem", "data_envio")
    search_fields = ("nome", "email", "assunto", "mensagem")


# ---------------------------------------------------------------------------
# Habilidades e categorias
# ---------------------------------------------------------------------------


class HabilidadeInline(admin.TabularInline):
    """Permite adicionar habilidades diretamente dentro da categoria."""

    model = Habilidade
    extra = 1  # Define quantos campos vazios aparecem por padrão
    fields = ("nome", "nivel", "tecnologia")
    # Busca em vez de lista suspensa; o TecnologiaAdmin já tem search_fields.
    autocomplete_fields = ("tecnologia",)


@admin.register(CategoriaHabilidade)
class CategoriaHabilidadeAdmin(admin.ModelAdmin):
    """Agrupa habilidades por categoria, com edição em massa via inline."""

    list_display = ("nome",)
    inlines = [HabilidadeInline]  # Ativa a edição em massa de habilidades


@admin.register(CategoriaProjeto)
class CategoriaProjetoAdmin(admin.ModelAdmin):
    """Gerencia as categorias de projeto; o slug é preenchido a partir do nome."""

    list_display = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}
