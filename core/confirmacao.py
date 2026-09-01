"""
Confirmação de INFORMAÇÕES ditas por uma pessoa (nome, data, etc.) —
usada pelo fluxo de atendimento (core/atendimento.py) para nunca
registrar um dado sem confirmação explícita:

    Pessoa: "Meu nome é João da Silva."
    BETA:   "Só para confirmar: seu nome é João da Silva?"
    (confirma -> registra; nega -> pergunta de novo)

Distinto da confirmação de AÇÕES SENSÍVEIS do core/router.py (que
confirma "fechar programa"/"desligar computador"): aqui o que se
confirma é um DADO falado por uma pessoa durante um atendimento, não
uma ação a executar no computador. Reaproveita as mesmas listas de
palavras de confirmação/negação de security/permissions.py para
manter um único vocabulário de "sim"/"não" em todo o projeto.
"""

from core.normalizer import normalize
from security.permissions import CONFIRMACAO_NEGATIVA, CONFIRMACAO_POSITIVA

# Frases que pedem para PULAR um campo opcional (já normalizadas:
# minúsculas, sem acento — ver core/normalizer.py). Cobrem os
# exemplos pedidos e variações naturais de cada um.
FRASES_PULAR = [
    "pular",
    "pula essa",
    "pule essa",
    "pular essa",
    "pula isso",
    "pule isso",
    "pular isso",
    "nao quero informar",
    "nao quero dizer",
    "nao quero responder",
    "nao tenho essa informacao",
    "nao tenho isso",
    "nao tenho essa resposta",
    "prefiro nao responder",
    "prefiro nao informar",
    "prefiro nao dizer",
    "sem resposta para isso",
    "deixa em branco",
    "deixe em branco",
    "pode deixar em branco",
    "nao sei informar",
]


def pergunta_de_confirmacao(rotulo, valor):
    return f"Só para confirmar: {rotulo} é {valor}?"


def interpretar_resposta(texto):
    """
    Retorna True (confirmou), False (negou) ou None (resposta
    ambígua — quem chama deve perguntar de novo, nunca assumir).
    """
    c = normalize(texto)

    if any(palavra in c for palavra in CONFIRMACAO_POSITIVA):
        return True
    if any(palavra in c for palavra in CONFIRMACAO_NEGATIVA):
        return False
    return None


def eh_pedido_de_pular(texto):
    """
    True quando a pessoa pediu explicitamente para pular a
    pergunta/campo atual (ex.: "pular", "não tenho essa informação",
    "prefiro não responder"). Quem chama (core/atendimento.py) só deve
    aceitar isso para campos marcados como não obrigatórios.
    """
    if not texto:
        return False
    c = normalize(texto)
    return any(frase in c for frase in FRASES_PULAR)
