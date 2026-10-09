"""Aplicativos separados por perfil (/apps/<nome>/) e acessos de teste para os sócios."""
from __future__ import annotations

import http.client
import json
import os
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_fluxos import Base  # noqa: E402

from sobrou.nucleo import ErroNegocio, SemPermissao  # noqa: E402
from sobrou.testes import APPS_TESTE  # noqa: E402


class TestSocios(Base):
    def test_cria_uma_conta_por_aplicativo_com_link(self):
        dono = self.adm
        r = self.p.criar_testador(dono, {"nome": "João Sócio", "telefone": "79 99999-0000"})
        self.assertEqual([x["app"] for x in r["links"]], list(APPS_TESTE))
        self.assertTrue(all(x["caminho"].startswith(f"/apps/{x['app']}/acesso?c=") for x in r["links"]))
        emails = [x["email"] for x in r["links"]]
        self.assertEqual(len(set(emails)), 5)
        self.assertIn("joao.caixa@teste.sobrou", emails)
        # cada link cria a senha e entra no papel certo
        papeis = {}
        for x in r["links"]:
            tok = x["caminho"].split("c=")[1]
            s = self.p.aceitar_convite(tok, "senhaBoa123", True)
            papeis[x["app"]] = self.p.ator_da_sessao(s["token"]).papel
        self.assertEqual(papeis, {k: v[0] for k, v in APPS_TESTE.items()})
        # loja e caixa ficam na Loja Teste RMD (dados fictícios)
        loja = self.p.ator_da_sessao(self.p.entrar("joao.loja@teste.sobrou", "senhaBoa123")["token"])
        teste = self.p.mundo_de_teste()["empresa_id"]
        self.assertEqual(loja.empresa_id, teste)
        lista = self.p.listar_testadores(dono)["itens"][0]
        self.assertTrue(all(c["senha_criada"] for c in lista["contas"]))
        # segundo João não colide
        r2 = self.p.criar_testador(dono, {"nome": "João Outro"})
        self.assertIn("joao2.caixa@teste.sobrou", [x["email"] for x in r2["links"]])

    def test_ninguem_entra_antes_do_socio_e_desligar_funciona(self):
        r = self.p.criar_testador(self.adm, {"nome": "Maria"})
        with self.assertRaises(Exception):
            self.p.entrar("maria.caixa@teste.sobrou", "1234")  # sem senha padrão conhecida
        tid = r["testador"]["id"]
        self.p.ligar_testador(self.adm, tid, False)
        with self.assertRaises(Exception):
            self.p.aceitar_convite(r["links"][0]["caminho"].split("c=")[1], "senhaBoa123", True)
        with self.assertRaises(ErroNegocio):
            self.p.novos_links_testador(self.adm, tid)
        self.p.ligar_testador(self.adm, tid, True)
        novos = self.p.novos_links_testador(self.adm, tid)["links"]
        self.assertTrue(self.p.aceitar_convite(novos[2]["caminho"].split("c=")[1], "senhaBoa123", True)["token"])

    def test_so_o_desenvolvedor(self):
        with self.assertRaises(SemPermissao):
            self.p.criar_testador(self.a, {"nome": "Intruso"})
        with self.assertRaises(SemPermissao):
            self.p.listar_testadores(self.cli)


class TestAppsServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from web import app
        from sobrou.plataforma import Plataforma
        cls.app = app
        cls.antiga = app._plataforma
        cls.pasta = tempfile.mkdtemp()
        app._plataforma = Plataforma(cls.pasta)  # banco só deste teste (não mexe nos outros testes)
        cls.srv = app.criar_servidor("127.0.0.1", 0)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.app._plataforma = cls.antiga

    def _get(self, caminho, cab=None):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        c.request("GET", caminho, headers=cab or {})
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()

    def test_cada_app_tem_manifesto_nome_e_icone_proprios(self):
        ids, nomes = set(), set()
        for app in APPS_TESTE:
            s, _h, corpo = self._get(f"/apps/{app}/manifest.webmanifest")
            self.assertEqual(s, 200)
            m = json.loads(corpo)
            ids.add(m["id"]); nomes.add(m["short_name"])
            self.assertEqual(m["scope"], "./")
            self.assertIn(f"static/img/apps/{app}-512.png", [i["src"] for i in m["icons"]])
            s, _h, _c = self._get(f"/apps/{app}/static/img/apps/{app}-512.png")
            self.assertEqual(s, 200)
            s, _h, html = self._get(f"/apps/{app}/")
            self.assertEqual(s, 200)
            self.assertIn(b'apple-mobile-web-app-title', html)
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(nomes), 5)

    def test_endereco_sem_barra_vai_para_dentro_do_app(self):
        s, h, _c = self._get("/apps/caixa")
        self.assertEqual(s, 302)
        self.assertEqual(h["Location"], "/apps/caixa/")
        self.assertEqual(self._get("/apps/naoexiste/")[0], 404)

    def test_sessao_de_um_app_nao_vale_no_outro(self):
        p = self.app.plataforma()
        p.garantir_admin_sobrou("adm-apps@sobrou.test")
        adm = p.ator_da_sessao(p.entrar("adm-apps@sobrou.test", "1234")["token"])
        p.banco.executar("UPDATE usuarios SET trocar_senha=0 WHERE id=?", (adm.usuario_id,))
        r = p.criar_testador(adm, {"nome": "Teste Sessão"})
        caixa = next(x for x in r["links"] if x["app"] == "caixa")
        tok = caixa["caminho"].split("c=")[1]
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        corpo = json.dumps({"senha": "senhaBoa123", "aceite_termos": True})
        c.request("POST", f"/apps/caixa/api/convite/{tok}", body=corpo, headers={"Content-Type": "application/json"})
        resp = c.getresponse(); resp.read()
        self.assertEqual(resp.status, 200)
        cookie = resp.getheader("Set-Cookie")
        self.assertIn("sob_sessao_caixa=", cookie)
        self.assertIn("Path=/apps/caixa", cookie)
        valor = cookie.split(";")[0]
        self.assertEqual(self._get("/apps/caixa/api/eu", {"Cookie": valor})[0], 200)
        self.assertEqual(self._get("/apps/loja/api/eu", {"Cookie": valor})[0], 401)  # não vale no app da Loja
        self.assertEqual(self._get("/api/eu", {"Cookie": valor})[0], 401)


if __name__ == "__main__":
    unittest.main()
