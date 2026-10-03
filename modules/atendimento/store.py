"""Persistência local e portátil das sessões do RMD Atendimento.

O store não altera a máquina de estados. Ele fornece um contrato simples
que pode ser substituído posteriormente por PostgreSQL/Supabase sem mudar
o módulo de atendimento.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


class AtendimentoStore:
    def __init__(self, path: str | Path = "data/atendimento/sessoes.json"):
        self.path = Path(path)
        self._lock = Lock()

    def _ler(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            valor = json.loads(self.path.read_text(encoding="utf-8"))
            return valor if isinstance(valor, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _gravar(self, dados: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.path.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(self.path)

    def salvar(self, sessao: dict[str, Any]) -> dict[str, Any]:
        if not sessao.get("atendimento_id"):
            raise ValueError("atendimento_id é obrigatório")
        with self._lock:
            dados = self._ler()
            dados = [x for x in dados if x.get("atendimento_id") != sessao["atendimento_id"]]
            dados.append(dict(sessao))
            self._gravar(dados)
        return sessao

    def obter(self, atendimento_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next((x for x in self._ler() if x.get("atendimento_id") == atendimento_id), None)

    def listar(self, empresa_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            dados = self._ler()
        if empresa_id is None:
            return dados
        return [x for x in dados if x.get("empresa_id") == empresa_id]
