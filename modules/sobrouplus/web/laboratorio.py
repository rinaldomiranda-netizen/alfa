"""Sobrou+ em DEMONSTRAÇÃO (para o Laboratório de Módulos do ALFA ou para mostrar a alguém).

Servidor separado, só neste computador (127.0.0.1), com banco de demonstração próprio (data/demo):
- 8096: o sistema;
- 8097: porta interna que gera o link de entrada de cada perfil, protegida por um segredo salvo na pasta de dados.
Uso:  python web/laboratorio.py <perfil>
perfis: admin_sobrou, admin_empresa, operador_empresa, financeiro, entregador, cliente, instituicao
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PORTA = int(os.getenv("SOBROU_DEMO_PORTA", "8096"))
PORTA_LINKS = PORTA + 1
PASTA = RAIZ / "data" / "demo"
SEGREDO = PASTA / "laboratorio_segredo.txt"
PERFIL_EDGE = RAIZ / ".edge_perfil_demo"
EDGE = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
PERFIS = ("admin_sobrou", "admin_empresa", "operador_empresa", "financeiro", "entregador", "cliente", "instituicao")


def _no_ar() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/api/saude", timeout=2) as r:
            return b"sobrou" in r.read()
    except Exception:  # noqa: BLE001
        return False


def _abrir_janela(url: str) -> None:
    if sys.platform.startswith("win"):
        for c in EDGE:
            if os.path.isfile(c):
                PERFIL_EDGE.mkdir(parents=True, exist_ok=True)
                subprocess.Popen([c, f"--app={url}", "--new-window", f"--user-data-dir={PERFIL_EDGE}"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    import webbrowser
    webbrowser.open(url)


def _subir() -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    (RAIZ / "logs").mkdir(exist_ok=True)
    python = sys.executable
    if python.lower().endswith("pythonw.exe") and os.path.isfile(python[:-5] + ".exe"):
        python = python[:-5] + ".exe"
    log = open(RAIZ / "logs" / "sobrou_demo.log", "ab")  # noqa: SIM115
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)) if sys.platform.startswith("win") else 0
    subprocess.Popen([python, "-X", "utf8", str(Path(__file__).resolve()), "--servir"], cwd=str(RAIZ), stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, creationflags=flags)
    for _ in range(60):
        if _no_ar() and SEGREDO.exists():
            return
        time.sleep(0.5)
    raise RuntimeError("O Sobrou+ (demonstração) não subiu. Veja logs/sobrou_demo.log.")


def abrir(perfil: str) -> str:
    if perfil not in PERFIS:
        raise ValueError(f"Perfil desconhecido: {perfil}")
    if not _no_ar():
        _subir()
    pedido = urllib.request.Request(f"http://127.0.0.1:{PORTA_LINKS}/link?perfil={perfil}",
                                    headers={"X-Segredo": SEGREDO.read_text(encoding="utf-8").strip()})
    with urllib.request.urlopen(pedido, timeout=10) as r:
        url = json.loads(r.read())["url"]
    _abrir_janela(url)
    return url


def servir() -> None:
    os.environ["SOBROU_DADOS"] = str(PASTA)
    sys.path.insert(0, str(RAIZ))
    from sobrou import demo, seguranca
    from web import app

    p = app.plataforma()
    demo.garantir_demonstracao(p)
    segredo = secrets.token_hex(24)
    PASTA.mkdir(parents=True, exist_ok=True)
    SEGREDO.write_text(segredo, encoding="utf-8")

    class Links(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            perfil = self.path.partition("perfil=")[2].split("&")[0]
            try:
                segredo_atual = SEGREDO.read_text(encoding="utf-8").strip()
            except OSError:
                segredo_atual = ""
            if not segredo_atual or self.headers.get("X-Segredo") != segredo_atual or perfil not in PERFIS:
                self.send_error(403)
                return
            uid = demo.garantir_demonstracao(p).get(perfil)
            if not uid:
                self.send_error(404)
                return
            corpo = json.dumps({"url": f"http://127.0.0.1:{PORTA}/entrar?token={seguranca.criar_token_unico(uid, None)}"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", PORTA_LINKS), Links).serve_forever, daemon=True).start()
    print(f"[Sobrou+ demonstração] http://127.0.0.1:{PORTA}", flush=True)
    app.criar_servidor("127.0.0.1", PORTA).serve_forever()


if __name__ == "__main__":
    if "--servir" in sys.argv:
        servir()
    else:
        print(abrir(sys.argv[1] if len(sys.argv) > 1 else "cliente"))
