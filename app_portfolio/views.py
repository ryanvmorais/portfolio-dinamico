"""
Views do portfólio: a página única e a entrega da mídia enviada pelo Admin.

A ``home`` monta a página com os dados do banco e recebe o formulário de
contato. O envio passa por honeypot, limite por IP e sanitização antes de
gravar e notificar por e-mail, e responde em HTML ou em JSON (AJAX). Com o
``MODO_DEMONSTRACAO`` ligado, o envio válido para depois da validação: nada é
gravado nem enviado, e o visitante recebe o aviso de demonstração.

A ``servir_midia`` entrega os arquivos do ``MEDIA_ROOT`` também com
``DEBUG=False``, porque a plataforma da demo não tem servidor web na frente
do Django (spec 006).
"""

import logging
import mimetypes

import bleach
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import SuspiciousFileOperation
from django.core.mail import send_mail
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe
from django.views.static import serve

from .forms import MensagemContatoForm
from .models import (
    CategoriaHabilidade,
    CategoriaProjeto,
    Estatistica,
    Perfil,
    Projeto,
    Tecnologia,
)

# Frases mostradas ao visitante quando o envio não vai adiante (spec 004,
# RF-03): o JavaScript exibe `message` das respostas JSON, e o limite de envio
# usa a mesma frase no fluxo HTML tradicional (django.contrib.messages).
MENSAGEM_ENVIADO = "Mensagem enviada!"
MENSAGEM_LIMITE_ENVIO = (
    "Você já enviou uma mensagem recentemente. Aguarde 10 minutos para enviar outra."
)
MENSAGEM_FALHA_ENVIO = (
    "Não foi possível enviar agora. Tente novamente em alguns minutos."
)
MENSAGEM_DADOS_INVALIDOS = "Confira os campos do formulário e tente novamente."

# Aviso do envio no modo demonstração (spec 005, RF-05). O link vai à parte, em
# dados (JSON) ou montado pelo base.html, nunca como HTML dentro da frase
# (ADR-03): o visitante lê "frase + link + ponto final".
MENSAGEM_DEMONSTRACAO = (
    "Este formulário faz parte de um projeto educacional e não envia mensagens. "
    "Quer ver como ele funciona por dentro?"
)
TEXTO_LINK_DEMONSTRACAO = "Clone ou baixe o código no GitHub"

logger = logging.getLogger(__name__)

# O Python 3.12 só conhece o .webp pelo mime.types do sistema, que a imagem de
# um contêiner enxuto pode não ter. Sem o tipo, a servir_midia responderia
# application/octet-stream, e com o nosniff o navegador não mostraria a foto.
mimetypes.add_type("image/webp", ".webp")


def home(request: HttpRequest) -> HttpResponse:
    """
    Renderiza a Home e processa o formulário de contato (GET + POST).

    No POST, aplica em sequência honeypot, validação do formulário, modo
    demonstração, rate limit por IP (reserva atômica via ``cache.add()``, com
    a trava do backend ``CacheArquivoAtomico``) e
    sanitização (Bleach) antes de salvar a mensagem e disparar o e-mail de
    notificação. Com o modo demonstração ligado, o envio válido para antes do
    rate limit e responde o aviso de demonstração (status ``demo`` no JSON,
    mensagem ``info`` no HTML). Responde em HTML (navegação comum) ou JSON
    (requisição AJAX, identificada pelo header ``X-Requested-With``).

    Args:
        request (HttpRequest): Requisição GET (exibição) ou POST (envio do
            formulário de contato).

    Returns:
        HttpResponse: Página renderizada, redirect (fluxo HTML) ou
            :class:`~django.http.JsonResponse` (fluxo AJAX).
    """
    # --- 1. BUSCAR DADOS DO BANCO (GET) ---
    perfil = Perfil.objects.first()

    # select_related e prefetch_related trazem categoria e tecnologias junto:
    # sem eles, o template faria uma consulta por projeto (N+1).
    projetos = (
        Projeto.objects.select_related("categoria_projeto")
        .prefetch_related("tecnologias")
        .all()
    )

    tech_icons = Tecnologia.objects.filter(mostrar_no_home=True).order_by(
        "ordem", "nome"
    )
    estatisticas = Estatistica.objects.all()
    categorias_projetos = CategoriaProjeto.objects.all()
    categorias_habilidades = CategoriaHabilidade.objects.prefetch_related(
        "habilidades"
    ).all()

    form = MensagemContatoForm()

    # --- 2. LÓGICA DO FORMULÁRIO DE CONTATO (POST) ---
    if request.method == "POST":

        # A. SEGURANÇA: HONEYPOT CHECK
        # O campo é invisível para pessoas; preenchido, é robô. O redirect
        # silencioso não dá ao robô sinal de que foi barrado.
        honeypot = request.POST.get("honeypot")
        if honeypot:
            return redirect("home")

        form = MensagemContatoForm(request.POST)

        if form.is_valid():
            # MODO DEMONSTRAÇÃO (spec 005, ADR-02)
            # Depois da validação, que é parte do que a demo mostra, e antes do
            # rate limit: sem gravar nem enviar, o dado do visitante não fica
            # guardado sem finalidade, e nenhuma chave nasce no cache (dá para
            # testar de novo na hora).
            if settings.MODO_DEMONSTRACAO:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "status": "demo",
                            "message": MENSAGEM_DEMONSTRACAO,
                            "link": {
                                "texto": TEXTO_LINK_DEMONSTRACAO,
                                "url": settings.URL_REPOSITORIO,
                            },
                        }
                    )
                # extra_tags="demo" diz ao base.html que o aviso leva o link.
                messages.info(request, MENSAGEM_DEMONSTRACAO, extra_tags="demo")
                return redirect("home")

            # B. SEGURANÇA: RATE LIMIT (Controle de Fluxo)
            # cache.add() só grava se a chave ainda não existir e reserva o
            # slot antes de processar o envio. Um cache.get() + cache.set()
            # deixaria requisições concorrentes passarem pela checagem antes
            # que a primeira gravasse o bloqueio (race condition, CWE-362). A
            # reserva só é atômica porque o backend do projeto trava o add()
            # (app_portfolio/cache.py): o do FileBasedCache puro não trava.
            user_ip = request.META.get("REMOTE_ADDR")
            cache_key = f"contact_limit_{user_ip}"
            if not cache.add(cache_key, True, 600):
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"status": "error", "message": MENSAGEM_LIMITE_ENVIO},
                        status=429,
                    )
                messages.error(request, MENSAGEM_LIMITE_ENVIO)
                return redirect("home")

            # C. SEGURANÇA: SANITIZAÇÃO (Bleach)
            # Remove qualquer tag HTML maliciosa enviada no campo de mensagem (Proteção XSS).
            mensagem_limpa = bleach.clean(
                form.cleaned_data["mensagem"], tags=[], strip=True
            )

            mensagem_obj = form.save(commit=False)
            mensagem_obj.mensagem = mensagem_limpa
            mensagem_obj.save()

            # D. COMUNICAÇÃO: ENVIO DE E-MAIL (SMTP)
            try:
                assunto_email = f"Novo Contato: {mensagem_obj.assunto}"
                corpo_email = (
                    f"Mensagem de: {mensagem_obj.nome}\n"
                    f"E-mail: {mensagem_obj.email}\n\n"
                    f"Conteúdo:\n{mensagem_obj.mensagem}"
                )

                # ENDERECO_CONTATO vem do .env; se ausente, o send_mail falha
                # aqui dentro e cai no except abaixo (comportamento já
                # esperado, não um caso a modelar no tipo). Sem fail_silently:
                # o argumento está depreciado no Django 6.1 e o padrão já
                # propaga a falha até o except.
                send_mail(
                    assunto_email,
                    corpo_email,
                    settings.ENDERECO_CONTATO,
                    [settings.ENDERECO_CONTATO],  # type: ignore[list-item]
                )

                # Suporte para respostas assíncronas (AJAX)
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"status": "success", "message": MENSAGEM_ENVIADO}
                    )
                messages.success(request, MENSAGEM_ENVIADO)
                return redirect("home")

            except Exception:
                logger.exception("Falha ao enviar e-mail de contato")
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"status": "error", "message": MENSAGEM_FALHA_ENVIO},
                        status=500,
                    )
                messages.error(request, MENSAGEM_FALHA_ENVIO)

        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"status": "error", "message": MENSAGEM_DADOS_INVALIDOS},
                    status=400,
                )
            messages.error(request, MENSAGEM_DADOS_INVALIDOS)

    # --- 3. CONTEXTO PARA O TEMPLATE ---
    context = {
        "perfil": perfil,
        "form": form,
        "projetos": projetos,
        "categorias_habilidades": categorias_habilidades,
        "tech_icons": tech_icons,
        "estatisticas": estatisticas,
        "categorias_projetos": categorias_projetos,
        # O aviso fixo do formulário e o link do aviso do envio (spec 005).
        "modo_demonstracao": settings.MODO_DEMONSTRACAO,
        "url_repositorio": settings.URL_REPOSITORIO,
        "texto_link_demonstracao": TEXTO_LINK_DEMONSTRACAO,
    }

    return render(request, "home.html", context)


# ---------------------------------------------------------------------------
# Mídia enviada pelo Admin
# ---------------------------------------------------------------------------


@require_safe
@cache_control(public=True, max_age=86400)
def servir_midia(request: HttpRequest, caminho: str) -> HttpResponseBase:
    """
    Entrega um arquivo do ``MEDIA_ROOT`` (fotos e currículo), com ou sem DEBUG.

    O ``serve`` do Django já junta o caminho à pasta com ``safe_join`` (``../``
    vira 404), recusa pasta sem listar o conteúdo, põe o ``Content-Type`` pela
    extensão e responde 304 ao ``If-Modified-Since``. A documentação dele
    desaconselha o uso em produção por eficiência; aqui o tráfego é baixo, o
    envio é só pelo Admin e a Cloudflare guarda as imagens em cache (spec 006,
    ADR-06). O ``max-age`` de um dia não esconde troca de imagem: o Django gera
    nome novo quando o arquivo já existe. O ``MEDIA_ROOT`` é lido a cada pedido,
    não na carga das rotas.

    O caminho que sai da pasta (``../``) faz o ``safe_join`` levantar
    ``SuspiciousFileOperation``, que o Django responderia com 400 e registraria
    no log; aqui vira 404, como um arquivo que não existe.

    Args:
        request (HttpRequest): Pedido GET ou HEAD (os outros métodos recebem 405).
        caminho (str): Caminho do arquivo dentro do ``MEDIA_ROOT``.

    Returns:
        HttpResponseBase: O arquivo (200) ou 304, se o navegador já tem a versão
            atual.

    Raises:
        Http404: Se o arquivo não existe, é uma pasta ou sai do ``MEDIA_ROOT``.
    """
    try:
        return serve(request, caminho, document_root=str(settings.MEDIA_ROOT))
    except SuspiciousFileOperation as erro:
        raise Http404("Arquivo não encontrado.") from erro
