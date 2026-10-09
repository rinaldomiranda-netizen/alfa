"""Acréscimos: esqueci a senha, backup, LGPD, aviso no celular (push), relatórios, gráficos, avaliações e planos."""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_fluxos import Base  # noqa: E402

from sobrou import push  # noqa: E402
from sobrou.nucleo import ErroNegocio, NaoAutenticado  # noqa: E402


class TestSenha(Base):
    def test_sem_canal_avisa_para_pedir_ao_admin(self):
        self.assertFalse(self.p.pedir_codigo_senha("cris@c.test")["ok"])

    def test_codigo_por_email(self):
        enviados = []
        self.p.salvar_integracao(self.adm, "email", {"ligado": True, "servidor": "smtp.exemplo", "remetente": "nao-responda@sobrou.test"})
        self.p.enviar_email = lambda para, assunto, corpo: enviados.append((para, corpo)) or True
        r = self.p.pedir_codigo_senha("cris@c.test")
        self.assertTrue(r["ok"])
        self.assertEqual(self.p.pedir_codigo_senha("naoexiste@x.test")["mensagem"], r["mensagem"])  # não revela quem existe
        codigo = enviados[0][1].split("é ")[1][:6]
        with self.assertRaises(ErroNegocio):
            self.p.redefinir_com_codigo("cris@c.test", "000000" if codigo != "000000" else "111111", "novaSenha9")
        self.p.redefinir_com_codigo("cris@c.test", codigo, "novaSenha9")
        with self.assertRaises(NaoAutenticado):
            self.p.ator_da_sessao(self.cli.extras.get("token"))  # sessões antigas caem
        self.assertTrue(self.p.entrar("cris@c.test", "novaSenha9")["token"])
        with self.assertRaises(ErroNegocio):  # código não serve duas vezes
            self.p.redefinir_com_codigo("cris@c.test", codigo, "outraSenha9")


class TestBackupLGPD(Base):
    def test_backup_diario(self):
        nome = self.p.backup_se_preciso()
        self.assertTrue(nome)
        self.assertIsNone(self.p.backup_se_preciso())  # só um por dia
        c = sqlite3.connect(str(self.p.pasta / "backups" / nome))
        self.assertGreater(c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0], 0)
        c.close()
        self.rel.andar(hours=25)
        self.assertTrue(self.p.backup_se_preciso())

    def test_termos_obrigatorios_e_excluir_conta(self):
        with self.assertRaises(ErroNegocio):
            self.p.cadastrar_cliente({"nome": "Sem", "email": "sem@c.test", "senha": "senha123ok"})
        u = self.p.banco.um("SELECT aceite_termos_em FROM usuarios WHERE id=?", (self.cli.usuario_id,))
        self.assertIn("v2026", u["aceite_termos_em"])
        dados = self.p.meus_dados(self.cli)
        self.assertEqual(dados["conta"]["email"], "cris@c.test")
        with self.assertRaises(ErroNegocio):
            self.p.excluir_minha_conta(self.cli, "errada")
        self.p.excluir_minha_conta(self.cli, "senha123ok")
        u = self.p.banco.um("SELECT * FROM usuarios WHERE id=?", (self.cli.usuario_id,))
        self.assertNotIn("cris", u["email"])
        self.assertIsNone(u["telefone"])
        with self.assertRaises(NaoAutenticado):
            self.p.entrar("cris@c.test", "senha123ok")


@unittest.skipUnless(push.DISPONIVEL, "cryptography ausente")
class TestPush(Base):
    def test_cifra_conforme_rfc8291_e_envio(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        ua = ec.generate_private_key(ec.SECP256R1())
        ua_pub = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        auth = os.urandom(16)
        corpo = push.cifrar(b'{"texto":"oi"}', push.b64u(ua_pub), push.b64u(auth))
        sal, idlen = corpo[:16], corpo[20]
        as_pub = corpo[21:21 + idlen]
        ecdh = ua.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
        ikm = push._hkdf(auth, ecdh, b"WebPush: info\x00" + ua_pub + as_pub, 32)
        cek = push._hkdf(sal, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = push._hkdf(sal, ikm, b"Content-Encoding: nonce\x00", 12)
        claro = AESGCM(cek).decrypt(nonce, corpo[21 + idlen:], None)
        self.assertEqual(claro, b'{"texto":"oi"}\x02')
        # inscrição + fila + envio
        self.assertTrue(self.p.chave_push_publica())
        self.p.inscrever_push(self.cli, {"endpoint": "https://push.exemplo/abc", "keys": {"p256dh": push.b64u(ua_pub), "auth": push.b64u(auth)}})
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        chamadas = []
        n = self.p.enviar_fila_push(enviador=lambda url, corpo, cab: chamadas.append(cab) or 201)
        self.assertGreater(n, 0)
        self.assertTrue(chamadas[0]["Authorization"].startswith("vapid t="))


class TestRelatoriosAvaliacoesPlanos(Base):
    def _venda(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 2}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        return self.p.validar_retirada(self.a, ped["token_retirada"])

    def test_relatorio_e_grafico(self):
        self._venda()
        nome, dados = self.p.relatorio_csv(self.a, "pedidos")
        self.assertTrue(nome.endswith(".csv"))
        texto = dados.decode("utf-8-sig")
        self.assertIn("numero;criado_em", texto)
        self.assertIn("25,00", texto)
        self.assertEqual(self.p.relatorio_csv(self.b, "pedidos")[1].decode("utf-8-sig").count("\n"), 1)  # empresa B não vê
        g = self.p.graficos(self.a)
        self.assertEqual(sum(d["pedidos"] for d in g["serie"]), 1)

    def test_avaliacao(self):
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        with self.assertRaises(ErroNegocio):
            self.p.avaliar_pedido(self.cli, ped["id"], 5)
        ped = self._venda()
        self.p.avaliar_pedido(self.cli, ped["id"], 4, "Muito boa!")
        with self.assertRaises(ErroNegocio):
            self.p.avaliar_pedido(self.cli, ped["id"], 5)
        self.assertEqual(self.p.vitrine({})[0]["nota"], {"media": 4.0, "total": 1})
        av = self.p.listar_avaliacoes(self.a)
        self.p.responder_avaliacao(self.a, av["itens"][0]["id"], "Obrigado!")
        self.assertEqual(self.p.listar_avaliacoes(self.b)["total"], 0)

    def test_avaliacao_bilateral_e_pontos_unicos(self):
        o = self.oferta()
        aberto = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        with self.assertRaises(ErroNegocio):
            self.p.avaliar_cliente_pedido(self.a, aberto["id"], 5)
        ped = self._venda()
        self.p.avaliar_cliente_pedido(self.a, ped["id"], 4, "Retirada tranquila.")
        self.assertEqual(self.p.obter_pedido(self.a, ped["id"])["avaliacao_cliente"]["nota"], 4)
        self.assertNotIn("avaliacao_cliente", self.p.obter_pedido(self.cli, ped["id"]))
        with self.assertRaises(ErroNegocio):
            self.p.avaliar_cliente_pedido(self.a, ped["id"], 5)
        recebidas = self.p.listar_avaliacoes_clientes(self.a)
        self.assertEqual((recebidas["total"], recebidas["itens"][0]["nota"]), (1, 4))
        reputacao = self.p.minha_reputacao(self.cli)
        self.assertEqual(reputacao["media"], 4.0)
        self.assertEqual(reputacao["total"], 1)
        self.assertEqual(reputacao["itens"][0]["loja"], self.emp_a["nome"])
        self.assertEqual(reputacao["pontos"], ped["subtotal_centavos"] // 100)
        with self.assertRaises(ErroNegocio):
            self.p.listar_avaliacoes_clientes(self.cli)

    def test_planos_taxa_limite_e_fatura(self):
        planos = {p["nome"]: p for p in self.p.listar_planos(self.adm)}
        self.p.definir_plano(self.adm, self.emp_a["id"], planos["Essencial"]["id"])
        self.assertEqual(self._venda()["taxa_percentual"], 15.0)
        for i in range(4):
            self.oferta(nome=f"Oferta {i}")
        with self.assertRaises(ErroNegocio):  # Essencial: até 5 no ar
            self.oferta(nome="Sexta")
        self.p.definir_plano(self.adm, self.emp_a["id"], planos["Profissional"]["id"])
        self.oferta(nome="Agora pode")
        self.p.banco.executar("UPDATE empresas SET demonstracao=0")
        self.assertEqual(self.p.gerar_faturas(), 1)
        self.assertEqual(self.p.gerar_faturas(), 0)  # uma por mês
        f = self.p.listar_faturas(self.a)[0]
        self.assertEqual(f["valor_centavos"], 9900)
        self.p.marcar_fatura_paga(self.adm, f["id"], "PIX 123")
        self.assertEqual(self.p.listar_faturas(self.a)[0]["status"], "paga")


if __name__ == "__main__":
    unittest.main()
