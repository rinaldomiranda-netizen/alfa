"""Painel web do RMD Atendimento Church no ALPHA e em modo standalone.

Segue o mesmo espírito de modules.atendimento.ui (WSGI puro, sem
depender de nenhum framework web), mas aqui a tela é de verdade
interativa: conversas, filas, serviços, fluxos, agenda, relatórios
etc. A tela (webapp.html, ao lado deste arquivo) fala com este
backend por três endpoints simples em JSON:

    GET  /api/state      -> {"online": bool, "conversas": [...], "cfg": {...}}
    POST /api/conversa   -> grava uma conversa (corpo = documento da conversa)
    POST /api/cfg        -> grava a configuração geral (corpo = documento de config)
    GET  /api/health     -> "ok" (usado por health checks de hospedagem)

Quando a beta-cloud não está configurada (ver store.py), o backend
responde normalmente mas com "online": false — a tela então funciona
só em memória, sem sincronizar entre aparelhos, e avisa isso no
indicador "Modo demonstração" do cabeçalho.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import AtendimentoChurchService

_PASTA = Path(__file__).parent
_PAGINA = _PASTA / "webapp.html"


def renderizar_painel() -> str:
    """Retorna o HTML completo da tela do RMD Atendimento Church."""
    return _PAGINA.read_text(encoding="utf-8")


def _resposta_json(start_response, dados: Any, status: str = "200 OK"):
    corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(corpo)))])
    return [corpo]


def _ler_corpo_json(environ) -> dict[str, Any]:
    try:
        tamanho = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        tamanho = 0
    bruto = environ["wsgi.input"].read(tamanho) if tamanho > 0 else b"{}"
    try:
        return json.loads(bruto or b"{}")
    except json.JSONDecodeError:
        return {}


def criar_app_wsgi(service: AtendimentoChurchService | None = None):
    """Cria o app WSGI do módulo. Uma instância própria de `service` pode
    ser passada (por exemplo, para escolher outra igreja_id ou para os
    testes injetarem um serviço falso)."""
    service = service or AtendimentoChurchService()

    def app(environ, start_response):
        metodo = environ.get("REQUEST_METHOD", "GET")
        caminho = environ.get("PATH_INFO", "/") or "/"

        if caminho == "/api/health":
            corpo = b"ok"
            start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
            return [corpo]

        if caminho == "/api/state" and metodo == "GET":
            try:
                return _resposta_json(start_response, service.estado())
            except Exception as erro:  # nunca derruba o painel por causa da nuvem
                return _resposta_json(start_response, {"erro": str(erro)}, "503 Service Unavailable")

        if caminho == "/api/conversa" and metodo == "POST":
            try:
                documento = service.salvar_conversa(_ler_corpo_json(environ))
                return _resposta_json(start_response, {"ok": True, "conversa": documento})
            except ValueError as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "400 Bad Request")
            except Exception as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "503 Service Unavailable")

        if caminho == "/api/cfg" and metodo == "POST":
            try:
                documento = service.salvar_config(_ler_corpo_json(environ))
                return _resposta_json(start_response, {"ok": True, "cfg": documento})
            except Exception as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "503 Service Unavailable")

        if caminho in ("/", "/index.html") and metodo == "GET":
            corpo = renderizar_painel().encode("utf-8")
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(corpo)))])
            return [corpo]

        corpo = b"Not Found"
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
        return [corpo]

    return app
