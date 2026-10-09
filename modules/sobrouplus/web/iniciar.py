"""Sobrou+ — modo REAL neste computador (sem dados de demonstração).

- Dados em SobrouPlus/data (banco próprio, separado de qualquer outro sistema).
- Abre na rede local (porta 8095): no celular, use o endereço mostrado (mesmo Wi-Fi).
- Instalação nova: senha temporária aleatória do proprietário aparece uma única vez no terminal e deve ser trocada.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("SOBROU_DADOS", str(RAIZ / "data"))
# Headers X-Forwarded-* so sao confiados quando um proxy reverso confiavel for explicitamente ativado.
os.environ.setdefault("SOBROU_ATRAS_DE_PROXY", "0")

from web import app  # noqa: E402
from sobrou import manutencao  # noqa: E402

DONO = os.getenv("SOBROU_DONO", "rinaldomiranda@hotmail.com")
PORTA_PREFERIDA = int(os.getenv("SOBROU_PORTA", "8095"))


def porta_livre(preferida: int) -> int:
    """Escolhe a porta preferida; se estiver ocupada, usa a próxima livre."""
    for porta in range(preferida, preferida + 20):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", porta))
            return porta
        except OSError:
            continue
        finally:
            s.close()
    raise OSError(f"Nenhuma porta livre entre {preferida} e {preferida + 19}.")


def ip_rede() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    PORTA = porta_livre(PORTA_PREFERIDA)
    if PORTA != PORTA_PREFERIDA:
        print(f" Porta {PORTA_PREFERIDA} ocupada; usando a porta livre {PORTA}.", flush=True)
    p = app.plataforma()
    manut = manutencao.rotina_inicial()
    print(f" Manutenção: backup={manut['backup'].get('ok')} restore_testado={manut['backup'].get('restore_testado', False)} integridade_db={manut['integridade'].get('banco')}", flush=True)
    dono = p.definir_dono(DONO)
    if dono.get("senha_inicial_unica"):
        print("Senha inicial única do proprietário (será exigida a troca no primeiro acesso): " + dono["senha_inicial_unica"], flush=True)
    p.rotina()
    # Publicado pela internet (túnel HTTPS): o servidor só atende o próprio computador
    # (o túnel), e ninguém no Wi-Fi acessa por HTTP sem proteção. SOBROU_REDE_LOCAL=1 libera o Wi-Fi.
    so_local = os.getenv("SOBROU_ATRAS_DE_PROXY") == "1" and os.getenv("SOBROU_REDE_LOCAL") != "1"
    servidor = app.criar_servidor("127.0.0.1" if so_local else "0.0.0.0", PORTA)
    print("=" * 60)
    print(" Sobrou+  —  Boa comida. Mais valor. Menos desperdício.")
    print(f" Neste computador:  http://127.0.0.1:{PORTA}/painel")
    publica = (os.getenv("SOBROU_URL_PUBLICA") or "").strip().rstrip("/")
    if so_local:
        print(f" No celular (internet, protegido):  {publica or 'endereço https do túnel'}")
    else:
        print(f" No celular (mesmo Wi-Fi):  http://{ip_rede()}:{PORTA}")
    print(f"   app do cliente  /   painel  /painel   entregador  /entregador")
    print(" Para fechar: feche esta janela.")
    print("=" * 60, flush=True)
    if "--sem-navegador" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PORTA}/painel")).start()
    servidor.serve_forever()
