"""Acesso do Criador (só senha + 2 etapas opcional), link de acesso (convite), modo teste e financeiro detalhado."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_fluxos import Base  # noqa: E402

from sobrou import seguranca  # noqa: E402
from sobrou.acesso import PrecisaCodigo  # noqa: E402
from sobrou.nucleo import ErroNegocio, NaoAutenticado, NaoEncontrado, SemPermissao  # noqa: E402


class TestCriador(Base):
    def setUp(self):
        super().setUp()
        self.p.definir_dono("dono@sobrou.test")

    def test_entra_so_com_a_senha_sem_troca_obrigatoria(self):
        s = self.p.entrar_criador("1234")
        self.assertFalse(s["usuario"]["trocar_senha"])
        dono = self.p.ator_da_sessao(s["token"])
        self.assertEqual(dono.papel, "admin_sobrou")
        self.assertTrue(self.p.senha_padrao(dono))  # aviso na tela para trocar (sem obrigar)
        with self.assertRaises(NaoAutenticado):
            self.p.entrar_criador("errada")

    def test_dois_fatores(self):
        dono = self.p.ator_da_sessao(self.p.entrar_criador("1234")["token"])
        seg = self.p.iniciar_2fa(dono)["segredo"]
        agora = int(time.time() // seguranca.TOTP_PASSO)
        with self.assertRaises(ErroNegocio):
            self.p.confirmar_2fa(dono, "000000" if seguranca.codigo_totp(seg, agora) != "000000" else "111111")
        self.p.confirmar_2fa(dono, seguranca.codigo_totp(seg, agora))
        with self.assertRaises(PrecisaCodigo):
            self.p.entrar_criador("1234")
        with self.assertRaises(PrecisaCodigo):  # mesmo código não serve de novo
            self.p.entrar_criador("1234", codigo=seguranca.codigo_totp(seg, agora))
        self.assertTrue(self.p.entrar_criador("1234", codigo=seguranca.codigo_totp(seg, agora + 1))["token"])

    def test_modo_teste_so_para_o_criador(self):
        dono = self.p.ator_da_sessao(self.p.entrar_criador("1234")["token"])
        for perfil in ("cliente", "entregador", "operador_empresa", "admin_empresa", "financeiro"):
            tok = self.p.abrir_teste(dono, perfil)
            conta = self.p.ator_da_sessao(self.p.entrar_com_token_unico(tok)["token"])
            self.assertEqual(conta.papel, perfil)
            self.assertTrue(self.p.eh_conta_teste(conta.usuario_id))
        with self.assertRaises(SemPermissao):
            self.p.abrir_teste(self.a, "cliente")
        teste = self.p.mundo_de_teste()
        self.assertEqual(self.p.banco.um("SELECT demonstracao FROM empresas WHERE id=?", (teste["empresa_id"],))["demonstracao"], 1)


class TestConvite(Base):
    def test_cadastro_gera_link_e_pessoa_cria_a_propria_senha(self):
        u = self.p.criar_usuario(self.a, {"nome": "Edu Moto", "email": "edu@a.test", "papel": "entregador", "empresa_id": self.emp_a["id"]})
        caminho = u["convite"]["caminho"]
        tok = caminho.split("c=")[1]
        self.assertEqual(self.p.ver_convite(tok)["empresa"], "Restaurante A")
        with self.assertRaises(ErroNegocio):
            self.p.aceitar_convite(tok, "senhaBoa123", False)  # termos obrigatórios
        with self.assertRaises(ErroNegocio):
            self.p.aceitar_convite(tok, "1234", True)  # senha fraca
        s = self.p.aceitar_convite(tok, "senhaBoa123", True)
        self.assertEqual(self.p.ator_da_sessao(s["token"]).papel, "entregador")
        with self.assertRaises(NaoEncontrado):  # link só vale uma vez
            self.p.ver_convite(tok)
        self.assertTrue(self.p.entrar("edu@a.test", "senhaBoa123")["token"])

    def test_novo_link_invalida_o_anterior_e_vence(self):
        u = self.p.criar_usuario(self.a, {"nome": "Lia", "email": "lia@a.test", "papel": "operador_empresa", "empresa_id": self.emp_a["id"]})
        t1 = u["convite"]["caminho"].split("c=")[1]
        t2 = self.p.novo_convite(self.a, u["id"])["caminho"].split("c=")[1]
        with self.assertRaises(NaoEncontrado):
            self.p.ver_convite(t1)
        with self.assertRaises(NaoEncontrado):  # outra empresa não gera link para gente de A
            self.p.novo_convite(self.b, u["id"])
        self.rel.andar(days=8)
        with self.assertRaises(NaoEncontrado):
            self.p.ver_convite(t2)

    def test_empresa_nova_ja_vem_com_link_do_responsavel(self):
        e = self.p.criar_empresa(self.adm, {"nome": "Mercado C", "tipo": "mercado", "nome_responsavel": "Caio", "email_responsavel": "caio@c.test"})
        self.assertIn("/acesso?c=", e["convite"]["caminho"])


class TestFinanceiroDetalhado(Base):
    def test_plataforma_ve_tudo_e_empresa_so_o_seu(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 2}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        self.p.validar_retirada(self.a, ped["token_retirada"])
        self.p.banco.executar("UPDATE empresas SET demonstracao=0")
        g = self.p.financeiro_detalhado(self.adm)
        self.assertEqual(g["gmv_centavos"], 2500)
        self.assertEqual(g["pedidos"], 1)
        self.assertGreater(g["receita_plataforma_centavos"], 0)
        self.assertEqual({e["nome"] for e in g["empresas"] if e.get("vendas")}, {"Restaurante A"})
        b = self.p.financeiro_detalhado(self.b)
        self.assertEqual(b["gmv_centavos"], 0)
        with self.assertRaises(SemPermissao):  # empresa A não consegue ver a B
            self.p.financeiro_detalhado(self.a, empresa_id=self.emp_b["id"])
        self.assertEqual(self.p.financeiro_detalhado(self.a)["gmv_centavos"], 2500)
        with self.assertRaises(SemPermissao):
            self.p.financeiro_detalhado(self.cli)


if __name__ == "__main__":
    import unittest
    unittest.main()
