"""Serviço de aplicação do RMD Atendimento Church.

Espelha modules.atendimento.service.AtendimentoService: a fachada
(AtendimentoChurchModule) cuida só do motor/persistência; este
serviço é o ponto único chamado pela API web (ui.py) e, no futuro,
pelo Alpha Core — sempre isolando por igreja_id para nunca misturar
dados de igrejas/congregações diferentes.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from . import whatsapp
from .modulo import AtendimentoChurchModule
from .store import LIMITE_MAXIMO_CONVERSAS, LIMITE_PADRAO_CONVERSAS, ChurchStore

_FUSO_BRASIL = timezone(timedelta(hours=-3))


class AtendimentoChurchService:
    def __init__(self, igreja_id: str = "default", modulo: AtendimentoChurchModule | None = None):
        if not igreja_id:
            raise ValueError("igreja_id é obrigatório")
        self.igreja_id = igreja_id
        self.modulo = modulo or AtendimentoChurchModule(store=ChurchStore(igreja_id=igreja_id))

    def estado(self, limit: int = LIMITE_PADRAO_CONVERSAS) -> dict[str, Any]:
        """Estado completo consumido pela tela (GET /api/state)."""
        status = self.modulo.status()
        return {
            "online": status["online"],
            "conversas": self.modulo.listar_conversas(limit=limit),
            "cfg": self.modulo.obter_config(),
            "zap": whatsapp.configurado(),
        }

    def salvar_conversa(self, documento: dict[str, Any]) -> dict[str, Any]:
        return self.modulo.salvar_conversa(documento)

    def salvar_config(self, documento: dict[str, Any]) -> dict[str, Any]:
        return self.modulo.salvar_config(documento)

    def exportar_backup(self) -> dict[str, Any]:
        """Gera o pacote de backup e registra a data na configuração da igreja."""
        pacote = self.modulo.exportar_backup()
        try:
            cfg = dict(self.modulo.obter_config())
            cfg["ultimo_backup"] = pacote["gerado_em"]
            self.modulo.salvar_config(cfg)
        except Exception:
            pass  # o download já foi gerado; só a "última vez" não foi anotada
        return pacote

    def registrar_mensagem_whatsapp(self, telefone: str, nome: str, texto: str) -> dict[str, Any]:
        """Cria ou atualiza a conversa desta pessoa a partir de uma mensagem
        recebida pelo WhatsApp (webhook da Meta). Reabre a conversa quando
        ela já estava encerrada, para ninguém ficar sem resposta."""
        hora = datetime.now(_FUSO_BRASIL).strftime("%H:%M")
        agora_ms = int(time.time() * 1000)
        existentes = self.modulo.listar_conversas(limit=LIMITE_MAXIMO_CONVERSAS)
        atual = next((c for c in existentes if c.get("tel") == telefone), None)
        if atual:
            mensagens = list(atual.get("m") or [])
            mensagens.append(["p", texto, hora])
            atual["m"] = mensagens
            atual["t"] = agora_ms
            if atual.get("st") == "enc":
                atual["st"] = "espera"
                atual["w"] = 1
            documento = atual
        else:
            documento = {
                "id": f"wa-{telefone}-{agora_ms}",
                "n": nome or telefone,
                "c": "WhatsApp",
                "f": "Secretaria",
                "a": "Mensagem via WhatsApp",
                "st": "espera",
                "w": 1,
                "ag": "",
                "tel": telefone,
                "t": agora_ms,
                "m": [["p", texto, hora]],
            }
        return self.modulo.salvar_conversa(documento)

    def enviar_whatsapp(self, telefone: str, texto: str) -> bool:
        """Envia uma mensagem de verdade pelo WhatsApp (False se não configurado)."""
        return whatsapp.enviar_mensagem(telefone, texto)
