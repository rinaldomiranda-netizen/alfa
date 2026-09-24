"""Serviço de aplicação do RMD Atendimento.

Orquestra o motor existente e a persistência sem colocar regras de negócio
na interface. A empresa é obrigatória para persistência multi-tenant.
"""
from __future__ import annotations

from typing import Any

from .modulo import AtendimentoModule
from .store import AtendimentoStore


class AtendimentoService:
    def __init__(self, store: AtendimentoStore | None = None, modulo: AtendimentoModule | None = None):
        self.store = store or AtendimentoStore()
        self.modulo = modulo or AtendimentoModule()

    def iniciar(self, empresa_id: str, roteiro: list[dict[str, Any]], saudacao: str | None = None):
        if not empresa_id:
            raise ValueError("empresa_id é obrigatório")
        mensagem = self.modulo.iniciar(roteiro, saudacao=saudacao)
        self._salvar(empresa_id)
        return mensagem

    def responder(self, empresa_id: str, texto: str):
        if not empresa_id:
            raise ValueError("empresa_id é obrigatório")
        resultado = self.modulo.responder(texto)
        self._salvar(empresa_id)
        return resultado

    def finalizar(self, empresa_id: str):
        if not empresa_id:
            raise ValueError("empresa_id é obrigatório")

        # O motor limpa o atendimento durante finalizar(); capturamos o ID
        # antes da chamada para manter o histórico com a referência real.
        atendimento_id = self.modulo.status().get("atendimento_id")
        respostas = self.modulo.finalizar()
        if atendimento_id:
            self.store.salvar({
                "atendimento_id": atendimento_id,
                "empresa_id": empresa_id,
                "estado": "FINALIZADO",
                "respostas": respostas,
            })
        return respostas

    def _salvar(self, empresa_id: str):
        s = self.modulo.status()
        self.store.salvar({
            "atendimento_id": s["atendimento_id"] or f"sessao-{id(self.modulo)}",
            "empresa_id": empresa_id,
            "nome_pessoa": s["nome_pessoa"],
            "estado": s["estado"],
            "status": s,
        })
