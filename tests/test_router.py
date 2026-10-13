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


    @unittest.mock.patch("core.web_search.pesquisar", return_value=(True, "Fontes atuais"))
    def test_pesquisa_web_nao_depende_do_fallback_ollama(self, mock_pesquisar):
        brain = MagicMock(return_value="fallback não deveria ser chamado")
        router = Router(self.intent_engine, self.executor, brain_fallback=brain)

        resultado, intent = router.handle("pesquise na internet sobre a capital do Chile")

        self.assertEqual(intent["intent"], "PESQUISAR_WEB")
        self.assertEqual(resultado, "Fontes atuais")
        mock_pesquisar.assert_called_once_with("a capital do Chile")
        brain.assert_not_called()

    def test_abrir_programa_conhecido_usa_descoberta_real_quando_agente_disponivel(self):
        agente = MagicMock()
        router = Router(self.intent_engine, self.executor, agente=agente)

        resultado, intent = router.handle("abra o chrome")

        self.assertEqual(intent["intent"], "ABRIR")
        agente.abrir_aplicativo_generico.assert_called_once_with("chrome")
        self.assertEqual(resultado, agente.abrir_aplicativo_generico.return_value)
        agente.executar_tarefa.assert_not_called()

    def test_fechar_word_exige_confirmacao_e_depois_usa_descoberta_real(self):
        agente = MagicMock()
        router = Router(self.intent_engine, self.executor, agente=agente)

        pergunta, intent = router.handle("feche o Word")

        self.assertEqual(intent["intent"], "FECHAR")
        self.assertIn("sim", pergunta.lower())
        agente.fechar_aplicativo_generico.assert_not_called()

        resultado, intent_confirmacao = router.handle("sim")

        agente.fechar_aplicativo_generico.assert_called_once_with("word")
        self.assertEqual(resultado, agente.fechar_aplicativo_generico.return_value)


if __name__ == "__main__":
    unittest.main()
