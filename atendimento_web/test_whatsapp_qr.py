"""Conexão do WhatsApp por QR Code: servidor de verdade + ponte Node em modo simulado (sem WhatsApp real)."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from atendimento_web import app, recepcao
from atendimento_web.test_app import Cliente
from modules.atendimento.plataforma import Plataforma, demo, ponte_qr, seguranca

_IT = seguranca.ITERACOES
PORTA_PONTE = 18787


@unittest.skipUnless(ponte_qr._node(), "Node não instalado")
class WhatsAppQrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seguranca.ITERACOES = 2_000
        cls.pasta = Path(tempfile.mkdtemp())
        cls.env = {k: os.environ.get(k) for k in ("RMD_ATENDIMENTO_DADOS", "PONTE_SIMULADO", "RMD_PONTE_SEGREDO")}
        os.environ.update(RMD_ATENDIMENTO_DADOS=str(cls.pasta), PONTE_SIMULADO="1", RMD_PONTE_SEGREDO="segredo-de-teste")
        cls.porta_ant = ponte_qr.PORTA_PONTE
        ponte_qr.PORTA_PONTE = PORTA_PONTE
        cls.p = Plataforma(cls.pasta / "q.db", pasta_backups=cls.pasta / "bk")
        cls.p.envio_sincrono = True
        app.definir_plataforma(cls.p)
        cls.demo = demo.garantir_demonstracao(cls.p)
        recepcao.definir_store(None)
        recepcao.caminho_store = lambda: cls.pasta / "recepcao.json"
        cls.servidor = app.criar_servidor("127.0.0.1", 0)
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.porta = cls.servidor.server_address[1]
        for _ in range(50):
            if ponte_qr.no_ar(cls.pasta):
                break
            time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        ponte_qr.parar_ponte()
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.servidor.parar_rotina.set()
        ponte_qr.PORTA_PONTE = cls.porta_ant
        for k, v in cls.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        seguranca.ITERACOES = _IT
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def entrar(self, perfil="owner"):
        c = Cliente(self.porta)
        token = seguranca.criar_token_unico(self.demo["usuarios"][perfil], self.demo["empresa_id"])
        self.assertEqual(c.pedir("GET", "/entrar?token=" + token, csrf=False)[0], 303)
        return c

    def sim(self, caminho, corpo=None):
        r = urllib.request.Request(f"http://127.0.0.1:{PORTA_PONTE}{caminho}", data=json.dumps(corpo or {}).encode(),
                                   method="POST", headers={"x-segredo": "segredo-de-teste"})
        return json.loads(urllib.request.urlopen(r, timeout=5).read())

    def test_fluxo_completo(self):
        c = self.entrar()
        st, painel, _ = c.pedir("GET", "/api/whatsapp")
        self.assertEqual(st, 200)
        self.assertTrue(painel["qr_disponivel"])
        st, canal, _ = c.pedir("POST", "/api/whatsapp/qr", {"nome": "Teste QR"})
        self.assertEqual(st, 200, canal)
        wid = canal["id"]
        self.assertEqual(canal["modo"], "qr")
        for _ in range(30):
            st, e, _ = c.pedir("GET", f"/api/whatsapp/canais/{wid}/qr")
            if e["estado"] == "aguardando_qr":
                break
            time.sleep(0.2)
        self.assertEqual(e["estado"], "aguardando_qr")
        self.assertTrue(e["qr"])
        # sem segredo / de fora: webhook negado
        st, _, _ = Cliente(self.porta).pedir("POST", "/webhooks/whatsapp-qr", {"tipo": "estado"}, csrf=False)
        self.assertEqual(st, 403)
        # lê o QR
        self.sim("/simular/escanear", {"canal_id": wid})
        st, e, _ = c.pedir("GET", f"/api/whatsapp/canais/{wid}/qr")
        self.assertEqual(e["estado"], "conectado")
        self.assertEqual(e["numero"], "5579999990000")
        self.assertIsNone(e["qr"])
        # mensagem de entrada vira conversa
        self.sim("/simular/mensagem", {"canal_id": wid, "de": "5579988887777", "nome": "Maria", "texto": "Olá, preciso de oração"})
        msgs = self.p.banco.todos("SELECT * FROM mensagens WHERE texto LIKE '%oração%'")
        self.assertEqual(len(msgs), 1)
        # resposta sai pela ponte
        cid = msgs[0]["conversa_id"]
        st, r, _ = c.pedir("POST", f"/api/conversas/{cid}/responder", {"texto": "A paz! Já vamos orar por você."})
        self.assertIn(st, (200, 201), r)
        time.sleep(0.5)
        r = urllib.request.Request(f"http://127.0.0.1:{PORTA_PONTE}/simular/enviadas", data=b"{}", method="POST", headers={"x-segredo": "segredo-de-teste"})
        itens = json.loads(urllib.request.urlopen(r, timeout=5).read())["itens"]
        self.assertTrue(any("A paz" in i["texto"] and i["para"] == "5579988887777" for i in itens), itens)
        # desconectar
        st, r, _ = c.pedir("POST", f"/api/whatsapp/canais/{wid}/desconectar", {})
        self.assertEqual(st, 200)
        st, e, _ = c.pedir("GET", f"/api/whatsapp/canais/{wid}/qr")
        self.assertEqual(e["estado"], "desconectado")


if __name__ == "__main__":
    unittest.main()
