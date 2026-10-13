import unittest
from unittest.mock import MagicMock, patch

from agente.orquestrador import AgenteExecutor


class TestFechamentoAppDescoberto(unittest.TestCase):
    def setUp(self):
        self.agente = object.__new__(AgenteExecutor)
        self.agente.registro = MagicMock()

    @patch("agente.descoberta_apps.localizar_executavel")
    @patch("psutil.process_iter")
    def test_fecha_word_quando_executavel_existe_e_processo_bate(self, mock_process_iter, mock_localizar):
        mock_localizar.return_value = r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
        processo = MagicMock()
        processo.info = {
            "name": "WINWORD.EXE",
            "exe": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        }
        mock_process_iter.return_value = [processo]

        resultado = self.agente.fechar_aplicativo_generico("word")

        processo.terminate.assert_called_once_with()
        self.assertIn("Fechei word", resultado)
        mock_localizar.assert_called_once_with("word")

    @patch("agente.descoberta_apps.localizar_executavel")
    @patch("psutil.process_iter")
    def test_nao_tenta_encerrar_nome_que_nao_esta_no_catalogo(self, mock_process_iter, mock_localizar):
        mock_process_iter.return_value = []
        mock_localizar.assert_not_called()

        resultado = self.agente.fechar_aplicativo_generico("aplicativo inventado")
        self.assertIn("método seguro configurado", resultado)
        mock_process_iter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
