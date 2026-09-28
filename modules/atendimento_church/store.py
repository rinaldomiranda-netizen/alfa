"""Persistência em nuvem (beta-cloud/Supabase) do RMD Atendimento Church.

Guarda dois tipos de documento, no mesmo espírito do AtendimentoStore
local original (modules/atendimento/store.py), mas compartilhados na
nuvem para sincronizar entre aparelhos e congregações:

    church_conversations  — uma linha por conversa (id, igreja_id, data jsonb)
    church_config         — configuração geral da igreja (id fixo "geral", data jsonb)

Acessa essas tabelas pela API REST do Supabase (PostgREST) usando a
chave "service_role" do projeto beta-cloud — uma chave que só pode
viver no servidor/backend deste módulo, NUNCA em código que roda no
navegador (por isso as tabelas têm RLS ligado e sem nenhuma policy:
só a service_role consegue ler/gravar). Sem essa chave configurada, o
módulo continua funcionando normalmente, só que "offline": os dados
ficam só na memória da página aberta, sem sincronizar entre
aparelhos (ver ui.py).

Configuração (variáveis de ambiente, no mesmo .env do ALFA):
    BETA_CLOUD_PROJECT_URL          já usado pelo ALFA para a beta-cloud
    BETA_CLOUD_SERVICE_ROLE_KEY     chave "service_role" do projeto
                                     beta-cloud, em Project Settings > API
                                     no painel do Supabase. Pegue essa
                                     chave você mesmo e cole no seu .env
                                     local — nunca compartilhe com
                                     ninguém, nem aqui no código.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - requests já é usado em voice/tts/elevenlabs_tts.py
    requests = None

TABELA_CONVERSAS = "church_conversations"
TABELA_CONFIG = "church_config"
CONFIG_ID_GERAL = "geral"
IGREJA_PADRAO = "default"
LIMITE_PADRAO_CONVERSAS = 200
LIMITE_MAXIMO_CONVERSAS = 2000


class ChurchCloudIndisponivel(Exception):
    """Levantado quando a beta-cloud não está configurada ou não responde."""


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChurchStore:
    """Acesso às tabelas church_* do beta-cloud (Supabase) via REST."""

    def __init__(
        self,
        url: str | None = None,
        service_role_key: str | None = None,
        igreja_id: str = IGREJA_PADRAO,
        timeout: float = 8.0,
    ):
        self.url = (url or os.environ.get("BETA_CLOUD_PROJECT_URL") or "").rstrip("/")
        self.service_role_key = service_role_key or os.environ.get("BETA_CLOUD_SERVICE_ROLE_KEY") or ""
        self.igreja_id = igreja_id or IGREJA_PADRAO
        self.timeout = timeout

    @property
    def configurado(self) -> bool:
        return bool(self.url and self.service_role_key and requests is not None)

    def _cabecalhos(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }

    def _rest(self, tabela: str) -> str:
        return f"{self.url}/rest/v1/{tabela}"

    def _exigir_configurado(self) -> None:
        if not self.configurado:
            raise ChurchCloudIndisponivel(
                "beta-cloud não configurada: defina BETA_CLOUD_PROJECT_URL e "
                "BETA_CLOUD_SERVICE_ROLE_KEY no .env para sincronizar o "
                "RMD Atendimento Church entre aparelhos."
            )

    def listar_conversas(self, limit: int = LIMITE_PADRAO_CONVERSAS) -> list[dict[str, Any]]:
        self._exigir_configurado()
        limite = max(1, min(int(limit or LIMITE_PADRAO_CONVERSAS), LIMITE_MAXIMO_CONVERSAS))
        resposta = requests.get(
            self._rest(TABELA_CONVERSAS),
            headers=self._cabecalhos(),
            params={
                "igreja_id": f"eq.{self.igreja_id}",
                "select": "data",
                "order": "updated_at.desc",
                "limit": str(limite),
            },
            timeout=self.timeout,
        )
        resposta.raise_for_status()
        return [linha["data"] for linha in resposta.json()]

    def salvar_conversa(self, documento: dict[str, Any]) -> dict[str, Any]:
        self._exigir_configurado()
        conversa_id = documento.get("id")
        if not conversa_id:
            raise ValueError("a conversa precisa ter 'id'")
        corpo = {"id": str(conversa_id), "igreja_id": self.igreja_id, "data": documento}
        resposta = requests.post(
            self._rest(TABELA_CONVERSAS),
            headers={**self._cabecalhos(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=corpo,
            timeout=self.timeout,
        )
        resposta.raise_for_status()
        return documento

    def obter_config(self) -> dict[str, Any] | None:
        self._exigir_configurado()
        resposta = requests.get(
            self._rest(TABELA_CONFIG),
            headers=self._cabecalhos(),
            params={"id": f"eq.{CONFIG_ID_GERAL}", "igreja_id": f"eq.{self.igreja_id}", "select": "data"},
            timeout=self.timeout,
        )
        resposta.raise_for_status()
        linhas = resposta.json()
        return linhas[0]["data"] if linhas else None

    def salvar_config(self, documento: dict[str, Any]) -> dict[str, Any]:
        self._exigir_configurado()
        corpo = {"id": CONFIG_ID_GERAL, "igreja_id": self.igreja_id, "data": documento}
        resposta = requests.post(
            self._rest(TABELA_CONFIG),
            headers={**self._cabecalhos(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=corpo,
            timeout=self.timeout,
        )
        resposta.raise_for_status()
        return documento

    def exportar_backup(self) -> dict[str, Any]:
        """Pacote completo (conversas + configuração) desta igreja, para download."""
        self._exigir_configurado()
        return {
            "igreja_id": self.igreja_id,
            "gerado_em": _agora_iso(),
            "conversas": self.listar_conversas(limit=LIMITE_MAXIMO_CONVERSAS),
            "config": self.obter_config(),
        }
