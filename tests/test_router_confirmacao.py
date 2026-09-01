"""
Testes do fluxo de confirmação de ações sensíveis (seção 14 da
especificação: "segurança e confirmações para ações sensíveis").

ATENÇÃO: todo teste envolvendo DESLIGAR_COMPUTADOR/REINICIAR_COMPUTADOR
mocka computer.executor.subprocess.run. Isso NUNCA deve ser removido:
sem o mock, esses testes desligariam/reiniciariam a máquina de verdade.
"""

import unittest
from unittest.mock import MagicMock, patch

from computer.executor import Executor
from core.intent_engine import IntentEngine
from core.router import Router


class TestConfirmacaoFecharPrograma(unittest.TestCase):

    def setUp(self):
        self.router = Router(IntentEngine(), Executor())

    def test_fechar_programa_pede_confirmacao_e_nao_executa_direto(self):
        with patch("computer.executor.psutil.process_iter") as mock_iter:
            resultado, intent = self.router.handle("feche a calculadora")
            mock_iter.assert_not_called()

        self.assertIn("confirma", resultado.lower())
        self.assertIsNotNone(self.router.pendente)
        self.assertEqual(self.router.pendente["intent"], "FECHAR")

    def test_confirmacao_positiva_executa_a_acao_pendente(self):
        self.router.handle("feche a calculadora")

        with patch("computer.executor.psutil.process_iter", return_value=[]):
            resultado, intent = self.router.handle("sim")

        self.assertIsNone(self.router.pendente)
        self.assertIn("calculadora", resultado.lower())

    def test_confirmacao_negativa_cancela_sem_executar(self):
        self.router.handle("feche a calculadora")

        with patch("computer.executor.psutil.process_iter") as mock_iter:
            resultado, intent = self.router.handle("não")
            mock_iter.assert_not_called()

        self.assertEqual(resultado, "Ação cancelada.")
        self.assertIsNone(self.router.pendente)

    def test_resposta_ambigua_cancela_pendencia_e_processa_novo_comando(self):
        self.router.handle("feche a calculadora")

        with patch("computer.executor.pyautogui.click") as mock_click:
            resultado, intent = self.router.handle("clique")
            mock_click.assert_called_once()

        self.assertIsNone(self.router.pendente)
        self.assertEqual(intent["intent"], "CLIQUE")

    def test_sem_programa_reconhecido_nao_pede_confirmacao(self):
        resultado, intent = self.router.handle("feche o troço estranho aí")
        self.assertIsNone(self.router.pendente)
        self.assertIn("não entendi", resultado.lower())


class TestConfirmacaoEnergiaComputador(unittest.TestCase):

    def setUp(self):
        self.router = Router(IntentEngine(), Executor())

    def test_desligar_computador_pede_confirmacao_e_nao_chama_shutdown(self):
        with patch("computer.executor.subprocess.run") as mock_run:
            resultado, intent = self.router.handle("desligar o computador")
            mock_run.assert_not_called()

        self.assertIn("desligar o computador", resultado.lower())
        self.assertIsNotNone(self.router.pendente)
        self.assertEqual(self.router.pendente["intent"], "DESLIGAR_COMPUTADOR")

    def test_desligar_computador_confirmado_chama_shutdown_uma_vez(self):
        self.router.handle("desligar o computador")

        with patch("computer.executor.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            resultado, intent = self.router.handle("sim")
            mock_run.assert_called_once_with(
                ["shutdown", "/s", "/t", "60"], capture_output=True, text=True
            )

        self.assertIsNone(self.router.pendente)

    def test_reiniciar_computador_negado_nao_chama_shutdown(self):
        self.router.handle("reiniciar o computador")

        with patch("computer.executor.subprocess.run") as mock_run:
            resultado, intent = self.router.handle("cancela")
            mock_run.assert_not_called()

        self.assertEqual(resultado, "Ação cancelada.")

    def test_cancelar_desligamento_nao_e_uma_acao_sensivel(self):
        # "cancelar desligamento" é sempre seguro de executar direto,
        # não deve ficar pendente de confirmação.
        with patch("computer.executor.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            resultado, intent = self.router.handle("cancelar desligamento")
            mock_run.assert_called_once()

        self.assertIsNone(self.router.pendente)


class TestRoteamentoParaVisao(unittest.TestCase):

    def setUp(self):
        self.vision = MagicMock()
        self.router = Router(IntentEngine(), Executor(), vision=self.vision)

    def test_visualizar_chama_modulo_de_visao_local(self):
        self.vision.analisar_tela.return_value = "há uma janela do navegador aberta"
        resultado, intent = self.router.handle("olhe minha tela")

        self.vision.analisar_tela.assert_called_once()
        self.assertEqual(resultado, "há uma janela do navegador aberta")
        self.assertEqual(intent["intent"], "VISUALIZAR")

    def test_camera_chama_modulo_de_visao_local(self):
        self.vision.analisar_camera.return_value = "ambiente iluminado, sem pessoas"
        resultado, intent = self.router.handle("veja pela câmera")

        self.vision.analisar_camera.assert_called_once()
        self.assertEqual(resultado, "ambiente iluminado, sem pessoas")


if __name__ == "__main__":
    unittest.main()
