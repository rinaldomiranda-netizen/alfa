"""Pesquisa web explícita para a Beta, sem depender de um LLM local.

A busca usa apenas a página HTML pública do DuckDuckGo e devolve títulos,
links e trechos apresentados pelo próprio mecanismo. Não abre links
automaticamente nem executa conteúdo retornado.
"""
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urlsplit, urlunsplit
from urllib.request import Request, urlopen


URL_BUSCA = "https://html.duckduckgo.com/html/"
TIMEOUT_PADRAO = 8
LIMITE_PADRAO = 5
TAMANHO_MAXIMO_HTML = 2_000_000


def _normalizar_link(href):
    """Converte redirecionamentos do DuckDuckGo em URLs HTTP(S) diretas."""
    href = (href or "").strip()
    if not href:
        return ""

    if href.startswith("//"):
        href = "https:" + href

    partes = urlsplit(href)
    parametros = parse_qs(partes.query)
    destino = parametros.get("uddg", [None])[0]
    if destino:
        href = destino
        partes = urlsplit(href)

    if partes.scheme not in ("http", "https") or not partes.netloc:
        return ""

    return urlunsplit((partes.scheme, partes.netloc, partes.path, partes.query, ""))


class _DuckDuckGoParser(HTMLParser):
    """Extrai somente os resultados mostrados na página HTML da busca."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.resultados = []
        self._atual = None
        self._captura = None
        self._profundidade = 0

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        classes = set((atributos.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._atual = {
                "titulo": "",
                "url": _normalizar_link(atributos.get("href")),
                "resumo": "",
            }
            self.resultados.append(self._atual)
            self._captura = "titulo"
            self._profundidade = 1
            return

        if self._atual is not None and "result__snippet" in classes:
            self._captura = "resumo"
            self._profundidade = 1
            return

        if self._captura:
            self._profundidade += 1

    def handle_startendtag(self, tag, attrs):
        # Tags vazias não contêm texto a capturar.
        return

    def handle_endtag(self, tag):
        if not self._captura:
            return
        self._profundidade -= 1
        if self._profundidade <= 0:
            self._captura = None
            self._profundidade = 0

    def handle_data(self, data):
        if not self._captura or self._atual is None:
            return
        if self._captura == "titulo":
            self._atual["titulo"] += data
        elif self._captura == "resumo":
            self._atual["resumo"] += data


def pesquisar(termo, limite=LIMITE_PADRAO, timeout=TIMEOUT_PADRAO):
    """Retorna (sucesso, mensagem) para ser usado pela Beta e pelo Tool Registry."""
    termo = " ".join(str(termo or "").split())
    if not termo:
        return False, "Não entendi o que você quer pesquisar na internet."
    if len(termo) > 300:
        return False, "A pesquisa é muito longa. Resuma o assunto em até 300 caracteres."

    try:
        quantidade = max(1, min(int(limite), 8))
    except (TypeError, ValueError):
        quantidade = LIMITE_PADRAO

    url = URL_BUSCA + "?q=" + quote_plus(termo)
    requisicao = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BetaAssistant/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        },
    )

    try:
        with urlopen(requisicao, timeout=timeout) as resposta:
            status = getattr(resposta, "status", 200)
            if status >= 400:
                return False, f"O mecanismo de pesquisa respondeu com erro HTTP {status}."
            cabecalhos = getattr(resposta, "headers", None)
            charset = "utf-8"
            if cabecalhos is not None and hasattr(cabecalhos, "get_content_charset"):
                charset = cabecalhos.get_content_charset() or charset
            documento = resposta.read(TAMANHO_MAXIMO_HTML + 1)
            if len(documento) > TAMANHO_MAXIMO_HTML:
                documento = documento[:TAMANHO_MAXIMO_HTML]
            html = documento.decode(charset, errors="replace")
    except Exception:
        return False, "Não consegui pesquisar na internet agora. Verifique a conexão e tente novamente."

    parser = _DuckDuckGoParser()
    try:
        parser.feed(html)
    except Exception:
        return False, "A página da pesquisa veio num formato que não consegui ler."

    resultados = []
    vistos = set()
    for item in parser.resultados:
        titulo = " ".join(item["titulo"].split())
        resumo = " ".join(item["resumo"].split())
        link = item["url"]
        if not titulo or not link or link in vistos:
            continue
        vistos.add(link)
        resultados.append({"titulo": titulo, "url": link, "resumo": resumo})
        if len(resultados) >= quantidade:
            break

    if not resultados:
        return False, "A pesquisa não retornou resultados que eu consiga ler. Tente reformular a pergunta."

    linhas = [f"Encontrei {len(resultados)} resultado(s) para: {termo}."]
    for indice, item in enumerate(resultados, 1):
        linhas.append(f"{indice}. {item['titulo']}")
        if item["resumo"]:
            linhas.append(f"   {item['resumo']}")
        linhas.append(f"   Fonte: {item['url']}")
    linhas.append("Use os links das fontes para confirmar os detalhes antes de tomar decisões importantes.")
    return True, "\n".join(linhas)
