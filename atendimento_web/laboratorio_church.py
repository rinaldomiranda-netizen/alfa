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
import socket
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
ARQUIVO_PORTA = PASTA_DADOS / "laboratorio_porta.txt"
ARQUIVO_SEGREDO = PASTA_DADOS / "laboratorio_segredo.txt"
PERFIL_EDGE = RAIZ / ".alfa_edge_profile_church_demo"
CAMINHOS_EDGE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
# perfil do Laboratório -> perfil real do sistema
PERFIS = {"owner": "owner", "cliente_admin": "admin", "pastor": "supervisor", "funcionario": "atendente"}


def _porta_ocupada(porta: int) -> bool:
    """True se alguém já atende nessa porta (o Windows deixa dois programas dividirem a mesma porta e confundir tudo)."""
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
            return True
    except OSError:
        return False


def _usar_porta(porta: int) -> None:
    global PORTA, PORTA_LINKS
    PORTA, PORTA_LINKS = porta, porta + 1


def _escolher_porta_livre() -> int:
    """Primeira dupla de portas (sistema + links) que ninguém está usando, a partir de 8091."""
    for base in range(PORTA, PORTA + 40, 2):
        if not _porta_ocupada(base) and not _porta_ocupada(base + 1):
            return base
    raise RuntimeError("Nenhuma porta livre para o RMD Atendimento Church.")


def _carregar_porta() -> None:
    """Usa a porta em que o servidor do Church deste computador foi aberto da última vez."""
    try:
        _usar_porta(int(ARQUIVO_PORTA.read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        pass


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
    flags, inicio = 0, None
    if sys.platform.startswith("win"):
        # Programa "sem janela" (pythonw) quando existe. Antes, com DETACHED_PROCESS, o python do venv (que abre o
        # python de verdade como filho) ganhava um console preto próprio — a "tela de bloco de notas" que sobrava.
        sem_janela = python[:-4] + "w.exe" if python.lower().endswith("python.exe") else python
        python = sem_janela if os.path.isfile(sem_janela) else python
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        inicio = subprocess.STARTUPINFO()
        inicio.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        inicio.wShowWindow = 0  # SW_HIDE
    _usar_porta(_escolher_porta_livre())  # nunca divide a porta com outro programa
    ARQUIVO_PORTA.write_text(str(PORTA), encoding="utf-8")
    ARQUIVO_SEGREDO.unlink(missing_ok=True)
    log = open(RAIZ / "logs" / "church_laboratorio.log", "ab")  # noqa: SIM115 - fica aberto com o processo
    ambiente = {**os.environ, "RMD_FECHAR_SEM_JANELA": "1", "RMD_CHURCH_DEMO_PORTA": str(PORTA)}  # o servidor se encerra quando a janela é fechada
    subprocess.Popen([python, "-X", "utf8", str(Path(__file__).resolve()), "--servir"], cwd=str(RAIZ), env=ambiente,
                     stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags, startupinfo=inicio)
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
    _carregar_porta()
    if not (_no_ar() and ARQUIVO_SEGREDO.exists()):
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
def _liberar_portas() -> None:
    """Encerra servidores antigos do Church que ficaram escondidos nas portas deste servidor (o Windows deixa dois
    programas dividirem a mesma porta e o pedido cai no errado). Só mexe em python do próprio Church e registra
    no log quem estava na porta."""
    if not sys.platform.startswith("win"):
        return
    meu, pai = os.getpid(), os.getppid()
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"Get-NetTCPConnection -State Listen -LocalPort {PORTA},{PORTA_LINKS} | ForEach-Object {{"
        "$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$_.OwningProcess);"
        "Write-Output ('porta '+$_.LocalPort+' pid '+$_.OwningProcess+' '+$p.Name+' '+$p.CommandLine);"
        f"if ($_.OwningProcess -ne {meu} -and $_.OwningProcess -ne {pai} -and $p.Name -match 'python' -and "
        "$p.CommandLine -match 'laboratorio_church|atendimento_web|iniciar_church') {"
        "Stop-Process -Id $_.OwningProcess -Force; Write-Output 'encerrado' } }"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script], capture_output=True,
                           text=True, timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print("[laboratório] portas antes de subir:", (r.stdout or "").strip() or "livres", flush=True)
    except Exception as erro:  # noqa: BLE001
        print(f"[laboratório] não consegui conferir as portas: {erro!r}", flush=True)
    time.sleep(0.8)


def _reiniciar_alfa_uma_vez() -> None:
    """O ALFA que já estava aberto guardou a versão antiga deste arquivo na memória. Reinicia o ALFA uma única vez
    (mesmo que o atalho "ALFA - Reiniciar") para carregar a versão nova; depois disso não mexe mais."""
    marca = PASTA_DADOS / "alfa_reiniciado_20261017.txt"
    reiniciar = RAIZ.parent / "REINICIAR_ALFA.vbs"
    if marca.exists() or ARQUIVO_PORTA.exists() or not reiniciar.is_file() or not sys.platform.startswith("win"):
        return
    try:
        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        marca.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        subprocess.Popen(["wscript", "//nologo", str(reiniciar)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print("[laboratório] ALFA antigo na memória: reiniciando o ALFA uma vez.", flush=True)
    except Exception as erro:  # noqa: BLE001
        print(f"[laboratório] não consegui reiniciar o ALFA: {erro!r}", flush=True)


def servir() -> None:
    _liberar_portas()
    _reiniciar_alfa_uma_vez()
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
