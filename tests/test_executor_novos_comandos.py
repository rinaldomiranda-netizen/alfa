"""
Testes dos comandos adicionados na segunda etapa de desenvolvimento:
teclado estendido, janelas, volume, ditado e energia do computador.

IMPORTANTE: subprocess.run é sempre mockado nos testes de
desligar/reiniciar/cancelar — nunca deve, em hipótese alguma, ser
chamado de verdade durante a suíte de testes.
"""

import unittest
from unittest.mock import patch

from computer.executor import Executor


class TestExecutorTecladoEstendido(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.pyautogui.write")
    def test_digitar_texto(self, mock_write):
        resultado = self.executor.executar({"intent": "DIGITAR", "texto": "Olá Mundo"})
        mock_write.assert_called_once_with("Olá Mundo", interval=0.01)
        self.assertIn("digitado", resultado.lower())

    @patch("computer.executor.pyautogui.write")
    def test_digitar_sem_texto_nao_chama_pyautogui(self, mock_write):
        resultado = self.executor.executar({"intent": "DIGITAR", "texto": None})
        mock_write.assert_not_called()
        self.assertIn("não entendi", resultado.lower())

    @patch("computer.executor.pyautogui.hotkey")
    def test_recortar_usa_ctrl_x(self, mock_hotkey):
        self.executor.executar({"intent": "RECORTAR"})
        mock_hotkey.assert_called_once_with("ctrl", "x")

    @patch("computer.executor.pyautogui.press")
    def test_tab(self, mock_press):
        self.executor.executar({"intent": "TAB"})
        mock_press.assert_called_once_with("tab")

    @patch("computer.executor.pyautogui.press")
    def test_backspace(self, mock_press):
        self.executor.executar({"intent": "BACKSPACE"})
        mock_press.assert_called_once_with("backspace")


class TestExecutorJanelas(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.pyautogui.hotkey")
    def test_minimizar_janela(self, mock_hotkey):
        self.executor.executar({"intent": "MINIMIZAR_JANELA"})
        mock_hotkey.assert_called_once_with("win", "down")

    @patch("computer.executor.pyautogui.hotkey")
    def test_maximizar_janela(self, mock_hotkey):
        self.executor.executar({"intent": "MAXIMIZAR_JANELA"})
        mock_hotkey.assert_called_once_with("win", "up")

    @patch("computer.executor.pyautogui.hotkey")
    def test_fechar_janela(self, mock_hotkey):
        self.executor.executar({"intent": "FECHAR_JANELA"})
        mock_hotkey.assert_called_once_with("alt", "f4")

    @patch("computer.executor.pyautogui.hotkey")
    def test_alternar_janela(self, mock_hotkey):
        self.executor.executar({"intent": "ALTERNAR_JANELA"})
        mock_hotkey.assert_called_once_with("alt", "tab")

    @patch("computer.executor.pyautogui.hotkey")
    def test_mostrar_area_trabalho(self, mock_hotkey):
        self.executor.executar({"intent": "MOSTRAR_AREA_TRABALHO"})
        mock_hotkey.assert_called_once_with("win", "d")


class TestExecutorVolume(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.pyautogui.press")
    def test_volume_aumentar_pressiona_tres_vezes(self, mock_press):
        self.executor.executar({"intent": "VOLUME_AUMENTAR"})
        self.assertEqual(mock_press.call_count, 3)
        mock_press.assert_called_with("volumeup")

    @patch("computer.executor.pyautogui.press")
    def test_volume_diminuir_pressiona_tres_vezes(self, mock_press):
        self.executor.executar({"intent": "VOLUME_DIMINUIR"})
        self.assertEqual(mock_press.call_count, 3)
        mock_press.assert_called_with("volumedown")

    @patch("computer.executor.pyautogui.press")
    def test_volume_mudo(self, mock_press):
        self.executor.executar({"intent": "VOLUME_MUDO"})
        mock_press.assert_called_once_with("volumemute")


class TestExecutorEnergiaComputador(unittest.TestCase):
    """
    Nunca chama shutdown de verdade: subprocess.run é sempre mockado.
    """

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.subprocess.run")
    def test_desligar_computador_usa_shutdown_com_atraso_de_60s(self, mock_run):
        mock_run.return_value.returncode = 0
        resultado = self.executor.executar({"intent": "DESLIGAR_COMPUTADOR"})
        mock_run.assert_called_once_with(
            ["shutdown", "/s", "/t", "60"], capture_output=True, text=True
        )
        self.assertIn("60 segundos", resultado)
        self.assertIn("cancelar desligamento", resultado.lower())

    @patch("computer.executor.subprocess.run")
    def test_reiniciar_computador_usa_shutdown_r(self, mock_run):
        mock_run.return_value.returncode = 0
        self.executor.executar({"intent": "REINICIAR_COMPUTADOR"})
        mock_run.assert_called_once_with(
            ["shutdown", "/r", "/t", "60"], capture_output=True, text=True
        )

    @patch("computer.executor.subprocess.run")
    def test_cancelar_desligamento_com_agendamento_existente(self, mock_run):
        mock_run.return_value.returncode = 0
        resultado = self.executor.executar({"intent": "CANCELAR_DESLIGAMENTO"})
        mock_run.assert_called_once_with(
            ["shutdown", "/a"], capture_output=True, text=True
        )
        self.assertIn("cancelado", resultado.lower())

    @patch("computer.executor.subprocess.run")
    def test_cancelar_desligamento_sem_agendamento(self, mock_run):
        mock_run.return_value.returncode = 1
        resultado = self.executor.executar({"intent": "CANCELAR_DESLIGAMENTO"})
        self.assertIn("não havia", resultado.lower())


if __name__ == "__main__":
    unittest.main()
