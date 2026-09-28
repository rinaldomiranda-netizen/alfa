"""Painel web do RMD Atendimento Church no ALPHA e em modo standalone.

Segue o mesmo espírito de modules.atendimento.ui (WSGI puro, sem
depender de nenhum framework web), com alguns recursos "de verdade"
além do miolo original:

    GET  /api/state       -> {"online": bool, "conversas": [...], "cfg": {...}}
    GET  /api/stream      -> a mesma coisa que /api/state, mas em tempo real
                              (Server-Sent Events): a tela recebe um evento
                              assim que algo muda, sem ficar perguntando de
                              tempos em tempos. Se a hospedagem não suportar
                              conexões de longa duração, a tela detecta e
                              volta sozinha a perguntar de tempos em tempos.
    POST /api/conversa   -> grava uma conversa (corpo = documento da conversa)
    POST /api/cfg        -> grava a configuração geral (corpo = documento de config)
    GET  /api/backup     -> baixa um arquivo .json com todas as conversas e a
                              configuração desta igreja (backup de verdade)
    GET  /api/health     -> "ok" (usado por health checks de hospedagem)
    GET  /api/whatsapp/webhook  -> confirmação do webhook para a Meta
    POST /api/whatsapp/webhook  -> recebe mensagens do WhatsApp (Meta)
    POST /api/whatsapp/enviar   -> envia uma mensagem de verdade pelo WhatsApp

O webhook do WhatsApp (ver whatsapp.py) fica de fora da exigência de
CHURCH_API_TOKEN, porque quem chama é a própria Meta, não a tela — a
verificação dele é o handshake da Meta (GET) e, opcionalmente, a
assinatura X-Hub-Signature-256 (WHATSAPP_APP_SECRET).

Multi-igreja: cada igreja é identificada por um "igreja_id", passado
como `?igreja=<id>` na própria URL (a tela lê isso de `window.IGREJA_ID`,
que este arquivo grava na página quando ela é servida com `?igreja=...`).
Sem esse parâmetro, tudo continua funcionando como uma igreja só
("default") — não precisa configurar nada para o caso mais comum.

Segurança opcional: se a variável de ambiente CHURCH_API_TOKEN estiver
definida, todas as rotas de dados (state, stream, conversa, cfg, backup)
passam a exigir essa mesma chave, enviada pelo navegador no cabeçalho
`X-Church-Token` ou em `?token=...`. Sem essa variável configurada (o
padrão), o módulo continua aberto como sempre foi — é um reforço
opcional para quando o painel ficar exposto sozinho na internet, fora
do próprio ALFA.

Quando a beta-cloud não está configurada (ver store.py), o backend
responde normalmente mas com "online": false — a tela então funciona
só em memória, sem sincronizar entre aparelhos, e avisa isso no
indicador "Modo demonstração" do cabeçalho.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

from . import whatsapp
from .service import AtendimentoChurchService
from .store import IGREJA_PADRAO

_PASTA = Path(__file__).parent
_PAGINA = _PASTA / "webapp.html"
_MARCADOR_BODY = '<body>\n<div class="app">'

# Cache compartilhado entre conexões /api/stream desta mesma igreja, para
# não bater na beta-cloud uma vez por segundo por aba aberta.
_CACHE_ESTADO: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SEGUNDOS = 1.5
_STREAM_INTERVALO_SEGUNDOS = 1.5
_STREAM_DURACAO_MAXIMA_SEGUNDOS = 570  # o navegador reconecta sozinho (EventSource)


def renderizar_painel(igreja_id: str | None = None) -> str:
    """Retorna o HTML completo da tela do RMD Atendimento Church.

    Quando `igreja_id` é informado, grava `window.IGREJA_ID` logo no
    início da página, para a própria tela saber de qual igreja ela é.
    """
    html = _PAGINA.read_text(encoding="utf-8")
    if igreja_id and _MARCADOR_BODY in html:
        script = f'<body>\n<script>window.IGREJA_ID={json.dumps(igreja_id)};</script>\n<div class="app">'
        html = html.replace(_MARCADOR_BODY, script, 1)
    return html


def _resposta_json(start_response, dados: Any, status: str = "200 OK"):
    corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(corpo)))])
    return [corpo]


def _ler_corpo_bruto(environ) -> bytes:
    try:
        tamanho = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        tamanho = 0
    return environ["wsgi.input"].read(tamanho) if tamanho > 0 else b""


def _ler_corpo_json(environ) -> dict[str, Any]:
    bruto = _ler_corpo_bruto(environ) or b"{}"
    try:
        return json.loads(bruto)
    except json.JSONDecodeError:
        return {}


def _query(environ) -> dict[str, list[str]]:
    return parse_qs(environ.get("QUERY_STRING", ""))


def _query_simples(environ) -> dict[str, str]:
    return {chave: valores[0] for chave, valores in _query(environ).items() if valores}


def _igreja_id_da_requisicao(environ) -> str | None:
    valores = _query(environ).get("igreja")
    return valores[0].strip() if valores and valores[0].strip() else None


def _limit_da_requisicao(environ, padrao: int = 200) -> int:
    valores = _query(environ).get("limit")
    if not valores:
        return padrao
    try:
        return max(1, min(int(valores[0]), 2000))
    except ValueError:
        return padrao


def _token_valido(environ) -> bool:
    esperado = os.environ.get("CHURCH_API_TOKEN") or ""
    if not esperado:
        return True  # sem chave configurada: módulo continua aberto, como sempre
    recebido = environ.get("HTTP_X_CHURCH_TOKEN") or (_query(environ).get("token") or [None])[0]
    return recebido == esperado


def _estado_cacheado(servico: AtendimentoChurchService, limit: int) -> dict[str, Any]:
    chave = f"{servico.igreja_id}:{limit}"
    agora = time.time()
    entrada = _CACHE_ESTADO.get(chave)
    if entrada and (agora - entrada["ts"]) < _CACHE_TTL_SEGUNDOS:
        return entrada["estado"]
    estado = servico.estado(limit=limit)
    _CACHE_ESTADO[chave] = {"estado": estado, "ts": agora}
    return estado


def _fluxo_sse(servico: AtendimentoChurchService, limit: int):
    """Gerador do Server-Sent Events: só envia um evento quando algo muda."""
    ultimo_payload = None
    fim = time.time() + _STREAM_DURACAO_MAXIMA_SEGUNDOS
    while time.time() < fim:
        try:
            estado = _estado_cacheado(servico, limit)
            payload = json.dumps(estado, ensure_ascii=False)
        except Exception as erro:  # nunca derruba a conexão por causa da nuvem
            payload = json.dumps({"erro": str(erro), "online": False}, ensure_ascii=False)
        if payload != ultimo_payload:
            ultimo_payload = payload
            yield f"data: {payload}\n\n".encode("utf-8")
        else:
            yield b": ping\n\n"  # mantém a conexão viva atrás de proxies
        time.sleep(_STREAM_INTERVALO_SEGUNDOS)


def criar_app_wsgi(
    service: AtendimentoChurchService | None = None,
    service_factory: Callable[[str], AtendimentoChurchService] | None = None,
):
    """Cria o app WSGI do módulo.

    - `service`: uma instância fixa (modo simples, ou testes) — ignora o
      `igreja_id` da requisição e sempre atende com essa mesma instância.
    - `service_factory`: função `igreja_id -> AtendimentoChurchService`,
      para servir várias igrejas com o mesmo processo (multi-tenant). Se
      nenhum dos dois for passado, cria uma `AtendimentoChurchService`
      padrão por igreja, isolando os dados normalmente.
    """
    fabrica = service_factory or (lambda igreja_id: AtendimentoChurchService(igreja_id=igreja_id))

    def resolver_service(environ) -> AtendimentoChurchService:
        if service is not None:
            return service
        igreja_id = _igreja_id_da_requisicao(environ) or IGREJA_PADRAO
        return fabrica(igreja_id)

    def app(environ, start_response):
        metodo = environ.get("REQUEST_METHOD", "GET")
        caminho = environ.get("PATH_INFO", "/") or "/"

        if caminho == "/api/health":
            corpo = b"ok"
            start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
            return [corpo]

        if (
            caminho.startswith("/api/")
            and caminho != "/api/whatsapp/webhook"
            and not _token_valido(environ)
        ):
            return _resposta_json(start_response, {"erro": "chave de acesso inválida ou ausente"}, "401 Unauthorized")

        if caminho == "/api/state" and metodo == "GET":
            try:
                servico = resolver_service(environ)
                limit = _limit_da_requisicao(environ)
                return _resposta_json(start_response, servico.estado(limit=limit))
            except Exception as erro:  # nunca derruba o painel por causa da nuvem
                return _resposta_json(start_response, {"erro": str(erro)}, "503 Service Unavailable")

        if caminho == "/api/stream" and metodo == "GET":
            servico = resolver_service(environ)
            limit = _limit_da_requisicao(environ)
            start_response("200 OK", [
                ("Content-Type", "text/event-stream; charset=utf-8"),
                ("Cache-Control", "no-cache"),
                ("X-Accel-Buffering", "no"),
            ])
            return _fluxo_sse(servico, limit)

        if caminho == "/api/conversa" and metodo == "POST":
            try:
                servico = resolver_service(environ)
                documento = servico.salvar_conversa(_ler_corpo_json(environ))
                return _resposta_json(start_response, {"ok": True, "conversa": documento})
            except ValueError as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "400 Bad Request")
            except Exception as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "503 Service Unavailable")

        if caminho == "/api/cfg" and metodo == "POST":
            try:
                servico = resolver_service(environ)
                documento = servico.salvar_config(_ler_corpo_json(environ))
                return _resposta_json(start_response, {"ok": True, "cfg": documento})
            except Exception as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "503 Service Unavailable")

        if caminho == "/api/backup" and metodo == "GET":
            try:
                servico = resolver_service(environ)
                pacote = servico.exportar_backup()
            except Exception as erro:
                return _resposta_json(start_response, {"erro": str(erro)}, "503 Service Unavailable")
            corpo = json.dumps(pacote, ensure_ascii=False, indent=2).encode("utf-8")
            nome = f"backup-{servico.igreja_id}-{time.strftime('%Y-%m-%d')}.json"
            start_response("200 OK", [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(corpo))),
                ("Content-Disposition", f'attachment; filename="{nome}"'),
            ])
            return [corpo]

        if caminho == "/api/whatsapp/webhook" and metodo == "GET":
            desafio = whatsapp.verificar_webhook(_query_simples(environ))
            if desafio is None:
                corpo = b"forbidden"
                start_response("403 Forbidden", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
                return [corpo]
            corpo = desafio.encode("utf-8")
            start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
            return [corpo]

        if caminho == "/api/whatsapp/webhook" and metodo == "POST":
            bruto = _ler_corpo_bruto(environ)
            assinatura = environ.get("HTTP_X_HUB_SIGNATURE_256")
            if not whatsapp.assinatura_valida(bruto, assinatura):
                corpo = b"forbidden"
                start_response("403 Forbidden", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
                return [corpo]
            try:
                payload = json.loads(bruto or b"{}")
            except json.JSONDecodeError:
                payload = {}
            extraida = whatsapp.extrair_mensagem_recebida(payload)
            if extraida:
                try:
                    servico = resolver_service(environ)
                    servico.registrar_mensagem_whatsapp(extraida["telefone"], extraida["nome"], extraida["texto"])
                except Exception:
                    pass  # nunca falha o webhook por causa da nuvem; a Meta reenvia depois
            corpo = b"EVENT_RECEIVED"
            start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
            return [corpo]

        if caminho == "/api/whatsapp/enviar" and metodo == "POST":
            corpo_req = _ler_corpo_json(environ)
            telefone = (corpo_req.get("telefone") or "").strip()
            texto = (corpo_req.get("texto") or "").strip()
            if not telefone or not texto:
                return _resposta_json(start_response, {"ok": False, "erro": "telefone e texto são obrigatórios"}, "400 Bad Request")
            try:
                servico = resolver_service(environ)
                enviado = servico.enviar_whatsapp(telefone, texto)
            except Exception as erro:
                return _resposta_json(start_response, {"ok": False, "erro": str(erro)}, "503 Service Unavailable")
            return _resposta_json(start_response, {"ok": True, "enviado": enviado})

        if caminho in ("/", "/index.html") and metodo == "GET":
            igreja_id = _igreja_id_da_requisicao(environ)
            corpo = renderizar_painel(igreja_id).encode("utf-8")
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(corpo)))])
            return [corpo]

        corpo = b"Not Found"
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(corpo)))])
        return [corpo]

    return app
