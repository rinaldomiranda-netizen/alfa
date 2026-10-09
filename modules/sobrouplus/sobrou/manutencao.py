"""Manutenção operacional do Sobrou+.

Rotinas não destrutivas para backup, teste de restauração, integridade e retenção.
Não altera pagamentos, 2FA ou regras de negócio.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.getenv("SOBROU_DADOS", str(RAIZ / "data")))
BACKUPS = DADOS / "backups"
LOGS = RAIZ / "logs"
RETENCAO_AUDITORIA_DIAS = int(os.getenv("SOBROU_RETENCAO_AUDITORIA_DIAS", "365"))
RETENCAO_LOG_DIAS = int(os.getenv("SOBROU_RETENCAO_LOG_DIAS", "180"))
ARQUIVOS_CRITICOS = (
    "sobrou/db.py", "sobrou/nucleo.py", "sobrou/contas.py",
    "sobrou/acesso.py", "sobrou/seguranca.py", "sobrou/plataforma.py",
    "web/app.py", "web/iniciar.py", "web/static/js/painel.js",
)

def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _db_path():
    return DADOS / "sobrou.db"

def _manifest():
    itens = {}
    for rel in ARQUIVOS_CRITICOS:
        p = RAIZ / rel
        if p.exists():
            h = hashlib.sha256()
            with p.open("rb") as f:
                for bloco in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(bloco)
            itens[rel] = {"sha256": h.hexdigest(), "bytes": p.stat().st_size}
    return itens

def backup_e_teste():
    db = _db_path()
    if not db.exists():
        return {"ok": False, "erro": "Banco ainda não existe.", "restore_testado": False}
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = BACKUPS / f"sobrou-{stamp}.db"
    # Backup consistente pelo mecanismo nativo do SQLite, sem copiar uma base em uso de forma insegura.
    src = sqlite3.connect(str(db))
    dst = sqlite3.connect(str(destino))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    teste = BACKUPS / f".restore-test-{stamp}.db"
    try:
        shutil.copy2(destino, teste)
        con = sqlite3.connect(str(teste))
        integridade = con.execute("PRAGMA integrity_check").fetchone()[0]
        con.execute("PRAGMA foreign_keys=ON")
        con.close()
        ok = integridade == "ok"
    finally:
        teste.unlink(missing_ok=True)
    manifest = _manifest()
    meta = {
        "quando": agora(), "arquivo": destino.name,
        "sha256": hashlib.sha256(destino.read_bytes()).hexdigest(),
        "restore_testado": ok, "integrity_check": integridade,
        "arquivos_criticos": manifest,
    }
    (BACKUPS / f"{destino.stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": ok, "arquivo": str(destino), "restore_testado": ok, "integrity_check": integridade}

def verificar_integridade():
    db = _db_path()
    resultado = {"banco": None, "arquivos": None}
    if db.exists():
        con = sqlite3.connect(str(db))
        try:
            resultado["banco"] = con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
    manifest_path = BACKUPS / "integridade-atual.json"
    atual = _manifest()
    anterior = {}
    if manifest_path.exists():
        try:
            anterior = json.loads(manifest_path.read_text(encoding="utf-8")).get("arquivos", {})
        except Exception:
            anterior = {}
    alterados = [k for k,v in atual.items() if k in anterior and v.get("sha256") != anterior[k].get("sha256")]
    faltantes = [k for k in ARQUIVOS_CRITICOS if k not in atual]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"quando": agora(), "arquivos": atual}, ensure_ascii=False, indent=2), encoding="utf-8")
    resultado["arquivos"] = {"alterados_desde_ultima_verificacao": alterados, "faltantes": faltantes}
    return resultado

def reter_logs():
    limite_auditoria = (datetime.now(timezone.utc) - timedelta(days=RETENCAO_AUDITORIA_DIAS)).isoformat(timespec="seconds")
    removidos_auditoria = 0
    db = _db_path()
    if db.exists():
        con = sqlite3.connect(str(db))
        try:
            cur = con.execute("DELETE FROM auditoria WHERE quando < ?", (limite_auditoria,))
            removidos_auditoria = cur.rowcount
            con.commit()
        finally:
            con.close()
    removidos_arquivos = 0
    limite = datetime.now(timezone.utc) - timedelta(days=RETENCAO_LOG_DIAS)
    if LOGS.exists():
        for p in LOGS.glob("*.log"):
            try:
                if datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < limite:
                    p.unlink()
                    removidos_arquivos += 1
            except OSError:
                pass
    return {"auditoria_removida": removidos_auditoria, "arquivos_log_removidos": removidos_arquivos}

def rotina_inicial():
    """Executa somente manutenção leve no início; backup completo no máximo uma vez por dia."""
    DADOS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    integridade = verificar_integridade()
    hoje = datetime.now().strftime("%Y%m%d")
    ja_fez = any(BACKUPS.glob(f"sobrou-{hoje}-*.db"))
    backup = {"ok": True, "pulou": ja_fez}
    if not ja_fez:
        backup = backup_e_teste()
    retencao = reter_logs()
    return {"integridade": integridade, "backup": backup, "retencao": retencao}
