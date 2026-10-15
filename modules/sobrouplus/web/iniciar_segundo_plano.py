"""Inicia o servidor real do Sobrou+ sem prender o servidor à janela do lançador."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SERVIDOR = RAIZ / "web" / "iniciar.py"


def _respondendo(porta: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/saude", timeout=1) as resposta:
            return resposta.status == 200 and b"sobrou" in resposta.read().lower()
    except (OSError, urllib.error.URLError):
        return False


def _porta_livre(preferida: int) -> int:
    for porta in range(preferida, preferida + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", porta))
                return porta
            except OSError:
                continue
    raise OSError(f"Nao ha porta livre entre {preferida} e {preferida + 19}.")


def iniciar() -> int:
    porta_preferida = int(os.getenv("SOBROU_PORTA", "8095"))
    if _respondendo(porta_preferida):
        webbrowser.open(f"http://127.0.0.1:{porta_preferida}/painel")
        return 0

    porta = _porta_livre(porta_preferida)
    ambiente = os.environ.copy()
    ambiente["SOBROU_PORTA"] = str(porta)
    python = sys.executable
    if python.lower().endswith("pythonw.exe") and Path(python[:-5] + ".exe").is_file():
        python = python[:-5] + ".exe"

    pasta_logs = RAIZ / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    arquivo_log = pasta_logs / "sobrou_real_background.log"
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

    with arquivo_log.open("ab") as log:
        processo = subprocess.Popen(
            [python, "-X", "utf8", str(SERVIDOR), "--sem-navegador"],
            cwd=str(RAIZ),
            env=ambiente,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=flags,
        )

    url = f"http://127.0.0.1:{porta}/painel"
    for _ in range(60):
        if _respondendo(porta):
            webbrowser.open(url)
            return 0
        if processo.poll() is not None:
            print(f"O servidor encerrou ao iniciar. Consulte {arquivo_log}.", flush=True)
            return processo.returncode or 1
        time.sleep(0.5)

    print(f"O servidor nao respondeu. Consulte {arquivo_log}.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(iniciar())
