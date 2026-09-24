import unittest
from modules.atendimento.ui import renderizar_painel


class TestAtendimentoUI(unittest.TestCase):
    def test_renderiza_painel(self):
        html = renderizar_painel()
        self.assertIn("RMD Atendimento", html)
        self.assertIn("Atendimento", html)
        self.assertIn("Módulo ALPHA", html)


if __name__ == "__main__":
    unittest.main()
