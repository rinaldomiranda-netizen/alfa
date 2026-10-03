"""RMD Atendimento Church no Laboratório de Módulos do ALFA.

O Church roda num servidor separado do RMD Atendimento (outra edição, outro banco de
demonstração), só neste computador (127.0.0.1):
- 8091: o sistema (edição Church, empresa de demonstração "Igreja Esperança");
- 8092: porta interna que só gera o link de entrada de cada perfil, protegida por um
  segredo que fica na pasta de dados (nenhum outro programa pede link sem ele).

O Laboratório chama abrir(perfil): se o servidor não estiver no ar, sobe em segundo
plano, pede o link do perfil e abre a janela do Edge (perfil de navegador próprio, para
a sessão não se misturar com a do RMD Atendimento).
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
PORTA = int(os.getenv("RMD_CHURCH_DEMO_PORTA", "8091"))
PORTA_LINKS = PORTA + 1
PASTA_DADOS = RAIZ / "data" / "rmd_atendimento_church_demo"
ARQUIVO_SEGREDO = PASTA_DADOS / "laboratorio_segredo.txt"
PERFIL_EDGE = RAIZ / ".alfa_edge_profile_church_demo"
CAMINHOS_EDGE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
# perfil do Laboratório -> perfil real do sistema
PERFIS = {"owner": "owner", "cliente_admin": "admin", "pastor": "supervisor", "funcionario": "atendente"}


def _no_ar() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/api/health", timeout=2) as r:
            return b"church" in r.read()
    except Exception:  # noqa: BLE001
        return False


def _abrir_janela(url: str) -> None:
    if sys.platform.startswith("win"):
        for caminho in CAMINHOS_EDGE:
            if os.path.isfile(caminho):
                PERFIL_EDGE.mkdir(parents=True, exist_ok=True)
                subprocess.Popen([caminho, f"--app={url}", "--new-window", "--start-maximized", f"--user-data-dir={PERFIL_EDGE}",
                                  "--no-first-run", "--no-default-browser-check", "--disable-sync"],  # abre direto no sistema, sem telas do Edge antes
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    import webbrowser

    webbrowser.open(url)


def _subir_servidor() -> None:
    """Sobe o servidor de demonstração do Church em segundo plano (processo próprio)."""
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    (RAIZ / "logs").mkdir(exist_ok=True)
    python = sys.executable
    if python.lower().endswith("pythonw.exe"):
        python = python[:-5] + ".exe" if os.path.isfile(python[:-5] + ".exe") else python
    log = open(RAIZ / "logs" / "church_laboratorio.log", "ab")  # noqa: SIM115 - fica aberto com o processo
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([python, "-X", "utf8", str(Path(__file__).resolve()), "--servir"], cwd=str(RAIZ),
                     stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags)
    for _ in range(60):
        if _no_ar() and ARQUIVO_SEGREDO.exists():
            return
        time.sleep(0.5)
    raise RuntimeError("O RMD Atendimento Church não subiu. Veja logs/church_laboratorio.log.")


def _pedir_link(perfil: str) -> str:
    segredo = ARQUIVO_SEGREDO.read_text(encoding="utf-8").strip()
    pedido = urllib.request.Request(f"http://127.0.0.1:{PORTA_LINKS}/link?perfil={perfil}", headers={"X-Segredo": segredo})
    with urllib.request.urlopen(pedido, timeout=10) as r:
        return json.loads(r.read())["url"]


def abrir(perfil_laboratorio: str) -> str:
    """Usado pelo Laboratório de Módulos. Devolve o endereço aberto."""
    if not _no_ar():
        _subir_servidor()
    if perfil_laboratorio == "visitante":
        url = f"http://127.0.0.1:{PORTA}/visitante?e=demonstracao"
    else:
        if perfil_laboratorio not in PERFIS:
            raise ValueError(f"Perfil desconhecido: {perfil_laboratorio}")
        url = _pedir_link(perfil_laboratorio)
    _abrir_janela(url)
    return url


# ---------------------------------------------------------------- processo do servidor
def servir() -> None:
    os.environ["RMD_EDICAO"] = "church"
    os.environ["RMD_ATENDIMENTO_DADOS"] = str(PASTA_DADOS)
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    from atendimento_web import app
    from modules.atendimento.plataforma import demo, seguranca

    p = app.plataforma()
    dados = demo.garantir_demonstracao(p)
    segredo = secrets.token_hex(24)
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SEGREDO.write_text(segredo, encoding="utf-8")

    class Links(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            perfil = self.path.partition("perfil=")[2].split("&")[0]
            if self.headers.get("X-Segredo") != segredo or perfil not in PERFIS:
                self.send_error(403)
                return
            usuario_id = demo.garantir_demonstracao(p)["usuarios"].get(PERFIS[perfil])
            if not usuario_id:
                self.send_error(404)
                return
            token = seguranca.criar_token_unico(usuario_id, dados["empresa_id"])
            corpo = json.dumps({"url": f"http://127.0.0.1:{PORTA}/entrar?token={token}"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    links = ThreadingHTTPServer(("127.0.0.1", PORTA_LINKS), Links)
    threading.Thread(target=links.serve_forever, daemon=True, name="ChurchLaboratorioLinks").start()
    servidor = app.criar_servidor("127.0.0.1", PORTA)
    print(f"[RMD Atendimento Church — laboratório] http://127.0.0.1:{PORTA}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    if "--servir" in sys.argv:
        servir()
    else:
        print(abrir(sys.argv[1] if len(sys.argv) > 1 else "cliente_admin"))
