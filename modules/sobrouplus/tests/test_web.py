"""Testa o servidor web de verdade (HTTP, cookie de sessão, JSON, CSRF, isolamento de empresa)."""
from __future__ import annotations

import base64
import http.cookiejar
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PASTA = tempfile.mkdtemp()
os.environ["SOBROU_DADOS"] = PASTA
from web import app  # noqa: E402

JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 100).decode()


class Cliente:
    def __init__(self, base):
        self.base = base
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def req(self, metodo, caminho, corpo=None, tipo="application/json"):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        r = urllib.request.Request(self.base + caminho, data=dados, method=metodo, headers={"Content-Type": tipo} if dados else {})
        try:
            with self.op.open(r) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


class TestWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.criar_servidor("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        plataforma = app.plataforma()
        pagar_real = plataforma.pagar
        def pagar_somente_teste(ator, pedido_id, meio="", base_url=None):
            if meio != "teste":
                return pagar_real(ator, pedido_id, meio, base_url)
            with plataforma.banco.transacao() as c:
                pedido = plataforma._uma(c, "SELECT * FROM pedidos WHERE id=?", (pedido_id,))
                agora = plataforma.agora()
                c.execute("""INSERT INTO pagamentos(id, pedido_id, empresa_id, meio, valor_centavos, status, referencia_externa, criado_em, atualizado_em)
                             VALUES (?,?,?,?,?,'aprovado',?,?,?)""",
                          (uuid.uuid4().hex, pedido_id, pedido["empresa_id"], "teste", pedido["total_centavos"], "TEST_FIXTURE", agora, agora))
                plataforma._efetivar_pagamento(c, pedido, ator, "fixture temporária de teste HTTP")
            return plataforma.obter_pedido(ator, pedido_id)
        plataforma.pagar = pagar_somente_teste
        cls.senha_inicial_dono = plataforma.definir_dono("dono@sobrou.test")["senha_inicial_unica"] or "1234"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(PASTA, ignore_errors=True)

    def test_fluxo_http_completo(self):
        adm = Cliente(self.base)
        self.assertEqual(adm.req("POST", "/api/entrar", {"email": "dono@sobrou.test", "senha": self.senha_inicial_dono})[0], 200)
        s, r = adm.req("GET", "/api/empresas")
        self.assertEqual(s, 403)
        self.assertTrue(r.get("trocar_senha"))
        self.assertEqual(adm.req("POST", "/api/senha", {"atual": self.senha_inicial_dono, "nova": self.senha_inicial_dono})[0], 400)
        self.assertEqual(adm.req("POST", "/api/senha", {"atual": self.senha_inicial_dono, "nova": "novaSenha9"})[0], 200)
        # 2FA está temporariamente fora do gate de entrada: após trocar a senha,
        # o administrador já pode acessar as áreas autorizadas normalmente.
        s, r = adm.req("GET", "/api/empresas")
        self.assertEqual(s, 200, r)
        self.assertNotIn("configurar_2fa", r)
        s, setup = adm.req("POST", "/api/seguranca/2fa/iniciar", {})
        self.assertEqual(s, 200, setup)
        contador = int(time.time() // app.seguranca.TOTP_PASSO)
        s, confirmado = adm.req("POST", "/api/seguranca/2fa/confirmar",
                                {"codigo": app.seguranca.codigo_totp(setup["segredo"], contador)})
        self.assertEqual(s, 200, confirmado)
        # parceiro se cadastra → em análise → admin aprova
        par = Cliente(self.base)
        s, r = par.req("POST", "/api/cadastro/empresa", {"nome": "Padoca Web", "tipo": "padaria", "email_responsavel": "p@web.test", "senha": "senhaBoa1", "aceite_termos": True})
        self.assertEqual(s, 200, r)
        s, setup_par = par.req("POST", "/api/seguranca/2fa/iniciar", {})
        self.assertEqual(s, 200, setup_par)
        contador_par = int(time.time() // app.seguranca.TOTP_PASSO)
        s, confirmado_par = par.req("POST", "/api/seguranca/2fa/confirmar",
                                    {"codigo": app.seguranca.codigo_totp(setup_par["segredo"], contador_par)})
        self.assertEqual(s, 200, confirmado_par)
        eid = r["usuario"]["empresa_id"]
        s, u = par.req("POST", "/api/unidades", {"nome": "Loja 1", "lat": -10.9, "lng": -37.0})
        s, f = par.req("POST", "/api/fotos", {"imagem": JPEG})
        self.assertEqual(s, 200, f)
        agora = datetime.now(timezone.utc)
        s, o = par.req("POST", "/api/ofertas", {"unidade_id": u["id"], "nome": "Pão francês 1 kg", "categoria": "padaria", "preco_normal": "18,00",
                                                "preco": "8,00", "quantidade_total": 4, "inicio": agora.isoformat(), "fim": (agora + timedelta(hours=2)).isoformat(),
                                                "retirada_inicio": agora.isoformat(), "retirada_fim": (agora + timedelta(hours=2)).isoformat(), "foto_id": f["id"]})
        self.assertEqual(s, 200, o)
        self.assertEqual(par.req("POST", f"/api/ofertas/{o['id']}/status", {"status": "ativa"})[0], 400)  # não aprovada
        self.assertEqual(adm.req("POST", f"/api/empresas/{eid}/aprovar", {"aprovada": True})[0], 200)
        self.assertEqual(par.req("POST", f"/api/ofertas/{o['id']}/status", {"status": "ativa"})[1]["status"], "ativa")
        # foto pública
        with urllib.request.urlopen(self.base + f"/fotos/{f['id']}") as r:
            self.assertEqual(r.headers["Content-Type"], "image/jpeg")
        # cliente compra pela vitrine
        cli = Cliente(self.base)
        self.assertEqual(len(cli.req("GET", "/api/vitrine")[1]["itens"]), 1)
        cli.req("POST", "/api/cadastro/cliente", {"nome": "Web", "email": "cli@web.test", "senha": "senhaBoa1", "aceite_termos": True})
        s, ped = cli.req("POST", "/api/pedidos", {"itens": [{"oferta_id": o["id"], "quantidade": 2}], "modo": "retirada"})
        self.assertEqual(s, 200, ped)
        self.assertEqual(cli.req("POST", f"/api/pedidos/{ped['id']}/pagar", {"meio": "teste"})[1]["status"], "pago")
        for acao in ("receber", "preparar", "pronto"):
            self.assertEqual(par.req("POST", f"/api/pedidos/{ped['id']}/avancar", {"acao": acao})[0], 200)
        s, fim = par.req("POST", "/api/retirada", {"codigo": f"{ped['numero']}-{ped['codigo_retirada']}"})
        self.assertEqual(fim["status"], "concluido")
        self.assertEqual(par.req("GET", "/api/impacto")[1]["kg_vendidos"], 1.0)
        # outra empresa não enxerga
        out = Cliente(self.base)
        out.req("POST", "/api/cadastro/empresa", {"nome": "Outra", "tipo": "cafe", "email_responsavel": "o@web.test", "senha": "senhaBoa1", "aceite_termos": True})
        s, setup_out = out.req("POST", "/api/seguranca/2fa/iniciar", {})
        self.assertEqual(s, 200, setup_out)
        contador_out = int(time.time() // app.seguranca.TOTP_PASSO)
        s, confirmado_out = out.req("POST", "/api/seguranca/2fa/confirmar",
                                    {"codigo": app.seguranca.codigo_totp(setup_out["segredo"], contador_out)})
        self.assertEqual(s, 200, confirmado_out)
        self.assertEqual(out.req("GET", f"/api/pedidos/{ped['id']}")[0], 404)
        self.assertEqual(out.req("GET", f"/api/ofertas/{o['id']}")[0], 404)
        self.assertEqual(out.req("GET", f"/api/pedidos?empresa_id={eid}")[0], 403)
        self.assertEqual(cli.req("GET", "/api/financeiro")[0], 403)

    def test_csrf_e_sem_sessao(self):
        c = Cliente(self.base)
        self.assertEqual(c.req("GET", "/api/pedidos")[0], 401)
        self.assertEqual(c.req("POST", "/api/entrar", {"email": "x", "senha": "y"}, tipo="application/x-www-form-urlencoded")[0], 415)
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
