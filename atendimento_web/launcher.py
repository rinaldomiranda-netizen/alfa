"""Abre o RMD Atendimento a partir do ALFA.

- Sobe o servidor dentro do próprio processo do ALFA, só para este
  computador (127.0.0.1). Se a porta 8080 estiver ocupada, usa outra livre.
- Entra automaticamente com o perfil escolhido no Laboratório de
  Módulos (link de uso único, vale 90 segundos).
- Abre numa janela própria do ALFA (Microsoft Edge em modo aplicativo,
  sem barra de endereço), igual ao Dashboard. Sem o Edge, usa o
  navegador padrão.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from atendimento_web import app as servidor_web
from modules.atendimento.plataforma import demo, permissoes, seguranca

RAIZ = Path(__file__).resolve().parent.parent
PERFIL_EDGE = RAIZ / ".alfa_edge_profile"
CAMINHOS_EDGE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

_SERVIDOR = None
_LOCK = threading.Lock()


def _porta_livre(preferida: int) -> int:
    for porta in (preferida, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
            try:
                teste.bind(("127.0.0.1", porta))
                return teste.getsockname()[1]
            except OSError:
                continue
    raise OSError("Nenhuma porta livre para o RMD Atendimento.")


def garantir_servidor() -> str:
    """Sobe o servidor (uma vez) e devolve o endereço base."""
    global _SERVIDOR
    with _LOCK:
        if _SERVIDOR is None:
            porta = _porta_livre(servidor_web.PORT)
            _SERVIDOR = servidor_web.criar_servidor("127.0.0.1", porta)
            threading.Thread(target=_SERVIDOR.serve_forever, daemon=True, name="RMDAtendimentoWeb").start()
        return f"http://127.0.0.1:{_SERVIDOR.server_address[1]}"


def link_de_acesso(perfil_laboratorio: str) -> str:
    perfil = permissoes.PERFIS_LABORATORIO.get(perfil_laboratorio)
    if not perfil:
        raise ValueError(f"Perfil desconhecido: {perfil_laboratorio}")
    base = garantir_servidor()
    dados = demo.garantir_demonstracao(servidor_web.plataforma())
    usuario_id = dados["usuarios"].get(perfil)
    if not usuario_id:
        raise RuntimeError(f"Usuário de demonstração do perfil {perfil} não encontrado.")
    token = seguranca.criar_token_unico(usuario_id, dados["empresa_id"])
    return f"{base}/entrar?token={token}"


def abrir_janela(url: str) -> None:
    if sys.platform.startswith("win"):
        for caminho in CAMINHOS_EDGE:
            if os.path.isfile(caminho):
                PERFIL_EDGE.mkdir(parents=True, exist_ok=True)
                subprocess.Popen(
                    [caminho, f"--app={url}", "--new-window", "--start-maximized", f"--user-data-dir={PERFIL_EDGE}"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return
    webbrowser.open(url)


def abrir_para_perfil(perfil_laboratorio: str) -> str:
    """Usado pelo Laboratório de Módulos do ALFA. Devolve o endereço base."""
    url = link_de_acesso(perfil_laboratorio)
    abrir_janela(url)
    return url.split("/entrar", 1)[0]
