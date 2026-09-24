import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from modules.atendimento.service import AtendimentoService
from modules.atendimento.store import AtendimentoStore


class TestFinalizacaoAtendimento(unittest.TestCase):
    def test_finalizacao_preserva_id_real(self):
        with tempfile.TemporaryDirectory() as d:
            store = AtendimentoStore(Path(d) / "s.json")
            modulo = Mock()
            modulo.status.side_effect = [
                {"atendimento_id": "atd-123", "nome_pessoa": "Maria", "estado": "ATIVO"},
            ]
            modulo.finalizar.return_value = {"Nome": "Maria"}
            service = AtendimentoService(store=store, modulo=modulo)

            service.finalizar("empresa-1")

            registro = store.obter("atd-123")
            self.assertIsNotNone(registro)
            self.assertEqual(registro["empresa_id"], "empresa-1")
            self.assertEqual(registro["estado"], "FINALIZADO")


if __name__ == "__main__":
    unittest.main()
