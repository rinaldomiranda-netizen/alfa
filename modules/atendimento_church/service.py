"""Serviço de aplicação do RMD Atendimento Church.

Espelha modules.atendimento.service.AtendimentoService: a fachada
(AtendimentoChurchModule) cuida só do motor/persistência; este
serviço é o ponto único chamado pela API web (ui.py) e, no futuro,
pelo Alpha Core — sempre isolando por igreja_id para nunca misturar
dados de igrejas/congregações diferentes.
"""
from __future__ import annotations

from typing import Any

from .modulo import AtendimentoChurchModule
from .store import ChurchStore


class AtendimentoChurchService:
    def __init__(self, igreja_id: str = "default", modulo: AtendimentoChurchModule | None = None):
        if not igreja_id:
            raise ValueError("igreja_id é obrigatório")
        self.igreja_id = igreja_id
        self.modulo = modulo or AtendimentoChurchModule(store=ChurchStore(igreja_id=igreja_id))

    def estado(self) -> dict[str, Any]:
        """Estado completo consumido pela tela (GET /api/state)."""
        status = self.modulo.status()
        return {
            "online": status["online"],
            "conversas": self.modulo.listar_conversas(),
            "cfg": self.modulo.obter_config(),
        }

    def salvar_conversa(self, documento: dict[str, Any]) -> dict[str, Any]:
        return self.modulo.salvar_conversa(documento)

    def salvar_config(self, documento: dict[str, Any]) -> dict[str, Any]:
        return self.modulo.salvar_config(documento)
