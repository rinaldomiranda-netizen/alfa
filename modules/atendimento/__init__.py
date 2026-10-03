"""Módulo RMD Atendimento para o ALFA.

- ``modules.atendimento.plataforma``: a plataforma completa (17 telas,
  banco de dados, login, perfis, WhatsApp...). Só biblioteca padrão.
- ``AtendimentoModule``: fachada do protocolo de recepção por roteiro
  que já existia em ``core.atendimento`` (usado na tela de Recepção).

O import de ``AtendimentoModule`` é feito sob demanda: assim a
plataforma roda separada do ALFA sem precisar das bibliotecas de
câmera/mouse que o protocolo de recepção usa.
"""

__all__ = ["AtendimentoModule"]


def __getattr__(nome):
    if nome == "AtendimentoModule":
        from .modulo import AtendimentoModule

        return AtendimentoModule
    raise AttributeError(nome)
