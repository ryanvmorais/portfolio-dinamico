# Modelos, imagens e formulário de contato

Mapa: vai mexer em `models.py`, `utils.py` ou na view `home` (o POST do contato)? Leia antes.
Requisitos e ADRs: `specs/001-vitrine-portfolio/`, `specs/002-formulario-contato/` e, para os
campos do redesenho (nível, estudo de caso, marca), `specs/008-redesenho-da-home/`.

## Modelos (em `models.py`)

1. **Auxiliares**: `Tecnologia` (nome e `ordem`; marca os projetos e, ligada a
   uma `Habilidade`, conta os projetos que a provam), `CategoriaProjeto`
   (agrupamento por `slug`) e `CategoriaHabilidade`.
2. **Identidade**: `Perfil` (sem constraint de singleton: convenção de uso,
   não regra de negócio; um segundo registro faria `Perfil.objects.first()`
   retornar algo arbitrário). `foto`, `curriculo`, `link_linkedin` e
   `link_github` são opcionais: o template guarda cada um com `{% if %}`. O
   rodapé lê a `bio_curta` e só o GitHub e o LinkedIn do `Perfil` (spec 008,
   RF-15). `anos_experiencia` igual a zero esconde o número no hero e no selo
   do Sobre.
3. **Portfólio**: `Projeto` (ordenado por `ordem`, M2M com `Tecnologia`,
   `categoria_projeto` opcional via `SET_NULL`, `link_github` e `link_online`
   opcionais). O estudo de caso são quatro `TextField` opcionais (`problema`,
   `papel`, `decisao_tecnica`, `resultado`, até 600 caracteres no Admin); a
   propriedade `tem_estudo_de_caso` diz se algum tem texto.
4. **Habilidades**: `Habilidade` (FK `CategoriaHabilidade`; `nivel` do
   `NivelHabilidade`, um `TextChoices` de três valores cuja ordem é a de
   exibição; FK opcional `tecnologia`, `SET_NULL`). A view anota
   `qtd_projetos` (projetos distintos da tecnologia ligada) e agrupa por nível
   em `agrupar_habilidades()`.
5. **Contato**: `MensagemContato` (`mensagem` com `MaxLengthValidator(5000)`).

Os números do hero não são cadastrados: os anos vêm do `Perfil` e os projetos
publicados são `len(projetos)` na view.

## Marca gerada das iniciais (em `marca.py`)

`calcular_iniciais()` junta a primeira letra da primeira e da última palavra do
`Perfil.nome` (com acento; sem nome, "Seu Nome"). As iniciais vão para o
monograma do logo (contexto `iniciais` da `home`), para o `/favicon.svg` (SVG
montado em texto, com a fonte do sistema) e para o `/apple-touch-icon.png` (PNG
opaco de 180 px desenhado pelo Pillow com a Inter de `static/fonts/`,
memoizado por `lru_cache`). Sem `Perfil`, as duas rotas redirecionam (302)
para o `favicon.webp` e o `apple-touch-icon.png` de `static/icons/`, que trazem o
mesmo monograma com as iniciais padrão ("SN"). O `?v=` com as iniciais no
`<head>` fura o cache de um dia quando o nome muda. As páginas de erro ligam o
`/favicon.svg` sem o `?v=` (não têm contexto), com o `favicon.webp` de reserva.

## Tratamento de imagens

`utils.converter_para_webp()` é chamado no `save()` de `Perfil` (campo `foto`)
e `Projeto` (campo `imagem`).

- **Qualidade**: comprime para WebP com `quality=80`.
- **Skip automático**: se a imagem já estiver em WebP, retorna `(None, None)`.
- **Transparência**: RGBA/P convertidos para RGBA (preserva alpha); demais
  modos vão para RGB.
- **`save=False`**: usado em `image_field.save(novo_nome, conteudo,
  save=False)` para evitar recursão infinita (não chama o `save()` do model
  de novo).

Ao adicionar um novo model com `ImageField`, siga o mesmo padrão: sobrescreva
`save()`, chame `converter_para_webp()`, cheque `if novo_conteudo and
novo_nome:` (os dois juntos: o `mypy` não infere que são não-`None` juntos a
partir de checar só um) e use `save=False`.

## Formulário de contato (em `views.py`)

Tudo roda dentro da view `home`, no ramo `if request.method == "POST"`, nesta
ordem:

1. **Honeypot**: campo oculto `honeypot`; preenchido → redirect silencioso,
   nada é salvo.
2. **Validação**: `MensagemContatoForm` (ModelForm).
3. **Modo demonstração** (spec 005): com `MODO_DEMONSTRACAO` ligado, responde
   `{"status": "demo", "message", "link"}` (AJAX) ou
   `messages.info(..., extra_tags="demo")` + redirect, sem gravar, enviar nem
   tocar no rate limit.
4. **Rate limit**: cache em arquivo (`CacheArquivoAtomico`, subclasse do
   `FileBasedCache` em `app_portfolio/cache.py`, pasta `django_cache/`,
   compartilhado entre workers) pela chave `contact_limit_{REMOTE_ADDR}`, janela
   de 600 s. `cache.add()` reserva a vaga **antes** de gravar e enviar, para que
   pedidos concorrentes não passem todos pela checagem (CWE-362). A reserva só é
   atômica pela trava de arquivo da subclasse: o `add()` do `FileBasedCache` puro
   checa e grava sem trava. A vaga não é liberada se o e-mail falhar.
5. **Sanitização**: `bleach.clean(mensagem, tags=[], strip=True)` antes de
   salvar (só o campo `mensagem`; `nome`/`assunto` não passam por `bleach`).
6. **Gravação**: `form.save(commit=False)`, troca da mensagem pela versão limpa e `save()`.
7. **Envio de e-mail**: `send_mail()` síncrono; falha é capturada e logada
   (`logger.exception`), nunca propaga: a mensagem já salva no banco não é
   perdida.
8. **Resposta híbrida**: o header `X-Requested-With: XMLHttpRequest` decide
   entre `JsonResponse` (AJAX) e `redirect`/`messages` (HTML tradicional). Os dois
   fluxos dizem a mesma frase (`MENSAGEM_ENVIADO`, `MENSAGEM_LIMITE_ENVIO`,
   `MENSAGEM_DADOS_INVALIDOS`, `MENSAGEM_FALHA_ENVIO`, em `views.py`): o
   `main.js` mostra o `message` de toda resposta que não seja sucesso, e o
   `base.html` mostra as `messages` no mesmo componente `.notification`.

> ⚠️ **Não regredir:** os testes desta feature (`app_portfolio/tests.py`)
> dependem da fixture autouse `disable_real_email`, que troca o mailer
> `default` do `MAILERS` para `locmem` durante a suíte. Sem ela, `send_mail()`
> tentaria conectar ao SMTP real do Gmail configurado em `settings.py` a cada
> teste: lento, dependente de rede, e capaz de enviar e-mail de verdade se o
> `.env` local tiver credenciais reais.
