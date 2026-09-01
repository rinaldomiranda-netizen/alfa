"""
Planejamento assistido por Ollama (cérebro local OPCIONAL).

FRONTEIRA DE SEGURANÇA: o LLM nunca executa nada diretamente. Ele só
pode propor um nome de ferramenta e parâmetros; `propor_plano()`
descarta qualquer ferramenta que não exista de verdade no Tool
Registry (agente/ferramentas.py) antes de montar a Tarefa — texto
livre do LLM jamais vira comando de shell nem chamada arbitrária.

Só é chamado para frases que o Intent Engine determinístico NÃO
reconheceu (intent DESCONHECIDO) E que parecem um pedido de ação (ver
`parece_tarefa`) — perguntas/conversa comuns nunca pagam o custo
extra de uma chamada de planejamento antes da conversa normal (ver
core/router.py).
"""

import json
import re
import urllib.request

from agente.planejador import Etapa, Tarefa

TIMEOUT_SEGUNDOS = 20

VERBOS_DE_ACAO = (
    "abra", "abre", "abrir", "feche", "fecha", "fechar", "crie", "criar",
    "digite", "escreva", "escrever", "salve", "salvar", "copie", "copiar",
    "mova", "mover", "renomeie", "renomear", "procure", "procurar",
    "localize", "localizar", "selecione", "selecionar", "clique", "clicar",
    "pesquise", "pesquisar", "navegue", "navegar", "troque", "trocar",
    "liste", "listar", "role", "rolar", "arraste", "arrastar",
)


def parece_tarefa(texto):
    """Filtro barato para não gastar uma chamada extra ao LLM em toda
    conversa comum — só tenta planejar quando há um verbo de ação."""
    normalizado = (texto or "").lower()
    return any(re.search(rf"\b{v}\b", normalizado) for v in VERBOS_DE_ACAO)


def _catalogo_ferramentas(registro):
    linhas = []
    for ferramenta in registro.listar():
        parametros = ", ".join(ferramenta.parametros.keys()) if ferramenta.parametros else ""
        linhas.append(f"- {ferramenta.nome}({parametros}): {ferramenta.descricao}")
    return "\n".join(linhas)


PROMPT_SISTEMA = """Você é o planejador da BETA, uma assistente de computador que roda \
100% local no Windows do usuário. Dado um pedido, responda SOMENTE um JSON no formato:

{{"etapas": [{{"ferramenta": "nome_exato", "parametros": {{...}}, "objetivo": "..."}}]}}

Use SOMENTE ferramentas desta lista (nome EXATO, nunca invente uma nova):
{catalogo}

Se o pedido não for uma tarefa executável no computador (for só uma \
pergunta ou conversa), responda exatamente {{"etapas": []}}.
Nunca invente parâmetros sem sentido para a ferramenta escolhida."""


def propor_plano(pedido, registro, url, modelo, contexto_extra=None):
    """
    Pergunta ao Ollama como cumprir `pedido` com as ferramentas do
    `registro`. Retorna uma Tarefa com 1+ etapas VALIDADAS, ou None se
    a chamada falhar, a resposta não puder ser interpretada, ou o LLM
    decidir que não é uma tarefa executável.

    `contexto_extra`, se fornecido, é uma frase curta lembrando o LLM
    do estado da conversa (ver agente/orquestrador.py -> CONTEXTO DE
    TAREFA), ex.: qual foi o último programa aberto.
    """
    mensagens = [
        {"role": "system", "content": PROMPT_SISTEMA.format(catalogo=_catalogo_ferramentas(registro))},
    ]
    if contexto_extra:
        mensagens.append({"role": "system", "content": contexto_extra})
    mensagens.append({"role": "user", "content": pedido})

    payload = {
        "model": modelo,
        "messages": mensagens,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 400},
        "keep_alive": "30m",
    }

    try:
        requisicao = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        plano_bruto = json.loads(dados["message"]["content"])
    except Exception:
        return None

    etapas_propostas = plano_bruto.get("etapas") if isinstance(plano_bruto, dict) else None
    if not isinstance(etapas_propostas, list) or not etapas_propostas:
        return None

    etapas = []
    for proposta in etapas_propostas:
        if not isinstance(proposta, dict):
            continue
        nome_ferramenta = proposta.get("ferramenta")
        parametros = proposta.get("parametros")
        if not isinstance(parametros, dict):
            parametros = {}

        # Modelos pequenos/rápidos às vezes escrevem "ferramenta(valor)"
        # em vez de separar nome e parâmetros — tenta recuperar SÓ SE
        # o nome real (antes do parêntese) existir no registro; nunca
        # aceita um nome que não exista, com ou sem parêntese.
        if nome_ferramenta and registro.obter(nome_ferramenta) is None:
            casamento = re.match(r"^(\w+)\((.*)\)$", nome_ferramenta.strip())
            if casamento and registro.obter(casamento.group(1)) is not None:
                ferramenta_real = registro.obter(casamento.group(1))
                valor_posicional = casamento.group(2).strip().strip("'\"")
                if valor_posicional and not parametros and ferramenta_real.parametros:
                    primeiro_parametro = next(iter(ferramenta_real.parametros))
                    parametros = {primeiro_parametro: valor_posicional}
                nome_ferramenta = casamento.group(1)

        # FRONTEIRA DE SEGURANÇA: só entra no plano se o nome (já
        # normalizado acima) existir DE VERDADE no registro — o LLM
        # nunca executa nada fora do catálogo que ele mesmo recebeu.
        if not nome_ferramenta or registro.obter(nome_ferramenta) is None:
            continue
        objetivo = proposta.get("objetivo") or nome_ferramenta
        etapas.append(Etapa(
            objetivo=objetivo,
            ferramenta=nome_ferramenta,
            parametros=parametros,
            tratamento_erro=f"Não consegui completar '{objetivo}'.",
        ))

    if not etapas:
        return None

    return Tarefa(objetivo_geral=pedido, etapas=etapas)
