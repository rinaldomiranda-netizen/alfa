"""Fluxos da Sede: encaminhar só à Sede, liberação, avisos e novas condições."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from modules.atendimento.plataforma import Plataforma, demo, seguranca
from modules.atendimento.plataforma import fluxos as motor
from modules.atendimento.plataforma.nucleo import Ator, ErroNegocio, NaoEncontrado

_IT = seguranca.ITERACOES


class FluxosSedeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seguranca.ITERACOES = 2_000
        cls.pasta = Path(tempfile.mkdtemp())
        cls.p = Plataforma(cls.pasta / "f.db", pasta_backups=cls.pasta / "bk")
        cls.p.envio_sincrono = True
        anterior = os.environ.get("RMD_EDICAO")
        os.environ["RMD_EDICAO"] = "church"
        try:
            cls.demo = demo.garantir_demonstracao(cls.p)
        finally:
            if anterior is None:
                os.environ.pop("RMD_EDICAO", None)
            else:
                os.environ["RMD_EDICAO"] = anterior
        cls.emp = cls.demo["empresa_id"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)
        seguranca.ITERACOES = _IT

    def ator(self, perfil):
        u = self.p.banco.um("SELECT * FROM usuarios WHERE id=?", (self.demo["usuarios"][perfil],))
        return Ator(u["id"], u["nome"], u["email"], perfil, self.emp, fila_id=u.get("fila_id"))

    def fila(self):
        return self.p.banco.um("SELECT id FROM filas WHERE empresa_id=? AND ativa=1", (self.emp,))["id"]

    def contato_da_igreja(self, nome, unidade_nome):
        uid = self.p.banco.um("SELECT id FROM igreja_unidades WHERE empresa_id=? AND nome=?", (self.emp, unidade_nome))["id"]
        c = self.p._criar_contato(self.emp, {"nome": nome, "telefone": "7998887" + str(abs(hash(nome)) % 10000).zfill(4)})
        self.p.banco.executar("UPDATE contatos SET unidade_id=? WHERE id=?", (uid, c["id"]))
        self.p._nova_jornada(self.emp, c["id"], {"etapa": "novo", "primeira_visita": None, "como_conheceu": None, "convidado_por": None,
                                                 "quer_visita": 0, "responsavel_id": None, "observacao": None, "unidade_id": uid})
        return c["id"]

    def publicar(self, nome, etapas, gatilho="palavra_chave", valor="documento"):
        admin = self.ator("admin")
        f = self.p.salvar_fluxo(admin, {"nome": nome, "gatilho_tipo": gatilho, "gatilho_valor": valor, "etapas": etapas})
        r = self.p.simular_fluxo(admin, f["id"], None, ["Certidão"])
        self.assertTrue(r["ok"], r)
        self.p.publicar_fluxo(admin, f["id"])
        return f["id"]

    # ---- motor puro
    def test_novos_operadores(self):
        a = motor._avaliar
        self.assertTrue(a("diferente", "Sim", "Não"))
        self.assertTrue(a("nao_contem", "oração", "documento"))
        self.assertTrue(a("comeca_com", "Setor 1", "setor"))
        self.assertTrue(a("em_lista", "Campo", "setor, campo"))
        self.assertFalse(a("em_lista", "igreja", "setor, campo"))
        self.assertTrue(a("maior", "12", "10"))
        self.assertTrue(a("menor", "9,5", "10"))
        self.assertFalse(a("maior", "abc", "10"))
        self.assertTrue(a("nao_existe", "  ", ""))

    def test_validacao(self):
        self.assertTrue(motor.validar_etapas([{"tipo": "handoff", "destino": "fila"}]))
        self.assertFalse(motor.validar_etapas([{"tipo": "handoff", "destino": "sede"}]))
        self.assertTrue(motor.validar_etapas([{"tipo": "handoff", "destino": "fila", "fila": "x", "liberacao": True}], {"x"}))
        self.assertTrue(motor.validar_etapas([{"tipo": "notificar", "texto": ""}]))
        self.assertTrue(motor.validar_etapas([{"tipo": "condicao", "variavel": "a", "operador": "maior", "valor": "x"}]))

    def test_so_aceita_o_que_existe(self):
        pergunta = {"tipo": "pergunta", "texto": "Qual?", "variavel": "assunto", "opcoes": ["Documento", "Oração"]}
        cond = lambda v, val, op="igual", var="assunto": [pergunta, {"tipo": "condicao", "variavel": var, "operador": op, "valor": val}]
        self.assertFalse(motor.validar_etapas(cond("Documento", "Documento")))
        self.assertTrue(motor.validar_etapas(cond("x", "Batizado")))                      # resposta que a pergunta não oferece
        self.assertTrue(motor.validar_etapas(cond("x", "Documento, Batizado", "em_lista")))
        self.assertTrue(motor.validar_etapas(cond("x", "Documento", var="inventada")))     # memória que não existe
        self.assertTrue(motor.validar_etapas(cond("x", "regiao", var="unidade_tipo")))      # valor fora da lista do sistema
        self.assertFalse(motor.validar_etapas(cond("x", "setor", var="unidade_tipo")))
        self.assertTrue(motor.validar_etapas([{"tipo": "mensagem", "texto": "Oi {{fulano}}"}]))
        self.assertTrue(motor.validar_etapas([{"tipo": "pergunta", "texto": "?", "variavel": "a", "opcoes": ["Sim", "sim"]}]))

    def test_simulacao_mostra_destino_e_aviso(self):
        etapas = [{"tipo": "notificar", "texto": "Olá Sede, {{nome}}"}, {"tipo": "handoff", "destino": "sede", "liberacao": True}]
        r = motor.simular(etapas, [])
        self.assertIn("Sede", r["final"])
        self.assertEqual(r["avisos_sede"], ["Olá Sede, "])

    def test_condicao_por_origem(self):
        etapas = [{"tipo": "condicao", "variavel": "origem", "operador": "igual", "valor": "sede", "ir_para": 2, "senao_ir_para": 3},
                  {"tipo": "mensagem", "texto": "da sede"}, {"tipo": "mensagem", "texto": "de uma igreja"}]
        self.assertIn("da sede", [m["texto"] for m in motor.simular(etapas, [], {"origem": "sede"})["conversa"]])
        self.assertIn("de uma igreja", [m["texto"] for m in motor.simular(etapas, [], {"origem": "unidade"})["conversa"]])

    # ---- ponta a ponta
    def test_pedido_vai_direto_para_a_sede_e_o_setor_nao_ve(self):
        self.publicar("Documento", [{"tipo": "handoff", "destino": "sede", "liberacao": True, "texto": "Enviado à Sede."}])
        cid = self.contato_da_igreja("Maria Doc", "Igreja Central")
        conv = self.p.receber_mensagem(self.emp, cid, "web", "preciso de um documento")
        self.assertEqual(conv["exclusiva_sede"], 1)
        self.assertEqual(conv["liberacao"], "pendente")
        admin, sup, atendente = self.ator("admin"), self.ator("supervisor"), self.ator("atendente")
        self.assertEqual(self.p.obter_conversa(admin, conv["id"])["id"], conv["id"])
        for quem in (sup, atendente):
            with self.assertRaises(NaoEncontrado):
                self.p.obter_conversa(quem, conv["id"])
            self.assertNotIn(conv["id"], [c["id"] for c in self.p.listar_conversas(quem)])
        # responder trava até liberar; só a Sede libera
        with self.assertRaises(ErroNegocio):
            self.p.responder(admin, conv["id"], "oi")
        with self.assertRaises(Exception):
            self.p.decidir_liberacao(sup, conv["id"], True)
        r = self.p.decidir_liberacao(admin, conv["id"], True, "Pode emitir")
        self.assertEqual(r["liberacao"], "liberada")
        self.p.responder(admin, conv["id"], "Documento liberado.")
        with self.assertRaises(ErroNegocio):
            self.p.decidir_liberacao(admin, conv["id"], True)

    def test_pedido_comum_continua_visivel_ao_setor(self):
        self.publicar("Comum", [{"tipo": "handoff", "destino": "fila", "fila": self.fila()}], valor="visita")
        cid = self.contato_da_igreja("João Visita", "Igreja Central")
        conv = self.p.receber_mensagem(self.emp, cid, "web", "quero uma visita")
        self.assertEqual(conv["exclusiva_sede"], 0)
        self.assertEqual(self.p.obter_conversa(self.ator("supervisor"), conv["id"])["id"], conv["id"])

    def test_aviso_vira_alerta_so_para_quem_pode_ver(self):
        self.publicar("Oração", [{"tipo": "notificar", "texto": "Oração para a Sede de {{unidade}}"},
                                 {"tipo": "handoff", "destino": "sede"}], valor="oracao")
        cid = self.contato_da_igreja("Ana Oração", "Igreja Central")
        conv = self.p.receber_mensagem(self.emp, cid, "web", "pedido de oracao")
        textos = [a["texto"] for a in self.p.listar_alertas(self.ator("admin"))["itens"]]
        self.assertIn("Oração para a Sede de Igreja Central", textos)
        self.assertTrue(all(a.get("referencia") != conv["id"] for a in self.p.listar_alertas(self.ator("supervisor"))["itens"]))

    def test_condicao_usa_a_igreja_da_pessoa(self):
        self.publicar("Por tipo", [
            {"tipo": "condicao", "variavel": "unidade_tipo", "operador": "em_lista", "valor": "igreja, congregacao", "ir_para": 2, "senao_ir_para": 3},
            {"tipo": "tag", "tag": "veio-de-igreja"}, {"tipo": "handoff", "destino": "fila", "fila": self.fila()}], valor="tipo")
        cid = self.contato_da_igreja("Pedro", "Igreja Bairro Novo")
        self.p.receber_mensagem(self.emp, cid, "web", "tipo")
        self.assertIn("veio-de-igreja", self.p.obter_contato(self.ator("admin"), cid).get("tags", []))


if __name__ == "__main__":
    unittest.main()
