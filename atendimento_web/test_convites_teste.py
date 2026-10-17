from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from modules.atendimento.plataforma import Plataforma, demo, seguranca
from modules.atendimento.plataforma.nucleo import NaoEncontrado

_IT = seguranca.ITERACOES


class ConvitesTesteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seguranca.ITERACOES = 2_000
        cls.pasta = Path(tempfile.mkdtemp())
        cls.p = Plataforma(cls.pasta / "c.db", pasta_backups=cls.pasta / "bk")
        os.environ["RMD_EDICAO"] = "church"
        owner = demo.garantir_owner(cls.p)
        cls.owner = cls.p._ator(owner, None)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("RMD_EDICAO", None)
        shutil.rmtree(cls.pasta, ignore_errors=True)
        seguranca.ITERACOES = _IT

    def test_convite_so_na_demo_e_encerra(self):
        r = self.p.criar_convite_teste(self.owner, "Pastor João")
        u = self.p.banco.um("SELECT * FROM usuarios WHERE id=?", (r["id"],))
        emp = self.p.empresa_por_slug("demonstracao")
        self.assertEqual(u["empresa_id"], emp["id"])
        self.assertEqual(u["perfil"], "admin")
        self.assertTrue(seguranca.conferir_senha("1234", u["senha_salt"], u["senha_hash"]))
        self.assertEqual(len(self.p.listar_convites_teste(self.owner)), 1)
        self.p.encerrar_convite_teste(self.owner, r["id"])
        self.assertFalse(self.p.listar_convites_teste(self.owner)[0]["ativo"])
        with self.assertRaises(NaoEncontrado):  # não encerra usuário de outra coisa
            self.p.encerrar_convite_teste(self.owner, self.p.banco.um("SELECT id FROM usuarios WHERE email='admin@demonstracao.local'")["id"])


if __name__ == "__main__":
    unittest.main()
