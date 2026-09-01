"""
Testes do roteador: comandos locais reconhecidos NÃO podem ser
enviados ao mecanismo de IA de fallback; só intents DESCONHECIDO
seguem para lá.
"""

import unittest
import unittest.mock
from unittest.mock import MagicMock

from core.intent_engine import IntentEngine
from core.router import Router
from computer.executor import Executor


class TestRouter(unittest.TestCase):

    def setUp(self):
        self.intent_engine = IntentEngine()
        self.executor = Executor()

    def test_comando_local_reconhecido_nao_chama_ia(self):
        brain = MagicMock(return_value="não deveria ser chamado")
        router = Router(self.intent_engine, self.executor, brain_fallback=brain)

        with unittest.mock.patch("computer.executor.pyautogui.click"):
            resultado, intent = router.handle("clique")

        brain.assert_not_called()
        self.assertEqual(intent["intent"], "CLIQUE")
        self.assertIn("realizado", resultado)

    def test_comando_desconhecido_vai_para_ia(self):
        brain = MagicMock(return_value="resposta da ia")
        router = Router(self.intent_engine, self.executor, brain_fallback=brain)

        resultado, intent = router.handle("me conte uma piada sobre bananas")

        brain.assert_called_once_with("me conte uma piada sobre bananas")
        self.assertEqual(intent["intent"], "DESCONHECIDO")
        self.assertEqual(resultado, "resposta da ia")

    def test_falha_na_ia_nao_derruba_o_roteador(self):
        brain = MagicMock(side_effect=RuntimeError("ollama fora do ar"))
        router = Router(self.intent_engine, self.executor, brain_fallback=brain)

        resultado, intent = router.handle("frase totalmente desconhecida xyz")

        self.assertEqual(intent["intent"], "DESCONHECIDO")
        self.assertIn("não consegui", resultado.lower())

    def test_sem_ia_configurada_retorna_mensagem_padrao(self):
        router = Router(self.intent_engine, self.executor, brain_fallback=None)
        resultado, intent = router.handle("frase totalmente desconhecida xyz")
        self.assertEqual(intent["intent"], "DESCONHECIDO")
        self.assertTrue(len(resultado) > 0)


if __name__ == "__main__":
    unittest.main()
