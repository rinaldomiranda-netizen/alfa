"""Sobrou+ — modo REAL neste computador (sem dados de demonstração).

- Dados em SobrouPlus/data (banco próprio, separado de qualquer outro sistema).
- Abre na rede local (porta 8095): no celular, use o endereço mostrado (mesmo Wi-Fi).
- Primeiro acesso do administrador: e-mail do dono, senha inicial padrão, troca obrigatória.
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

from web import app  # noqa: E402

DONO = os.getenv("SOBROU_DONO", "rinaldomiranda@hotmail.com")
PORTA = int(os.getenv("SOBROU_PORTA", "8095"))


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
    p = app.plataforma()
    p.definir_dono(DONO)
    p.rotina()
    servidor = app.criar_servidor("0.0.0.0", PORTA)
    print("=" * 60)
    print(" Sobrou+  —  Boa comida. Mais valor. Menos desperdício.")
    print(f" Neste computador:  http://127.0.0.1:{PORTA}/painel")
    print(f" No celular (mesmo Wi-Fi):  http://{ip_rede()}:{PORTA}")
    print(f"   app do cliente  /   painel  /painel   entregador  /entregador")
    print(" Para fechar: feche esta janela.")
    print("=" * 60, flush=True)
    if "--sem-navegador" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PORTA}/painel")).start()
    servidor.serve_forever()
