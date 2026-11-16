---
feature: Descoberta da demo pelos buscadores e pelas redes sociais
status: concluído
date: 2026-11-16
related:
  - 004-correcoes-de-interface
  - 005-modo-demonstracao
  - 006-hospedagem
origin: nova feature
---

# Design — Descoberta da demo pelos buscadores e pelas redes sociais

## 1. Visão geral

O `settings.py` ganha `URL_PUBLICA`, lida e validada na subida por uma função
pequena, no mesmo estilo da checagem de `SECRET_KEY`. Um módulo novo,
`app_portfolio/descoberta.py`, concentra tudo o que é endereço público e
descoberta: a função que monta os metadados do `<head>` e as três views dos
arquivos (`robots.txt`, `sitemap.xml` e `security.txt`), que montam o texto em
Python, sem template.

A view `home` passa a pôr no contexto um dicionário `metadados`, e o `base.html`
deixa de calcular título, description e `og:*` a partir do `perfil`: só
renderiza o que recebe. Quem decide entre os textos da demo e os do `Perfil`, e
de onde vem o endereço absoluto, é a função `montar_metadados`, testável sem
renderizar a página.

## 2. Componentes

| Arquivo | Muda o quê |
| --- | --- |
| `portfolio/settings.py` | `URL_PUBLICA` e a função que a valida (RF-01) |
| `app_portfolio/descoberta.py` (novo) | `montar_metadados`, `robots_txt`, `sitemap_xml`, `security_txt`, textos da demo e `Expires` (RF-02 a RF-08) |
| `app_portfolio/views.py` | A `home` põe `metadados` no contexto (RF-02 a RF-04) |
| `app_portfolio/urls.py` | Rotas `robots.txt`, `sitemap.xml` e `.well-known/security.txt` (RF-06 a RF-08) |
| `templates/base.html` | `<head>` renderiza `metadados`, canonical, `og:url`, `twitter:card` e `apple-touch-icon` (RF-02 a RF-05) |
| `static/img/portfolio-django-divulgacao.png` (movida de `assets/`) | Imagem do cartão da demo, 1280 × 640 (RF-04, ADR-05) |
| `static/icons/apple-touch-icon.png` (novo) | Ícone de tela inicial, 180 × 180 (RF-05, ADR-06) |
| `app_portfolio/test_descoberta.py` (novo) | Testes do RF-10 |
| `pyproject.toml` | O módulo de teste novo entra no override de mypy da suíte |
| `.env.example`, `README.md`, `README.en.md`, `CLAUDE.md`, `docs/referencia/configuracoes.md`, `specs/README.md` | `URL_PUBLICA`, o sentido novo do `MODO_DEMONSTRACAO`, a árvore de arquivos e o índice (RNF-04) |

### `settings.py`

Logo depois de `URL_REPOSITORIO`:

```python
def _ler_url_publica(valor: str) -> str:
    """Devolve a URL sem a barra final, ou "" se vazia; ValueError se inválida."""

URL_PUBLICA = _ler_url_publica(os.getenv("URL_PUBLICA", ""))
```

A validação usa `urllib.parse.urlsplit`: esquema `http` ou `https`, `netloc` não
vazio, caminho vazio ou `/`, sem query e sem fragmento. Fora disso, `ValueError`
com a chave e um exemplo do valor esperado. A barra final sai com `rstrip("/")`,
então os pontos de uso sempre acrescentam o caminho a partir de `/`.

### `descoberta.py`

```python
TITULO_DEMONSTRACAO = "Demonstração | Portfólio em Django de código aberto"
DESCRICAO_DEMONSTRACAO = "Demonstração do portfolio-dinamico, ... Os dados são fictícios."
IMAGEM_DEMONSTRACAO = "img/portfolio-django-divulgacao.png"   # caminho em static/
ALT_IMAGEM_DEMONSTRACAO = "..."                                # descreve a imagem
EXPIRES_SECURITY_TXT = "2027-11-01T00:00:00Z"                  # renovar antes de vencer

def montar_metadados(request: HttpRequest, perfil: Perfil | None) -> dict[str, str | int]: ...
def robots_txt(request: HttpRequest) -> HttpResponse: ...
def sitemap_xml(request: HttpRequest) -> HttpResponse: ...
def security_txt(request: HttpRequest) -> HttpResponse: ...
```

**`montar_metadados`** devolve as chaves `titulo`, `descricao`, `og_titulo`,
`og_descricao`, `url_canonica` (vazia sem `URL_PUBLICA`), `imagem` (endereço
absoluto ou vazia), `imagem_largura`, `imagem_altura`, `imagem_alt` (só na demo)
e `twitter_card`.

- Com `MODO_DEMONSTRACAO`: os textos da demo nos quatro campos e a imagem de
  divulgação, `static(IMAGEM_DEMONSTRACAO)`, com 1280 × 640.
- Sem o modo: os mesmos valores de hoje, com os mesmos padrões de hoje (RF-09):
  título `"<nome ou 'Seu Nome'> | Desenvolvedor Full-Stack"`, description com o
  padrão "Portfólio de Desenvolvedor Full-Stack…", `og:title` com o padrão
  `'Portfólio'` e `og:description` sem padrão. A imagem é a `perfil.foto.url`,
  quando há foto.
- O endereço absoluto da imagem é `URL_PUBLICA + caminho` quando ela existe e
  `request.build_absolute_uri(caminho)` quando não (o mesmo esquema e `Host` que
  o template usa hoje, spec 004, RF-20).
- `twitter_card` é `summary_large_image` com imagem e `summary` sem.

**As três views** levam `@require_safe` (GET e HEAD) e
`@cache_control(public=True, max_age=86400)`, como a `servir_midia`. Cada uma
monta uma lista de linhas e devolve `HttpResponse` com o `content_type` do RF.
A `sitemap_xml` escapa a `<loc>` com `xml.sax.saxutils.escape`. A `sitemap_xml`
sem `URL_PUBLICA` e a `security_txt` sem o modo levantam `Http404`, que o
`404.html` atende como qualquer página que não existe.

### `base.html`

O `<head>` troca as expressões sobre `perfil` por `metadados`:

```django
<title>{% block title %}{{ metadados.titulo }}{% endblock %}</title>
<meta name="description" content="{{ metadados.descricao }}">
{% if metadados.url_canonica %}
<link rel="canonical" href="{{ metadados.url_canonica }}">
<meta property="og:url" content="{{ metadados.url_canonica }}">
{% endif %}
<meta property="og:title" ...>  <meta property="og:description" ...>
{% if metadados.imagem %} og:image (+ width, height e alt quando houver) {% endif %}
<meta name="twitter:card" content="{{ metadados.twitter_card }}">
<link rel="apple-touch-icon" href="{% static 'icons/apple-touch-icon.png' %}">
```

O `twitter:card` sozinho basta: na falta de `twitter:title`, `twitter:image` e
afins, o X usa os `og:*`. As páginas de erro estendem o `erro.html`, que não
herda o `base.html`, então ficam sem canonical sem nenhuma regra a mais (RF-02).

## 3. Modelo de dados

Nenhuma mudança. Nenhuma migração.

## 4. Interfaces

### Variáveis de ambiente (novas ou com uso novo)

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `URL_PUBLICA` | vazia | Endereço público do site (ex.: `https://seu-dominio.com.br`). Liga canonical, `og:url`, a linha `Sitemap:` e o `sitemap.xml`, e dá o endereço absoluto das imagens. Inválida, o servidor não sobe |
| `MODO_DEMONSTRACAO` | `False` | Além do formulário (spec 005): título, description e imagem do cartão da demo e o `security.txt` |

A demo passa a rodar também com
`URL_PUBLICA=https://portfolio-dinamico.ryanmorais.com.br`.

### Rotas

| Rota | Antes | Depois |
| --- | --- | --- |
| `/robots.txt` | 404 na origem (na demo, só o arquivo gerenciado do proxy) | 200, `text/plain; charset=utf-8` |
| `/sitemap.xml` | 404 | 200, `application/xml`, com `URL_PUBLICA`; 404 sem ela |
| `/.well-known/security.txt` | 404 | 200, `text/plain; charset=utf-8`, com `MODO_DEMONSTRACAO`; 404 sem ele |

### Conteúdo dos arquivos

```text
# robots.txt
User-agent: *
Allow: /

Sitemap: https://portfolio-dinamico.ryanmorais.com.br/sitemap.xml
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://portfolio-dinamico.ryanmorais.com.br/</loc></url>
</urlset>
```

```text
# security.txt: contato de segurança da demonstração (RFC 9116). Relate em
# privado, pelos avisos de segurança do GitHub; o escopo e os prazos estão na política.
Contact: https://github.com/ryanvmorais/portfolio-dinamico/security/advisories/new
Expires: 2027-11-01T00:00:00Z
Preferred-Languages: pt, en
Canonical: https://portfolio-dinamico.ryanmorais.com.br/.well-known/security.txt
Policy: https://github.com/ryanvmorais/portfolio-dinamico/blob/main/SECURITY.md
```

`Contact:` e `Policy:` partem de `URL_REPOSITORIO`, então um fork que troca essa
constante (o comentário dela já pede isso) leva os dois junto.

## 5. Decisões técnicas (ADRs)

### ADR-01 — Arquivos de descoberta montados em Python, sem template

**Decisão.** As três views montam o corpo como lista de linhas em
`descoberta.py`.
**Alternativas.** (a) Templates `robots.txt`, `sitemap.xml` e `security.txt` em
`templates/`, renderizados com `content_type`; (b) arquivos estáticos servidos
pelo WhiteNoise.
**Porquê.** Cada arquivo tem de 3 a 7 linhas, e duas delas dependem de
configuração. Em Python, o teste chama a view e compara o texto, e o `Expires`
fica numa constante que o teste lê sem analisar arquivo. Template de texto exige
`{% autoescape off %}` para não escapar URL como HTML; o arquivo estático não
lê `URL_PUBLICA` nem o modo.
**Trade-off.** Quem quer mudar o texto edita Python, não um arquivo de texto; o
corpo fica junto da regra que decide se ele existe.

### ADR-02 — Sitemap sem `django.contrib.sitemaps`

**Decisão.** O XML é montado à mão, com uma `<loc>` e o `escape` da biblioteca
padrão.
**Alternativas.** (a) `django.contrib.sitemaps` com uma classe `Sitemap`.
**Porquê.** O app do Django monta o domínio pelo `get_current_site`, que sem o
`django.contrib.sites` usa o `Host` do pedido (RNF-03 proíbe); contornar exige
sobrescrever `get_domain` ou instalar o `sites` com o domínio no banco. Para uma
URL, são duas apps e uma migração a mais por quatro linhas de XML.
**Trade-off.** Se o site ganhar páginas, o sitemap à mão cresce junto; aí o
`contrib.sitemaps` volta a compensar.

### ADR-03 — Metadados montados na view, não no template

**Decisão.** `montar_metadados` decide os textos e os endereços, e o
`base.html` só renderiza.
**Alternativas.** (a) `{% if modo_demonstracao %}` e filtros `default` no
próprio `<head>`; (b) um context processor.
**Porquê.** A regra tem três casos de imagem, dois de texto e duas origens de
endereço: no template ela ficaria espalhada em `{% if %}` aninhados, testável só
pelo HTML. Na função, cada caso vira um teste direto, e os textos da demo são
constantes, como as `MENSAGEM_*` da `views.py`. O context processor rodaria em
toda página, mas só a home estende o `base.html`.
**Trade-off.** Uma página nova que estenda o `base.html` precisa pôr
`metadados` no contexto, ou o `<head>` sai sem título.

### ADR-04 — `URL_PUBLICA` validada na subida

**Decisão.** Valor inválido derruba a subida com `ValueError`.
**Alternativas.** (a) Ignorar o valor inválido e seguir como se vazia;
(b) registrar um aviso no log.
**Porquê.** Um valor sem esquema ou com caminho publicaria canonical e sitemap
errados para o buscador, um erro que só aparece semanas depois, no relatório de
indexação. Falhar na subida mostra o erro no deploy, como a falta de
`SECRET_KEY`.
**Trade-off.** Um erro de digitação na variável tira o site do ar até a correção;
com o deploy da plataforma, a versão anterior segue no ar até a nova subir.

### ADR-05 — A imagem de divulgação sai de `assets/` para `static/img/`

**Decisão.** `git mv assets/django-fullstack-portfolio-social-preview.png
static/img/portfolio-django-divulgacao.png`, sem cópia.
**Alternativas.** (a) Copiar para `static/` e manter as duas; (b) servir de
`assets/` por uma rota.
**Porquê.** Um arquivo só: a prévia social do repositório é enviada à mão nas
configurações do GitHub, de qualquer caminho, e o cartão da demo precisa do
arquivo em `static/` para o `collectstatic` e o WhiteNoise. PNG, porque é o
formato que todas as redes aceitam no `og:image`.
**Trade-off.** O `collectstatic` publica mais 141 KB; `assets/` fica só com a
capa dos READMEs.

### ADR-06 — Ícone de tela inicial gerado uma vez a partir do `favicon.webp`

**Decisão.** O `apple-touch-icon.png` (180 × 180) sai do `favicon.webp`
(256 × 256, opaco) por redução com Pillow (`Image.LANCZOS`), e o PNG é
versionado.
**Alternativas.** (a) Comando de management que gera o ícone no build;
(b) desenhar um ícone novo.
**Porquê.** O favicon já é opaco e maior que 180 px, então a redução não perde
nitidez nem ganha fundo transparente (que o iOS preencheria de preto). Gerar no
build traria o Pillow ao caminho do deploy por um arquivo que muda quase nunca.
**Trade-off.** Se o favicon mudar, o ícone precisa ser refeito à mão; o teste
confere só o tamanho e a opacidade, não a semelhança.

### ADR-07 — `Expires` fixo, com teste de prazo

**Decisão.** `EXPIRES_SECURITY_TXT` é uma data fixa no código, e o teste falha
quando faltam menos de 30 dias ou quando ela passa de 366 dias à frente.
**Alternativas.** (a) `Expires` calculado na hora (hoje + 1 ano).
**Porquê.** O `Expires` existe para o leitor saber se o contato ainda é cuidado
(RFC 9116, 2.5.5). Calculado na hora, ele nunca vence, mesmo com o canal
abandonado. A data fixa obriga uma revisão por ano, e o teste avisa um mês antes.
**Trade-off.** Uma vez por ano, a suíte fica vermelha até alguém renovar a data
num commit.

## 6. Impacto e dependências

- **Dependências:** nenhuma nova. O Pillow já é dependência de runtime e só é
  usado uma vez, na geração do ícone (ADR-06).
- **`base.html`:** as expressões sobre `perfil` no `<head>` saem; o `og:image`
  montado com `request.scheme` e `request.get_host` passa para a
  `montar_metadados`. O corpo da página não muda.
- **Spec 004, RF-20:** fica como está (registro concluído). O comportamento sem
  `URL_PUBLICA` é o mesmo; com ela, o endereço passa a vir da configuração.
- **Spec 005:** fica como está. O sentido novo do `MODO_DEMONSTRACAO` é desta
  spec e vai para a documentação das variáveis.
- **Testes existentes:** o do `test_interface.py` que confere o `og:image`
  absoluto pelo HTML (spec 004, RF-20) segue valendo sem `URL_PUBLICA`; nenhum
  teste atual lê o `<title>` ou o `og:title`.
- **CI e Lighthouse:** sem `URL_PUBLICA` no CI, o HTML auditado não tem
  canonical, como hoje.
- **Operação fora do repositório:** definir `URL_PUBLICA` no painel da
  plataforma e enviar o sitemap aos buscadores.

## 7. Estratégia de testes

Tudo em `app_portfolio/test_descoberta.py`, sem rede, com a fixture `settings`
do pytest-django para ligar `URL_PUBLICA` e `MODO_DEMONSTRACAO`:

- **`URL_PUBLICA` (RF-01):** `_carregar_settings` (de `tests.py`, cuja lista de
  variáveis limpas ganha `URL_PUBLICA`) com valor sem barra, com barra, vazio e
  quatro inválidos (sem esquema, `ftp://`, com caminho, com query): os inválidos
  levantam `ValueError`.
- **`montar_metadados` (RF-02 a RF-04, RF-09):** chamada direta, com
  `RequestFactory` e um `Perfil` em memória, nos casos demo, perfil com foto e
  perfil sem foto, com e sem `URL_PUBLICA`. Sem `URL_PUBLICA`, um `Host` forjado
  aparece só no `og:image`, nunca na `url_canonica` (RNF-03).
- **`<head>` da home (RF-02 a RF-05):** GET com o banco de teste; confere
  canonical sem a query string, `og:url`, `twitter:card`, `apple-touch-icon` e os
  textos da demo. Uma página 404 sem canonical.
- **Arquivos (RF-06 a RF-08):** cliente de teste em cada rota, com e sem a
  configuração; status, `Content-Type`, corpo; `ADMIN_URL` trocada não aparece no
  `robots.txt`; o sitemap analisado com `xml.etree.ElementTree` tem uma `<loc>`
  igual ao canonical da home.
- **Prazo do `Expires` (RF-08, ADR-07):** `EXPIRES_SECURITY_TXT` entre 30 e 366
  dias à frente da data do teste.
- **Imagens (RF-04, RF-05):** Pillow abre `static/img/portfolio-django-divulgacao.png`
  (1280 × 640, igual às constantes) e `static/icons/apple-touch-icon.png`
  (180 × 180, sem canal alfa).

## Desvios

1. **Constantes a mais em `descoberta.py`** (RF-04, RF-09). Além das listadas na
   seção 2, `LARGURA_IMAGEM_DEMONSTRACAO` e `ALTURA_IMAGEM_DEMONSTRACAO` guardam
   as dimensões da imagem (o teste compara o arquivo com elas), e
   `SUFIXO_TITULO` e `DESCRICAO_PADRAO` guardam os padrões que antes estavam no
   `base.html`. O `montar_metadados` devolve `imagem_largura` e `imagem_altura`
   como `0` quando a imagem é a foto do perfil, de tamanho desconhecido; o
   template só escreve as dimensões quando são diferentes de zero.
2. **`alt` da imagem de divulgação** (RF-04). A imagem não é uma captura da home:
   é a arte de divulgação do template (título, resumo e um trecho do `views.py`),
   e o `ALT_IMAGEM_DEMONSTRACAO` descreve isso.
3. **Imagem de divulgação refeita, em JPEG** (RF-04, ADR-05). A imagem que estava
   em `assets/` trazia o nome antigo do repositório e um trecho de código que não
   existe mais no `views.py`. Ela foi refeita com o nome atual e um trecho do
   código de hoje, e saiu como `static/img/portfolio-django-divulgacao.jpg`, no
   lugar do PNG movido: o degradê do fundo deixava o PNG com cerca de 780 KiB, e
   o JPEG (qualidade 88) fica com 106 KiB sem diferença visível. O formato
   continua aceito por todas as redes no `og:image` e pelo GitHub na prévia
   social; o arquivo de `assets/` sai do repositório do mesmo jeito.

## Notas de implementação

- **Testes:** 193 antes da spec, 230 depois; os 37 novos ficam em
  `app_portfolio/test_descoberta.py`. O `_carregar_settings` de `tests.py`
  passou a limpar `URL_PUBLICA`.
- **`check --deploy`:** com `DEBUG=False`, `ALLOWED_HOSTS` e `URL_PUBLICA`
  definidos, "System check identified no issues".
- **`<head>` conferido** renderizando a home com o modo demonstração e
  `URL_PUBLICA`: título, description, canonical, `og:*` com dimensões e alt,
  `twitter:card` e `apple-touch-icon` na ordem da seção 2.
- **Imagens:** a de divulgação ficou em JPEG, 1280 × 640, 106 KiB (desvio 3); o
  `apple-touch-icon.png` (180 × 180, RGB, 38 KB) saiu do
  `favicon.webp` por redução `LANCZOS`.
- **Avisos do pytest:** os testes novos que usam o cliente emitem o mesmo
  "No directory at: staticfiles" do WhiteNoise que o resto da suíte já emite
  (o `collectstatic` não roda nos testes).

