"""Correções da revisão de segurança (09/10/2026): cada teste reproduz o ataque e confere que foi barrado."""
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

from sobrou import seguranca  # noqa: E402
from sobrou.nucleo import ErroNegocio, NaoAutenticado, SemPermissao  # noqa: E402


class TestLogin(Base):
    def test_bloqueio_vale_so_para_o_ip_que_errou(self):
        self.p.definir_dono("dono@sobrou.test")
        for _ in range(6):
            with self.assertRaises((NaoAutenticado, ErroNegocio)):
                self.p.entrar_criador("errada", ip="203.0.113.9")
        with self.assertRaises(ErroNegocio):  # o atacante fica bloqueado
            self.p.entrar_criador("1234", ip="203.0.113.9")
        self.assertTrue(self.p.entrar_criador("1234", ip="198.51.100.7")["token"])  # o dono continua entrando

    def test_email_inexistente_responde_igual(self):
        for _ in range(6):
            with self.assertRaises((NaoAutenticado, ErroNegocio)):
                self.p.entrar("ninguem@x.test", "errada", ip="203.0.113.9")
        with self.assertRaises(ErroNegocio):  # mesma mensagem de bloqueio de quem existe
            self.p.entrar("ninguem@x.test", "errada", ip="203.0.113.9")


class TestFinanceiro(Base):
    def test_financeiro_da_loja_nao_marca_a_propria_mensalidade(self):
        planos = {p["nome"]: p for p in self.p.listar_planos(self.adm)}
        self.p.definir_plano(self.adm, self.emp_a["id"], planos["Profissional"]["id"])
        self.p.banco.executar("UPDATE empresas SET demonstracao=0")
        self.p.gerar_faturas()
        f = self.p.listar_faturas(self.a)[0]
        self.p.criar_usuario(self.a, {"nome": "Fin", "email": "fin@a.test", "papel": "financeiro", "empresa_id": self.emp_a["id"]})
        fin = self.p.ator_da_sessao(self.p.entrar("fin@a.test", "1234")["token"])
        with self.assertRaises(SemPermissao):
            self.p.marcar_fatura_paga(fin, f["id"], "PIX falso")
        with self.assertRaises(SemPermissao):
            self.p.calcular_repasse(fin, self.emp_a["id"])
        self.assertEqual(self.p.listar_faturas(self.a)[0]["status"], f["status"])
        self.p.marcar_fatura_paga(self.adm, f["id"], "PIX 123")  # a equipe Sobrou+ continua podendo


class TestCodigos(Base):
    def test_codigo_de_entrega_tem_limite_de_tentativas(self):
        chave = "entrega:teste"
        for _ in range(5):
            seguranca.FALHAS_CODIGO.falhou(chave)
        self.assertTrue(seguranca.FALHAS_CODIGO.bloqueado(chave))

    def test_relatorio_csv_nao_leva_formula(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        self.p.validar_retirada(self.a, ped["token_retirada"])
        self.p.avaliar_pedido(self.cli, ped["id"], 5, "=HYPERLINK(\"http://x\")")
        _, conteudo = self.p.relatorio_csv(self.a, "avaliacoes")
        texto = conteudo.decode("utf-8")
        self.assertIn("'=HYPERLINK", texto)


class TestIntegracoes(Base):
    def test_nao_aponta_para_a_rede_interna(self):
        for url in ("http://router.project-osrm.org", "https://127.0.0.1", "https://192.168.0.1", "https://169.254.169.254"):
            with self.assertRaises(ErroNegocio):
                self.p.salvar_integracao(self.adm, "mapas", {"rotas_url": url})
        with self.assertRaises(ErroNegocio):
            self.p.salvar_integracao(self.adm, "email", {"servidor": "127.0.0.1"})

    def test_token_volta_igual_depois_de_guardado(self):
        self.p.salvar_integracao(self.adm, "whatsapp", {"ligado": True, "token": "EAAtokenwhats", "phone_number_id": "1234567"})
        self.assertEqual(self.p.ler_integracao("whatsapp")["token"], "EAAtokenwhats")


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SOBROU_ATRAS_DE_PROXY"] = "1"
        from web import app
        cls.app = app
        app.ATRAS_DE_PROXY = True
        cls.srv = app.criar_servidor("127.0.0.1", 0)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.app.ATRAS_DE_PROXY = os.getenv("SOBROU_ATRAS_DE_PROXY") == "1"

    def _post(self, caminho, corpo, cab=None):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        dados = json.dumps(corpo).encode()
        h = {"Content-Type": "application/json", "Content-Length": str(len(dados))}
        h.update(cab or {})
        c.request("POST", caminho, body=dados, headers=h)
        r = c.getresponse()
        r.read()
        return r.status

    def test_xff_escrito_por_quem_acessa_nao_burla_o_limite(self):
        situacoes = [self._post("/api/entrar", {"email": f"x{i}@x.test", "senha": "e"},
                                {"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.50"}) for i in range(25)]
        self.assertIn(400, situacoes)  # bloqueou ("Muitas tentativas") mesmo trocando o primeiro IP

    def test_tamanho_negativo_e_recusado(self):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        c.putrequest("POST", "/api/telemetria")
        c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", "-1")
        c.endheaders()
        self.assertEqual(c.getresponse().status, 400)

    def test_sair_de_outro_site_e_recusado(self):
        self.assertEqual(self._post("/api/sair", {}, {"Cookie": "sob_sessao=x", "Origin": "https://site-malicioso.test"}), 403)


if __name__ == "__main__":
    unittest.main()
