from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from modules.atendimento.plataforma import Plataforma, demo, seguranca
from modules.atendimento.plataforma.duplicidade import Duplicidade
from modules.atendimento.plataforma.nucleo import ErroNegocio

_IT = seguranca.ITERACOES


class DuplicidadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seguranca.ITERACOES = 2_000
        cls.pasta = Path(tempfile.mkdtemp())
        cls.p = Plataforma(cls.pasta / "c.db", pasta_backups=cls.pasta / "bk")
        cls.p.envio_sincrono = True
        os.environ["RMD_EDICAO"] = "church"
        cls.demo = demo.garantir_demonstracao(cls.p)
        cls.emp = cls.demo["empresa_id"]
        u = cls.p.banco.um("SELECT * FROM usuarios WHERE id=?", (cls.demo["usuarios"]["admin"],))
        cls.ator = cls.p._ator(u, cls.emp)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("RMD_EDICAO", None)
        shutil.rmtree(cls.pasta, ignore_errors=True)
        seguranca.ITERACOES = _IT

    def test_mesmo_telefone_pergunta(self):
        a = self.p.criar_contato(self.ator, {"nome": "Maria Souza", "telefone": "79 99999-1000"})
        with self.assertRaises(Duplicidade) as e:
            self.p.criar_contato(self.ator, {"nome": "Maria S.", "telefone": "(79) 99999-1000", "email": "m@x.com"})
        self.assertFalse(e.exception.pode_criar)
        self.assertEqual(e.exception.candidatos[0]["id"], a["id"])
        with self.assertRaises(ErroNegocio):  # mesmo telefone nunca vira "pessoas diferentes"
            self.p.criar_contato(self.ator, {"nome": "Maria S.", "telefone": "79999991000", "duplicidade": {"acao": "criar"}})

    def test_manter_completa_vazios(self):
        a = self.p.criar_contato(self.ator, {"nome": "Joao Lima", "telefone": "79 98888-2000"})
        r = self.p.criar_contato(self.ator, {"nome": "João Lima", "telefone": "79 98888-2000", "email": "j@x.com", "tags": "membro",
                                             "duplicidade": {"acao": "manter", "id": a["id"]}})
        self.assertEqual(r["id"], a["id"])
        self.assertEqual(r["email"], "j@x.com")
        self.assertIn("membro", r["tags"])

    def test_mesmo_nome_pode_criar(self):
        self.p.criar_contato(self.ator, {"nome": "Zilda Pimentel", "telefone": "79 97777-3000"})
        with self.assertRaises(Duplicidade) as e:
            self.p.criar_contato(self.ator, {"nome": "zilda  pimentel", "telefone": "79 97777-3001"})
        self.assertTrue(e.exception.pode_criar)
        r = self.p.criar_contato(self.ator, {"nome": "zilda pimentel", "telefone": "79 97777-3001", "duplicidade": {"acao": "criar"}})
        self.assertTrue(r["id"])

    def test_mesclar_move_historico(self):
        a = self.p.criar_contato(self.ator, {"nome": "Pedro Alves", "telefone": "79 96666-4000"})
        b = self.p.criar_contato(self.ator, {"nome": "Pedro A", "email": "p@x.com", "observacoes": "visita"})
        self.p.banco.executar("INSERT INTO igreja_jornada(id,empresa_id,contato_id,etapa,criado_em,atualizado_em) VALUES ('j1',?,?,'novo','x','x')", (self.emp, b["id"]))
        r = self.p.mesclar_contatos(self.ator, a["id"], b["id"])
        self.assertEqual(r["email"], "p@x.com")
        self.assertIn("visita", r["observacoes"])
        self.assertIsNone(self.p.banco.um("SELECT 1 FROM contatos WHERE id=?", (b["id"],)))
        self.assertTrue(self.p.banco.um("SELECT 1 FROM igreja_jornada WHERE contato_id=?", (a["id"],)))

    def test_varredura_e_edicao(self):
        a = self.p.criar_contato(self.ator, {"nome": "Rita Costa", "telefone": "79 95555-5000"})
        b = self.p.criar_contato(self.ator, {"nome": "Rita C", "telefone": "79 95555-5001"})
        with self.assertRaises(Duplicidade):
            self.p.editar_contato(self.ator, b["id"], {"nome": "Rita Costa"})
        r = self.p.editar_contato(self.ator, b["id"], {"nome": "Rita Costa", "duplicidade": {"acao": "mesclar", "id": a["id"], "manter": "outro"}})
        self.assertEqual(r["id"], a["id"])
        self.assertEqual(r["whatsapp"], "5579955555000")


if __name__ == "__main__":
    unittest.main()
