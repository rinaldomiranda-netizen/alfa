"""Fachada do RMD Atendimento Church dentro da plataforma ALPHA.

Segue o mesmo papel de modules.atendimento.AtendimentoModule: o Alpha
Core não precisa conhecer os detalhes do banco/nuvem, só chama esta
fachada. Diferente do RMD Atendimento original — que reaproveita o
motor de entrevista por voz de core.atendimento, feito para o
atendimento presencial com a BETA —, o Atendimento Church é uma
central multicanal (WhatsApp, site, telefone, presencial) com filas e
equipe humana. Por isso ele não depende de core.atendimento: tem seu
próprio contrato simples aqui dentro.
"""
from __future__ import annotations

from typing import Any

from .store import ChurchStore

CONFIG_PADRAO: dict[str, Any] = {
    "co": "Minha Igreja",
    "hor": "Segunda a sexta, 9h às 18h.",
    "boas": "Paz do Senhor! Recebemos sua mensagem e já vamos atender você.",
}


class AtendimentoChurchModule:
    """Fachada do módulo RMD Atendimento Church."""

    module_id = "rmd-atendimento-church"
    version = "1.0.0"

    def __init__(self, store: ChurchStore | None = None):
        self.store = store or ChurchStore()

    @property
    def online(self) -> bool:
        return self.store.configurado

    def status(self) -> dict[str, Any]:
        return {
            "id": self.module_id,
            "versao": self.version,
            "online": self.online,
        }

    def listar_conversas(self) -> list[dict[str, Any]]:
        if not self.online:
            return []
        return self.store.listar_conversas()

    def salvar_conversa(self, documento: dict[str, Any]) -> dict[str, Any]:
        return self.store.salvar_conversa(documento)

    def obter_config(self) -> dict[str, Any]:
        if not self.online:
            return dict(CONFIG_PADRAO)
        config = self.store.obter_config()
        return config if config is not None else dict(CONFIG_PADRAO)

    def salvar_config(self, documento: dict[str, Any]) -> dict[str, Any]:
        return self.store.salvar_config(documento)
