"""Chamadas HTTP para serviços externos (mapas, pagamento, WhatsApp) — só biblioteca padrão.

Os testes trocam `Plataforma.rede` por uma função falsa; nada aqui é chamado sem as integrações estarem ligadas.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

AGENTE = "SobrouPlus/0.2 (+https://sobrou.plus; contato rinaldomiranda@hotmail.com)"


class ErroRede(Exception):
    def __init__(self, mensagem: str, status: int | None = None, corpo=None):
        super().__init__(mensagem)
        self.status = status
        self.corpo = corpo


def chamar(metodo: str, url: str, corpo=None, cabecalhos: dict | None = None, tempo: float = 12) -> dict | list:
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    cab = {"User-Agent": AGENTE, "Accept": "application/json"}
    if dados is not None:
        cab["Content-Type"] = "application/json"
    cab.update(cabecalhos or {})
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            bruto = r.read()
            return json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as e:
        try:
            detalhe = json.loads(e.read() or b"{}")
        except ValueError:
            detalhe = {}
        raise ErroRede(f"HTTP {e.code}", e.code, detalhe) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErroRede(f"Sem conexão com o serviço: {e}") from e
