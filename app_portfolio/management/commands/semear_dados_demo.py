"""
Preenche o banco com dados fictícios, para desenvolver e auditar a Home.

Um banco vazio devolve uma Home sem projetos nem habilidades, e as métricas do
Lighthouse ficam enganosas. O Lighthouse CI
(``.github/workflows/lighthouse.yml``) roda este comando antes de subir o servidor.

O comando é idempotente (rodar duas vezes não duplica nada), recusa rodar com
``DEBUG=False`` (são dados de mentira, nunca de produção) e gera as imagens com o
Pillow, para o CI não depender de rede nem de arquivos no repositório.

Uso::

    uv run python manage.py semear_dados_demo
"""

from __future__ import annotations

import io
from typing import Any, NamedTuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageOps

from app_portfolio.models import (
    CategoriaHabilidade,
    CategoriaProjeto,
    Habilidade,
    NivelHabilidade,
    Perfil,
    Projeto,
    Tecnologia,
)

# --- 1. DADOS DE DEMONSTRAÇÃO ---

# Paleta (topo, base) dos gradientes que fazem as vezes de foto. Geradas aqui, com o
# Pillow, para o comando não depender de rede (o Lighthouse CI roda isolado).
CORES = [
    ("#2563eb", "#0f172a"),
    ("#0d9488", "#042f2e"),
    ("#9333ea", "#1e1b4b"),
]

# A ordem da lista vira o campo ``ordem``: é a ordem das tags dentro de cada card.
TECNOLOGIAS = [
    "Python",
    "Django",
    "FastAPI",
    "PostgreSQL",
    "Redis",
    "TypeScript",
    "React",
    "React Native",
    "Vue.js",
    "Tailwind CSS",
    "Firebase",
    "Docker",
    "Nginx",
    "GitHub Actions",
    "AWS",
]

# (nome, slug): o slug é o que os projetos abaixo usam para escolher a categoria.
# Dois projetos por categoria, para cada filtro mostrar o mesmo número (RF-30).
CATEGORIAS_PROJETO = [("Web App", "web-app"), ("API", "api"), ("Mobile", "mobile")]


class ProjetoDemo(NamedTuple):
    """
    Um projeto fictício, com tudo o que o card da home mostra (spec 008, RF-30).

    Attributes:
        titulo (str): Título do card.
        categoria (str): Slug de uma das ``CATEGORIAS_PROJETO``.
        endereco (str): Trecho final do link "Ver online" (no example.com) e do
            repositório.
        descricao (str): Resumo de cerca de 165 caracteres, para os cards empatarem.
        tecnologias (tuple[str, ...]): Cinco nomes de ``TECNOLOGIAS``.
        problema (str): Campo "Problema" do estudo de caso.
        papel (str): Campo "Meu papel" do estudo de caso.
        decisao_tecnica (str): Campo "Decisão técnica" do estudo de caso.
        resultado (str): Campo "Resultado" do estudo de caso.
    """

    titulo: str
    categoria: str
    endereco: str
    descricao: str
    tecnologias: tuple[str, ...]
    problema: str
    papel: str
    decisao_tecnica: str
    resultado: str


# Cinco tecnologias por projeto, distribuídas para a contagem dos chips descer de
# nível para nível (quatro a dois no dia a dia, um em "já usei") e as tags caberem
# em duas linhas a partir de 360 px (ADR-14). Cada estudo de caso cita só as
# tecnologias do próprio projeto. Os endereços usam o example.com, domínio
# reservado para exemplos (RFC 2606).
PROJETOS = [
    ProjetoDemo(
        titulo="Plataforma de E-commerce",
        categoria="web-app",
        endereco="plataforma-de-e-commerce",
        descricao="Sistema de vendas online com pagamentos integrados, controle de "
        "estoque e painel de controle interno. Solução escalável focada em "
        "conversão e segurança dos usuários.",
        tecnologias=("Python", "Django", "PostgreSQL", "TypeScript", "React"),
        problema="Lojistas pequenos vendiam pelo Instagram e perdiam pedidos por "
        "não ter estoque nem pagamento integrados.",
        papel="Projeto solo: modelagem do banco, carrinho, integração de pagamento "
        "e o painel do lojista.",
        decisao_tecnica="Django com PostgreSQL e o Admin como painel interno, para "
        "entregar o MVP sem escrever um back-office.",
        resultado="Loja-piloto no ar em seis semanas, com checkout em três passos e "
        "estoque baixado a cada venda.",
    ),
    ProjetoDemo(
        titulo="API de Gestão Financeira",
        categoria="api",
        endereco="api-de-gestao-financeira",
        descricao="Interface RESTful para controle financeiro com login JWT e "
        "Swagger. Estrutura robusta para processamento de transações e relatórios "
        "detalhados com máxima segurança.",
        tecnologias=("Python", "PostgreSQL", "Redis", "Nginx", "GitHub Actions"),
        problema="Um app de finanças pessoais precisava de um back-end seguro para "
        "contas, lançamentos e relatórios.",
        papel="Projeto solo: desenho da API REST, autenticação por token, testes "
        "automatizados e documentação.",
        decisao_tecnica="Redis guarda os relatórios já calculados; o PostgreSQL só "
        "refaz a conta quando entra um lançamento.",
        resultado="Documentação interativa no Swagger, e cada pull request passa por "
        "testes e lint no CI antes do merge.",
    ),
    ProjetoDemo(
        titulo="Dashboard de Analytics",
        categoria="web-app",
        endereco="dashboard-de-analytics",
        descricao="Painel de análise de dados em tempo real com gráficos interativos "
        "e relatórios automatizados. Construído com foco em UX para garantir "
        "clareza e agilidade operacional.",
        tecnologias=("Django", "PostgreSQL", "TypeScript", "Vue.js", "Docker"),
        problema="A equipe de vendas montava relatórios à mão em planilhas e só via "
        "os números no fim do mês.",
        papel="Em dupla: fiquei com o back-end, a agregação dos dados e o deploy; a "
        "outra pessoa fez a interface.",
        decisao_tecnica="Agregar os dados em tabelas-resumo de hora em hora, para os "
        "gráficos abrirem sem pesar no banco.",
        resultado="O relatório mensal virou um painel diário, que se atualiza "
        "sozinho, sem planilha no meio.",
    ),
    ProjetoDemo(
        titulo="App de Gestão de Tarefas",
        categoria="mobile",
        endereco="app-de-gestao-de-tarefas",
        descricao="Aplicativo completo para organização de tarefas com nuvem e modo "
        "offline. Interface intuitiva com alertas inteligentes para otimizar a "
        "produtividade no dia a dia.",
        tecnologias=("TypeScript", "React Native", "Tailwind CSS", "Firebase", "AWS"),
        problema="Quem trabalha em campo perdia tarefas anotadas no papel e ficava "
        "sem a lista quando o sinal caía.",
        papel="Projeto solo: telas, sincronização com a nuvem, notificações e a "
        "publicação nas lojas de apps.",
        decisao_tecnica="Firebase com cache local: o app funciona sem internet e "
        "sincroniza sozinho quando a conexão volta.",
        resultado="A lista fica disponível offline, e os lembretes chegam na hora "
        "certa mesmo com o app fechado.",
    ),
    ProjetoDemo(
        titulo="Rede Social para Devs",
        categoria="mobile",
        endereco="rede-social-para-devs",
        descricao="Aplicativo de interação para programadores com foco em networking "
        "e artigos. Espaço ideal para divulgar portfólios e colaborar em projetos "
        "de código aberto ativos.",
        tecnologias=("Python", "Django", "React Native", "Tailwind CSS", "Docker"),
        problema="Devs iniciantes não tinham onde mostrar projetos e trocar revisão "
        "de código com gente mais experiente.",
        papel="Equipe de três: fiz a API em Django e o feed do app; design e "
        "moderação ficaram com os colegas.",
        decisao_tecnica="Feed paginado por cursor, para a rolagem seguir leve mesmo "
        "com milhares de publicações.",
        resultado="Testado com uma turma de bootcamp, que trocou revisões de código "
        "já na primeira semana.",
    ),
    ProjetoDemo(
        titulo="Serviço de Chatbot com IA",
        categoria="api",
        endereco="servico-de-chatbot-com-ia",
        descricao="Chatbot inteligente com processamento de linguagem natural e "
        "múltiplas integrações. Atendimento automatizado eficiente para otimizar o "
        "suporte e a experiência final.",
        tecnologias=("Python", "FastAPI", "Docker", "Nginx", "GitHub Actions"),
        problema="O suporte respondia as mesmas dúvidas o dia inteiro, e o cliente "
        "esperava horas por uma resposta simples.",
        papel="Projeto solo: API de conversa, integração com o modelo de linguagem e "
        "histórico de atendimentos.",
        decisao_tecnica="FastAPI, por ser assíncrono: o serviço espera a resposta do "
        "modelo sem travar as outras conversas.",
        resultado="As dúvidas repetidas passaram a ter resposta na hora; o time "
        "ficou com os casos que pedem uma pessoa.",
    ),
]

# Categoria de habilidade -> (habilidade, nível): seis por categoria, na proporção
# 3, 2 e 1 (RF-31), e no dia a dia da mais usada para a menos usada. A habilidade
# se liga à tecnologia de mesmo nome (spec 008, RF-12); as de "estudando" não têm
# tecnologia nos projetos e ficam como chips sem contagem.
HABILIDADES = {
    "Back-end": [
        ("Python", NivelHabilidade.DIA_A_DIA),
        ("Django", NivelHabilidade.DIA_A_DIA),
        ("PostgreSQL", NivelHabilidade.DIA_A_DIA),
        ("FastAPI", NivelHabilidade.JA_USEI),
        ("Redis", NivelHabilidade.JA_USEI),
        ("Go", NivelHabilidade.ESTUDANDO),
    ],
    "Front-end": [
        ("TypeScript", NivelHabilidade.DIA_A_DIA),
        ("React Native", NivelHabilidade.DIA_A_DIA),
        ("Tailwind CSS", NivelHabilidade.DIA_A_DIA),
        ("React", NivelHabilidade.JA_USEI),
        ("Vue.js", NivelHabilidade.JA_USEI),
        ("Svelte", NivelHabilidade.ESTUDANDO),
    ],
    "DevOps e ferramentas": [
        ("Docker", NivelHabilidade.DIA_A_DIA),
        ("GitHub Actions", NivelHabilidade.DIA_A_DIA),
        ("Nginx", NivelHabilidade.DIA_A_DIA),
        ("AWS", NivelHabilidade.JA_USEI),
        ("Firebase", NivelHabilidade.JA_USEI),
        ("Kubernetes", NivelHabilidade.ESTUDANDO),
    ],
}


class Command(BaseCommand):
    """
    Cria perfil, projetos, tecnologias e habilidades de demonstração.

    Idempotente e restrito a ``DEBUG=True``; ver a docstring do módulo.

    Uso::

        uv run python manage.py semear_dados_demo
    """

    help = "Cria dados de demonstração (só com DEBUG=True) para auditorias e testes."

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Cria cada grupo de dados e informa o total ao final.

        Fluxo:
            1. Recusa rodar se ``DEBUG`` estiver desligado.
            2. Cria o perfil, se ainda não houver um.
            3. Cria as tecnologias e os projetos com imagem e estudo de caso.
            4. Cria as habilidades, ligadas às tecnologias.
            5. Imprime o total de projetos e habilidades.

        Args:
            *args (Any): Argumentos posicionais (não utilizados).
            **options (Any): Argumentos nomeados do parser (não utilizados).

        Raises:
            CommandError: Se ``settings.DEBUG`` for falso.
        """
        if not settings.DEBUG:
            raise CommandError(
                "semear_dados_demo só roda com DEBUG=True: são dados de "
                "demonstração, nunca de produção."
            )

        self._perfil()
        tecnologias = self._tecnologias()
        self._projetos(tecnologias)
        self._habilidades(tecnologias)
        self.stdout.write(
            self.style.SUCCESS(
                f"Dados de demonstração prontos: {Projeto.objects.count()} projetos, "
                f"{Habilidade.objects.count()} habilidades."
            )
        )

    # --- 2. UTILITÁRIOS ---

    @staticmethod
    def _imagem(
        nome: str, largura: int, altura: int, indice: int
    ) -> ContentFile[bytes]:
        """
        Gera um gradiente JPEG para usar como imagem de um ``ImageField``.

        Os modelos convertem para WebP no ``save()``, como com um upload real.

        Args:
            nome (str): Nome do arquivo.
            largura (int): Largura em pixels.
            altura (int): Altura em pixels.
            indice (int): Posição na paleta ``CORES`` (dá a volta ao passar do fim).

        Returns:
            ContentFile[bytes]: Arquivo em memória, pronto para atribuir ao campo.
        """
        topo, base = CORES[indice % len(CORES)]
        gradiente = Image.linear_gradient("L").resize((largura, altura))
        imagem = ImageOps.colorize(gradiente, black=base, white=topo)
        buffer = io.BytesIO()
        imagem.save(buffer, format="JPEG", quality=80)
        return ContentFile(buffer.getvalue(), name=nome)

    # --- 3. CRIAÇÃO DOS DADOS ---

    def _perfil(self) -> None:
        """Cria o perfil (nome, contatos e foto) se ainda não houver um."""
        if Perfil.objects.exists():
            return
        perfil = Perfil.objects.create(
            nome="Maria Souza",
            cargo="Desenvolvedora Full Stack",
            bio="Desenvolvo aplicações web do banco de dados à interface.\n\n"
            "Gosto de código simples, testado e bem documentado.",
            bio_curta="Aplicações web do banco de dados à interface.",
            anos_experiencia=5,
            email_contato="maria@example.com",
            localizacao="São Paulo, Brasil",
            status_trabalho="Disponível para projetos",
            formacao="Análise e Desenvolvimento de Sistemas",
            link_linkedin="https://www.linkedin.com/in/maria-souza-demo",
            link_github="https://github.com/maria-souza-demo",
        )
        perfil.foto.save(
            "demo-perfil.jpg", self._imagem("demo-perfil.jpg", 800, 800, 0)
        )

    @staticmethod
    def _tecnologias() -> list[Tecnologia]:
        """
        Cria as tecnologias dos projetos.

        Returns:
            list[Tecnologia]: As tecnologias, na ordem de ``TECNOLOGIAS``.
        """
        return [
            Tecnologia.objects.get_or_create(nome=nome, defaults={"ordem": ordem})[0]
            for ordem, nome in enumerate(TECNOLOGIAS)
        ]

    def _projetos(self, tecnologias: list[Tecnologia]) -> None:
        """
        Cria as categorias de projeto e os projetos com imagem, tecnologias,
        endereço no ar e estudo de caso.

        Args:
            tecnologias (list[Tecnologia]): As tecnologias criadas; cada projeto
                recebe as de mesmo nome que as de ``ProjetoDemo.tecnologias``.
        """
        por_nome = {tecnologia.nome: tecnologia for tecnologia in tecnologias}
        categorias = {
            slug: CategoriaProjeto.objects.get_or_create(
                slug=slug, defaults={"nome": nome}
            )[0]
            for nome, slug in CATEGORIAS_PROJETO
        }
        for ordem, demo in enumerate(PROJETOS):
            projeto, novo = Projeto.objects.get_or_create(
                titulo=demo.titulo,
                defaults={
                    "categoria_projeto": categorias[demo.categoria],
                    "descricao": demo.descricao,
                    "link_github": f"https://github.com/maria-souza-demo/{demo.endereco}",
                    "link_online": f"https://example.com/{demo.endereco}",
                    "ordem": ordem,
                    "problema": demo.problema,
                    "papel": demo.papel,
                    "decisao_tecnica": demo.decisao_tecnica,
                    "resultado": demo.resultado,
                },
            )
            if novo:
                nome_arquivo = f"demo-projeto-{ordem}.jpg"
                projeto.imagem.save(
                    nome_arquivo, self._imagem(nome_arquivo, 1200, 800, ordem)
                )
                projeto.tecnologias.set([por_nome[nome] for nome in demo.tecnologias])

    @staticmethod
    def _habilidades(tecnologias: list[Tecnologia]) -> None:
        """
        Cria as categorias de habilidade e as habilidades com nível.

        Args:
            tecnologias (list[Tecnologia]): As tecnologias criadas; a habilidade
                de mesmo nome fica ligada a ela.
        """
        por_nome = {tecnologia.nome: tecnologia for tecnologia in tecnologias}
        for nome, habilidades in HABILIDADES.items():
            categoria, _ = CategoriaHabilidade.objects.get_or_create(nome=nome)
            for habilidade, nivel in habilidades:
                Habilidade.objects.get_or_create(
                    categoria=categoria,
                    nome=habilidade,
                    defaults={"nivel": nivel, "tecnologia": por_nome.get(habilidade)},
                )
