import tempfile
import unittest
from pathlib import Path

from modules.atendimento.store import AtendimentoStore


class TestAtendimentoStore(unittest.TestCase):
    def test_salvar_obter_e_filtrar_por_empresa(self):
        with tempfile.TemporaryDirectory() as d:
            store = AtendimentoStore(Path(d) / "sessoes.json")
            item = {"atendimento_id": "a1", "empresa_id": "empresa-1", "nome_pessoa": "Teste"}
            store.salvar(item)
            self.assertEqual(store.obter("a1")["nome_pessoa"], "Teste")
            self.assertEqual(len(store.listar("empresa-1")), 1)
            self.assertEqual(store.listar("empresa-2"), [])


if __name__ == "__main__":
    unittest.main()
