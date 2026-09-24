import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from atendimento_web import app


class AtendimentoWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        app.STORE_PATH = Path(cls.tmp.name) / "sessoes.json"
        app.STORE = app.AtendimentoStore(app.STORE_PATH)
        app.SESSOES.clear()
        app.EMPRESAS.clear()
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.tmp.cleanup()

    def request(self, path, payload=None):
        data = None
        headers = {}
        method = "GET"
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
            method = "POST"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode())

    def test_health(self):
        status, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_fluxo_novo_responder_historico(self):
        status, body = self.request("/api/atendimentos", {"empresa_id": "teste"})
        self.assertEqual(status, 200)
        self.assertTrue(body["session_id"])
        self.assertIn("Com quem estou falando?", body["mensagem"])
        sid = body["session_id"]

        status, body = self.request(
            f"/api/atendimentos/{sid}/mensagens",
            {"empresa_id": "teste", "texto": "Maria"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["acao"], "confirmar")

        status, body = self.request(
            f"/api/atendimentos/{sid}/mensagens",
            {"empresa_id": "teste", "texto": "sim"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["status"]["ativo"])

        status, body = self.request("/api/historico?empresa_id=teste")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body["itens"]), 1)


if __name__ == "__main__":
    unittest.main()
