"""
Identidade de quem está sendo ATENDIDO pela BETA — diferente da
identidade de quem OPERA o computador (Rinaldo, ver
core/personality.py e core/alfa_core.py).

Pessoas da família são reconhecidas só pelo NOME que a própria pessoa
diz e confirma (como qualquer outro dado do atendimento) — não há
biometria nem verificação real de identidade aqui.

Visitantes (qualquer nome fora da lista de conhecidos) só têm acesso
a perguntas do roteiro marcadas como `"requer_autorizacao": True`
(ver core/atendimento.py) se disserem a frase de autorização
definida pelo Rinaldo. Isso é uma barreira simples de conversa, não
um segundo fator de autenticação de verdade — e NUNCA concede
privilégios de sistema: mesmo autorizada, uma pessoa atendida
continua sem acesso ao roteador de comandos normal
(core/router.py) enquanto o atendimento estiver ativo.
"""

from core.normalizer import normalize

PESSOAS_CONHECIDAS = ["rinaldo", "marlene", "lucas felipe", "cassiano"]

FRASE_AUTORIZACAO = "o alpha autoriza"


def eh_pessoa_conhecida(nome):
    if not nome:
        return False
    nome_normalizado = normalize(nome)
    if not nome_normalizado:
        return False
    return any(
        conhecido in nome_normalizado or nome_normalizado in conhecido
        for conhecido in PESSOAS_CONHECIDAS
    )


def contem_frase_autorizacao(texto):
    if not texto:
        return False
    return FRASE_AUTORIZACAO in normalize(texto)
