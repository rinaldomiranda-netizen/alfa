import tempfile
import unittest
from pathlib import Path

from modules.atendimento.service import AtendimentoService
from modules.atendimento.store import AtendimentoStore


class TestAtendimentoService(unittest.TestCase):
    def test_empresa_obrigatoria(self):
        with tempfile.TemporaryDirectory() as d:
            service = AtendimentoService(store=AtendimentoStore(Path(d) / "s.json"))
            with self.assertRaises(ValueError):
                service.iniciar("", [])

    def test_iniciar_persiste_empresa(self):
        with tempfile.TemporaryDirectory() as d:
            store = AtendimentoStore(Path(d) / "s.json")
            service = AtendimentoService(store=store)
            mensagem = service.iniciar("empresa-1", [])
            self.assertTrue(mensagem)
            registros = store.listar("empresa-1")
            self.assertEqual(len(registros), 1)
            self.assertEqual(registros[0]["empresa_id"], "empresa-1")


if __name__ == "__main__":
    unittest.main()
