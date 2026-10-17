"""Abre o RMD Atendimento Church DE VERDADE (sem demonstração) neste computador.

- Banco próprio, separado da demonstração: ALFA/data/rmd_atendimento_church
- Na primeira vez cria a conta do dono (senha inicial 1234, troca obrigatória no 1º acesso)
  e a Sede (o nome se muda em Configurações).
- Fica disponível na rede Wi-Fi: celulares na mesma rede abrem o cartão do visitante pelo QR.
- Se já estiver aberto, só abre a janela de novo.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PORTA = int(os.getenv("RMD_CHURCH_PORTA", "8090"))
os.environ.setdefault("RMD_EDICAO", "church")
os.environ.setdefault("RMD_ATENDIMENTO_DADOS", str(RAIZ / "data" / "rmd_atendimento_church"))
os.environ.setdefault("RMD_OWNER_EMAIL", "rinaldomiranda@hotmail.com")
os.environ.setdefault("RMD_OWNER_NOME", "Rinaldo")
os.environ.setdefault("RMD_PRIMEIRA_EMPRESA", "Sede da Igreja")
os.environ.setdefault("RMD_PLANO", "enterprise")
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

PERFIL_EDGE = RAIZ / ".alfa_edge_profile_church"
CAMINHOS_EDGE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def ip_da_rede() -> str:
    """IP deste computador na Wi-Fi (nada é enviado: só pergunta ao sistema qual placa sairia)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def ja_aberto() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/api/health", timeout=2) as r:
            return b"church" in r.read()
    except Exception:  # noqa: BLE001
        return False


def abrir_janela(url: str) -> None:
    if sys.platform.startswith("win"):
        for caminho in CAMINHOS_EDGE:
            if os.path.isfile(caminho):
                PERFIL_EDGE.mkdir(parents=True, exist_ok=True)
                subprocess.Popen([caminho, f"--app={url}", "--new-window", "--start-maximized", f"--user-data-dir={PERFIL_EDGE}",
                                  "--no-first-run", "--no-default-browser-check", "--disable-sync"],  # abre direto no sistema, sem telas do Edge antes
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    webbrowser.open(url)


def main() -> None:
    url = f"http://{ip_da_rede()}:{PORTA}/"
    if ja_aberto():
        abrir_janela(url)
        return
    from atendimento_web import app

    p = app.plataforma()
    app._primeira_instalacao(p)
    servidor = app.criar_servidor("0.0.0.0", PORTA)
    print(f"[RMD Atendimento Church] aberto em {url} (dados em {p.banco.caminho.parent})", flush=True)
    import threading

    threading.Thread(target=lambda: (time.sleep(1.2), abrir_janela(url)), daemon=True).start()
    try:
        servidor.serve_forever()
    finally:
        servidor.parar_rotina.set()


if __name__ == "__main__":
    main()
