"""Cargos da igreja: lista padrão, permissões por cargo (só tiram) e cargo nas conversas."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from modules.atendimento.plataforma import Plataforma, demo, seguranca
from modules.atendimento.plataforma.nucleo import Ator, ErroNegocio

_IT = seguranca.ITERACOES


class CargosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seguranca.ITERACOES = 2_000
        cls.pasta = Path(tempfile.mkdtemp())
        cls.p = Plataforma(cls.pasta / "c.db", pasta_backups=cls.pasta / "bk")
        cls.p.envio_sincrono = True
        os.environ["RMD_EDICAO"] = "church"
        cls.demo = demo.garantir_demonstracao(cls.p)
        cls.emp = cls.demo["empresa_id"]

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("RMD_EDICAO", None)
        shutil.rmtree(cls.pasta, ignore_errors=True)
        seguranca.ITERACOES = _IT

    def ator(self, perfil):
        u = self.p.banco.um("SELECT * FROM usuarios WHERE id=?", (self.demo["usuarios"][perfil],))
        return self.p._ator(u, self.emp)

    def cargo(self, nome):
        return next(g for g in self.p.listar_cargos(self.ator("admin")) if g["nome"].startswith(nome))

    def test_lista_padrao(self):
        nomes = [g["nome"] for g in self.p.listar_cargos(self.ator("admin"))]
        for esperado in ("Pastor presidente", "Presbítero", "Diácono", "Evangelista", "Tesoureiro", "Zelador", "Membro"):
            self.assertTrue(any(n.startswith(esperado) for n in nomes), esperado)

    def test_cargo_so_tira_permissao(self):
        admin = self.ator("admin")
        diacono = self.p.salvar_cargo(admin, {"nome": "Cargo teste", "nivel": 20, "restricoes": {
            "recursos": {"relatorios": False}, "acoes": {"conversas": {"encerrar": False}, "empresas": {"criar": False}}}})
        self.p.editar_usuario(admin, self.demo["usuarios"]["atendente"], {"cargo_id": diacono["id"]})
        a = self.ator("atendente")
        self.assertEqual(a.extras["cargo"]["nome"], "Cargo teste")
        self.assertFalse(a.pode("relatorios", "ver"))
        self.assertFalse(a.pode("conversas", "encerrar"))
        self.assertTrue(a.pode("conversas", "responder"))
        self.assertFalse(a.pode("usuarios", "criar"))      # nunca ganha o que o perfil não tem
        self.assertNotIn("empresas", diacono["restricoes"].get("acoes", {}))
        usuarios = {u["id"]: u for u in self.p.listar_usuarios(admin)}
        self.assertEqual(usuarios[self.demo["usuarios"]["atendente"]]["cargo_nome"], "Cargo teste")

    def test_cargo_em_uso_nao_apaga(self):
        admin = self.ator("admin")
        g = self.p.salvar_cargo(admin, {"nome": "Cargo em uso", "nivel": 5})
        self.p.editar_usuario(admin, self.demo["usuarios"]["supervisor"], {"cargo_id": g["id"]})
        with self.assertRaises(ErroNegocio):
            self.p.excluir_cargo(admin, g["id"])
        self.p.editar_usuario(admin, self.demo["usuarios"]["supervisor"], {"cargo_id": None})
        self.assertTrue(self.p.excluir_cargo(admin, g["id"])["ok"])

    def test_atendente_nao_cria_cargo(self):
        with self.assertRaises(Exception):
            self.p.salvar_cargo(self.ator("atendente"), {"nome": "X", "nivel": 1})

    def test_sem_celula(self):
        from modules.atendimento.plataforma import igreja
        self.assertNotIn("grupo", igreja.CHAVES_ETAPAS)
        nomes = [s["nome"] for s in self.p.banco.todos("SELECT nome FROM servicos WHERE empresa_id=?", (self.emp,))]
        self.assertFalse(any("célula" in n.lower() for n in nomes))


if __name__ == "__main__":
    unittest.main()
