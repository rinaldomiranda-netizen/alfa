"""Recepção por roteiro (protocolo do ALFA que já existia em core/atendimento.py).

Continua funcionando igual, agora protegida por login e sempre na
empresa da sessão (a empresa nunca vem do navegador). Depende das
bibliotecas de câmera/tela do ALFA; se elas não estiverem instaladas
(ex.: RMD Atendimento rodando separado), só esta tela fica indisponível
— o resto da plataforma continua funcionando.
"""
from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

from modules.atendimento.plataforma.db import pasta_dados

SESSOES: dict[str, object] = {}
EMPRESAS: dict[str, str] = {}
LOCK = threading.RLock()
_STORE = None


class RecepcaoIndisponivel(RuntimeError):
    pass


def caminho_store() -> Path:
    return Path(os.getenv("ATENDIMENTO_STORE_PATH", str(pasta_dados() / "recepcao_sessoes.json")))


def _store():
    global _STORE
    if _STORE is None:
        from modules.atendimento.store import AtendimentoStore

        _STORE = AtendimentoStore(caminho_store())
    return _STORE


def definir_store(store) -> None:
    global _STORE
    _STORE = store


def _dependencias():
    try:
        from core.roteiro_pesquisa import roteiro_nova_entrevista
        from modules.atendimento.modulo import AtendimentoModule
        from modules.atendimento.service import AtendimentoService
    except Exception as erro:  # noqa: BLE001 - biblioteca opcional ausente
        raise RecepcaoIndisponivel(
            "A Recepção por roteiro precisa das bibliotecas do ALFA (câmera/tela). Abra pelo ALFA para usar esta tela."
        ) from erro
    return roteiro_nova_entrevista, AtendimentoModule, AtendimentoService


def _status(service) -> dict:
    s = service.modulo.status()
    return {k: s[k] for k in ("id", "versao", "ativo", "estado", "atendimento_id", "nome_pessoa")}


def _resposta(service, resultado) -> dict:
    if isinstance(resultado, dict):
        mensagem, proxima, acao = resultado.get("mensagem", ""), resultado.get("proxima_pergunta"), resultado.get("acao")
    else:
        mensagem, proxima, acao = str(resultado), None, None
    if not proxima and service.modulo.ativo:
        proxima = service.modulo.engine.pergunta_atual()
    return {"mensagem": mensagem, "proxima_pergunta": proxima, "acao": acao, "status": _status(service)}


def iniciar(empresa_id: str) -> dict:
    roteiro, Modulo, Servico = _dependencias()
    session_id = uuid.uuid4().hex
    service = Servico(store=_store(), modulo=Modulo(camera_module=None, pesquisa_app=None))
    mensagem = service.iniciar(empresa_id, roteiro())
    with LOCK:
        SESSOES[session_id] = service
        EMPRESAS[session_id] = empresa_id
    return {"session_id": session_id, "mensagem": mensagem, "proxima_pergunta": service.modulo.engine.pergunta_atual(),
            "status": _status(service)}


def _sessao(session_id: str, empresa_id: str):
    with LOCK:
        service = SESSOES.get(session_id)
        dona = EMPRESAS.get(session_id)
    if service is None or dona != empresa_id:
        raise KeyError("Sessão inválida.")
    return service


def responder(session_id: str, empresa_id: str, texto: str) -> dict:
    service = _sessao(session_id, empresa_id)
    resultado = service.responder(empresa_id, texto)
    if (isinstance(resultado, dict) and resultado.get("acao") == "proxima_pergunta"
            and resultado.get("proxima_pergunta") == "Qual é o seu nome completo?" and service.modulo.engine.nome_pessoa):
        interno = service.responder(empresa_id, service.modulo.engine.nome_pessoa)
        if isinstance(interno, dict) and interno.get("acao") == "confirmar":
            interno = service.responder(empresa_id, "sim")
        resultado = interno
    return _resposta(service, resultado)


def finalizar(session_id: str, empresa_id: str) -> dict:
    service = _sessao(session_id, empresa_id)
    return {"ok": True, "respostas": service.finalizar(empresa_id), "status": _status(service)}


def historico(empresa_id: str) -> list[dict]:
    return list(reversed(_store().listar(empresa_id)[-100:]))
