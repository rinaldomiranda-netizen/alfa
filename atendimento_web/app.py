from __future__ import annotations

import json
import os
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.roteiro_pesquisa import roteiro_nova_entrevista
from modules.atendimento.modulo import AtendimentoModule
from modules.atendimento.service import AtendimentoService
from modules.atendimento.store import AtendimentoStore

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
FRONTEND_DIST = BASE.parent / "frontend_dist"
STORE_PATH = Path(os.getenv("ATENDIMENTO_STORE_PATH", str(BASE / "data" / "sessoes.json")))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

STORE = AtendimentoStore(STORE_PATH)
SESSOES: dict[str, AtendimentoService] = {}
EMPRESAS: dict[str, str] = {}
LOCK = threading.RLock()


def nova_sessao(empresa_id: str) -> tuple[str, AtendimentoService, str]:
    session_id = uuid.uuid4().hex
    modulo = AtendimentoModule(camera_module=None, pesquisa_app=None)
    service = AtendimentoService(store=STORE, modulo=modulo)
    mensagem = service.iniciar(empresa_id, roteiro_nova_entrevista())
    with LOCK:
        SESSOES[session_id] = service
        EMPRESAS[session_id] = empresa_id
    return session_id, service, mensagem


def status_publico(service: AtendimentoService) -> dict:
    s = service.modulo.status()
    return {
        "id": s["id"],
        "versao": s["versao"],
        "ativo": s["ativo"],
        "estado": s["estado"],
        "atendimento_id": s["atendimento_id"],
        "nome_pessoa": s["nome_pessoa"],
    }


def resposta_publica(service: AtendimentoService, resultado: object) -> dict:
    if isinstance(resultado, dict):
        mensagem = resultado.get("mensagem", "")
        proxima = resultado.get("proxima_pergunta")
        acao = resultado.get("acao")
    else:
        mensagem = str(resultado)
        proxima = None
        acao = None
    if not proxima and service.modulo.ativo:
        proxima = service.modulo.engine.pergunta_atual()
    return {
        "mensagem": mensagem,
        "proxima_pergunta": proxima,
        "acao": acao,
        "status": status_publico(service),
    }


def web_responder(service: AtendimentoService, empresa_id: str, texto: str) -> dict:
    resultado = service.responder(empresa_id, texto)
    if (
        isinstance(resultado, dict)
        and resultado.get("acao") == "proxima_pergunta"
        and resultado.get("proxima_pergunta") == "Qual é o seu nome completo?"
        and service.modulo.engine.nome_pessoa
    ):
        nome = service.modulo.engine.nome_pessoa
        interno = service.responder(empresa_id, nome)
        if isinstance(interno, dict) and interno.get("acao") == "confirmar":
            interno = service.responder(empresa_id, "sim")
        resultado = interno
    return resposta_publica(service, resultado)


class Handler(BaseHTTPRequestHandler):
    server_version = "RMDAtendimento/1.0"

    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        tamanho = int(self.headers.get("Content-Length", "0"))
        if tamanho <= 0:
            return {}
        bruto = self.rfile.read(tamanho)
        return json.loads(bruto.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._json({}, 204)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/api/health":
            self._json({"ok": True, "servico": "RMD Atendimento", "versao": "1.0"})
            return
        if url.path == "/api/historico":
            empresa_id = parse_qs(url.query).get("empresa_id", [""])[0].strip()
            if not empresa_id:
                self._json({"erro": "empresa_id é obrigatório"}, 400)
                return
            registros = STORE.listar(empresa_id)
            self._json({"itens": list(reversed(registros[-100:]))})
            return
        if url.path == "/atendimento" or url.path == "/atendimento/":
            self._arquivo(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if FRONTEND_DIST.exists() and not url.path.startswith("/api/"):
            caminho_relativo = url.path.lstrip("/") or "index.html"
            candidato = (FRONTEND_DIST / caminho_relativo).resolve()
            try:
                candidato.relative_to(FRONTEND_DIST.resolve())
            except ValueError:
                self._json({"erro": "Caminho inválido"}, 403)
                return
            if candidato.is_file():
                content_type = "text/html; charset=utf-8" if candidato.name == "index.html" else None
                self._arquivo(candidato, content_type)
                return
            # SPA fallback: rotas visuais do React são tratadas no cliente.
            self._arquivo(FRONTEND_DIST / "index.html", "text/html; charset=utf-8")
            return
        self._json({"erro": "Rota não encontrada"}, 404)

    def do_POST(self) -> None:
        url = urlparse(self.path)
        try:
            body = self._body()
        except Exception:
            self._json({"erro": "JSON inválido"}, 400)
            return

        if url.path == "/api/atendimentos":
            empresa_id = str(body.get("empresa_id", "")).strip()
            if not empresa_id:
                self._json({"erro": "empresa_id é obrigatório"}, 400)
                return
            session_id, service, mensagem = nova_sessao(empresa_id)
            self._json({
                "session_id": session_id,
                "mensagem": mensagem,
                "proxima_pergunta": service.modulo.engine.pergunta_atual(),
                "status": status_publico(service),
            })
            return

        if url.path.startswith("/api/atendimentos/") and url.path.endswith("/mensagens"):
            session_id = url.path.split("/")[3]
            empresa_id = str(body.get("empresa_id", "")).strip()
            texto = str(body.get("texto", "")).strip()
            if not empresa_id or not texto:
                self._json({"erro": "empresa_id e texto são obrigatórios"}, 400)
                return
            with LOCK:
                service = SESSOES.get(session_id)
                empresa_real = EMPRESAS.get(session_id)
            if service is None or empresa_real != empresa_id:
                self._json({"erro": "Sessão inválida ou empresa divergente"}, 404)
                return
            self._json(web_responder(service, empresa_id, texto))
            return

        if url.path.startswith("/api/atendimentos/") and url.path.endswith("/finalizar"):
            session_id = url.path.split("/")[3]
            empresa_id = str(body.get("empresa_id", "")).strip()
            with LOCK:
                service = SESSOES.get(session_id)
                empresa_real = EMPRESAS.get(session_id)
            if service is None or empresa_real != empresa_id:
                self._json({"erro": "Sessão inválida ou empresa divergente"}, 404)
                return
            respostas = service.finalizar(empresa_id)
            self._json({
                "ok": True,
                "respostas": respostas,
                "status": status_publico(service),
            })
            return

        self._json({"erro": "Rota não encontrada"}, 404)

    def _arquivo(self, caminho: Path, content_type: str) -> None:
        try:
            data = caminho.read_bytes()
        except OSError:
            self._json({"erro": "Arquivo não encontrado"}, 404)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        print(f"[HTTP] {self.address_string()} {format % args}")


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    print(f"[RMD ALFA] http://{HOST}:{PORT}")
    print(f"[RMD ALFA] dashboard: /")
    print(f"[RMD ALFA] atendimento: /atendimento")
    print(f"[RMD Atendimento] armazenamento: {STORE_PATH}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
