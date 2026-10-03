"""Cópia do banco inteiro para FORA do servidor, uma vez por dia.

Se o servidor (ou o disco dele) se perder, a cópia do dia continua guardada
num armazenamento privado separado (Supabase Storage, pasta privada
"rmd-backups"), com os últimos 30 dias.

Configuração só por variáveis de ambiente (nunca no código):
  RMD_BACKUP_URL    endereço que recebe a cópia
  RMD_BACKUP_CHAVE  chave secreta deste servidor
  RMD_BACKUP_NOME   nome da pasta (ex.: web, church)
Sem as variáveis, nada é enviado (uso local no computador continua igual).
"""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import pasta_dados

_LOCK = threading.Lock()
INTERVALO_NOVA_TENTATIVA = timedelta(hours=1)


def _config() -> tuple[str, str, str]:
    return (os.getenv("RMD_BACKUP_URL", "").strip(), os.getenv("RMD_BACKUP_CHAVE", "").strip(),
            (os.getenv("RMD_BACKUP_NOME", "").strip().lower() or "principal"))


def configurado() -> bool:
    url, chave, _ = _config()
    return bool(url and chave)


def _arquivo_estado() -> Path:
    return pasta_dados() / "backup_externo.json"


def estado() -> dict:
    try:
        dados = json.loads(_arquivo_estado().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    return {"configurado": configurado(), "ultimo_ok": dados.get("ultimo_ok"), "ultima_tentativa": dados.get("ultima_tentativa"),
            "ultimo_erro": dados.get("ultimo_erro"), "tamanho": dados.get("tamanho"), "arquivo": dados.get("arquivo")}


def _salvar_estado(dados: dict) -> None:
    try:
        _arquivo_estado().write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _copia_compactada(caminho_banco: Path) -> bytes:
    """Cópia consistente do SQLite (API de backup do próprio SQLite), compactada."""
    temporario = pasta_dados() / "backup_externo.tmp.db"
    temporario.unlink(missing_ok=True)
    origem = sqlite3.connect(str(caminho_banco), timeout=30)
    destino = sqlite3.connect(str(temporario))
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()
    try:
        return gzip.compress(temporario.read_bytes(), compresslevel=6)
    finally:
        temporario.unlink(missing_ok=True)


def enviar_agora(caminho_banco: Path) -> dict:
    url, chave, nome = _config()
    if not (url and chave):
        raise RuntimeError("Backup externo não configurado.")
    with _LOCK:
        anterior = estado()
        registro = {k: anterior.get(k) for k in ("ultimo_ok", "tamanho", "arquivo")}
        registro["ultima_tentativa"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            conteudo = _copia_compactada(Path(caminho_banco))
            pedido = urllib.request.Request(
                url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"servico": nome}),
                data=conteudo, method="POST",
                headers={"x-rmd-chave": chave, "Content-Type": "application/gzip", "User-Agent": "RMDAtendimento-backup"},
            )
            with urllib.request.urlopen(pedido, timeout=120) as resposta:
                retorno = json.loads(resposta.read().decode("utf-8") or "{}")
            if not retorno.get("ok"):
                raise RuntimeError(retorno.get("erro") or "resposta inesperada")
            registro.update(ultimo_ok=registro["ultima_tentativa"], tamanho=len(conteudo), arquivo=retorno.get("arquivo"), ultimo_erro=None)
            print(f"[backup externo] cópia enviada: {retorno.get('arquivo')} ({len(conteudo)} bytes)", flush=True)
        except urllib.error.HTTPError as erro:
            registro["ultimo_erro"] = f"HTTP {erro.code}"
            print(f"[backup externo] falhou: HTTP {erro.code}", flush=True)
        except Exception as erro:  # noqa: BLE001 - falha no backup nunca derruba o sistema
            registro["ultimo_erro"] = str(erro)[:200] or erro.__class__.__name__
            print(f"[backup externo] falhou: {registro['ultimo_erro']}", flush=True)
        _salvar_estado(registro)
        return estado()


def talvez_enviar(caminho_banco: Path) -> None:
    """Chamado pela rotina de cada minuto: envia uma vez por dia (e tenta de novo a cada hora se falhar)."""
    if not configurado():
        return
    atual = estado()
    agora = datetime.now(timezone.utc)
    if atual["ultimo_ok"] and atual["ultimo_ok"][:10] == agora.date().isoformat():
        return
    if atual["ultima_tentativa"]:
        try:
            if agora - datetime.fromisoformat(atual["ultima_tentativa"]) < INTERVALO_NOVA_TENTATIVA:
                return
        except ValueError:
            pass
    enviar_agora(caminho_banco)
