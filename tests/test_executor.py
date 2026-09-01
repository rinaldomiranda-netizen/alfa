"""
Testes do executor: garantem que intenção + parâmetros realmente
chegam a uma chamada de sistema (pyautogui), com as coordenadas
corretas, e não apenas retornam uma mensagem de sucesso "fake".

pyautogui é mockado apenas na fronteira com o SO (a chamada real de
mover o cursor), para não mexer no mouse físico durante os testes
automatizados; a lógica do executor (cálculo de destino, dispatch de
intenção) roda de verdade.
"""

import unittest
from unittest.mock import patch

from computer.executor import Executor, SAIR


class TestExecutorMouse(unittest.TestCase):

    def setUp(self):
        self.executor = Executor(passo_pixels=100, duracao=0.01)

    @patch("computer.executor.pyautogui.moveTo")
    @patch("computer.executor.pyautogui.position", return_value=(500, 500))
    @patch("computer.executor.pyautogui.size", return_value=(1920, 1080))
    def test_mover_mouse_direita_chama_pyautogui_com_coordenadas_corretas(
        self, mock_size, mock_position, mock_move
    ):
        resultado = self.executor.executar(
            {"intent": "MOVER_MOUSE", "direcao": "direita"}
        )
        mock_move.assert_called_once_with(600, 500, duration=0.01)
        self.assertIn("direita", resultado)

    @patch("computer.executor.pyautogui.moveTo")
    @patch("computer.executor.pyautogui.position", return_value=(500, 500))
    @patch("computer.executor.pyautogui.size", return_value=(1920, 1080))
    def test_mover_mouse_esquerda(self, mock_size, mock_position, mock_move):
        self.executor.executar({"intent": "MOVER_MOUSE", "direcao": "esquerda"})
        mock_move.assert_called_once_with(400, 500, duration=0.01)

    @patch("computer.executor.pyautogui.moveTo")
    @patch("computer.executor.pyautogui.position", return_value=(500, 500))
    @patch("computer.executor.pyautogui.size", return_value=(1920, 1080))
    def test_mover_mouse_respeita_limites_da_tela(self, mock_size, mock_position, mock_move):
        mock_position.return_value = (10, 10)
        self.executor.executar({"intent": "MOVER_MOUSE", "direcao": "esquerda"})
        # x - 100 daria -90; deve ser sujado (clamp) para 0.
        mock_move.assert_called_once_with(0, 10, duration=0.01)

    def test_mover_mouse_sem_direcao_pede_direcao_e_nao_executa_nada(self):
        with patch("computer.executor.pyautogui.moveTo") as mock_move:
            resultado = self.executor.executar({"intent": "MOVER_MOUSE", "direcao": None})
            mock_move.assert_not_called()
            self.assertIn("qual lado", resultado.lower())

    @patch("computer.executor.pyautogui.mouseUp")
    @patch("computer.executor.pyautogui.mouseDown")
    @patch("computer.executor.pyautogui.moveTo")
    @patch("computer.executor.pyautogui.position", return_value=(500, 500))
    @patch("computer.executor.pyautogui.size", return_value=(1920, 1080))
    def test_arrastar_mouse_baixo(
        self, mock_size, mock_position, mock_move, mock_down, mock_up
    ):
        resultado = self.executor.executar(
            {"intent": "ARRASTAR_MOUSE", "direcao": "baixo"}
        )
        mock_down.assert_called_once()
        mock_move.assert_called_once_with(500, 600, duration=0.15)
        mock_up.assert_called_once()
        self.assertIn("baixo", resultado)


class TestExecutorOutrasAcoes(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.pyautogui.click")
    def test_clique_esquerdo(self, mock_click):
        self.executor.executar({"intent": "CLIQUE", "botao": "esquerdo"})
        mock_click.assert_called_once()

    @patch("computer.executor.pyautogui.rightClick")
    def test_clique_direito(self, mock_click):
        self.executor.executar({"intent": "CLIQUE", "botao": "direito"})
        mock_click.assert_called_once()

    @patch("computer.executor.pyautogui.doubleClick")
    def test_clique_duplo(self, mock_click):
        self.executor.executar({"intent": "CLIQUE", "botao": "duplo"})
        mock_click.assert_called_once()

    @patch("computer.executor.pyautogui.scroll")
    def test_scroll_baixo_usa_valor_negativo(self, mock_scroll):
        self.executor.executar({"intent": "SCROLL", "direcao": "baixo"})
        mock_scroll.assert_called_once_with(-500)

    @patch("computer.executor.pyautogui.scroll")
    def test_scroll_cima_usa_valor_positivo(self, mock_scroll):
        self.executor.executar({"intent": "SCROLL", "direcao": "cima"})
        mock_scroll.assert_called_once_with(500)

    @patch("computer.executor.pyautogui.hotkey")
    def test_copiar_usa_ctrl_c(self, mock_hotkey):
        self.executor.executar({"intent": "COPIAR"})
        mock_hotkey.assert_called_once_with("ctrl", "c")

    @patch("computer.executor.subprocess.Popen")
    def test_abrir_programa_permitido(self, mock_popen):
        resultado = self.executor.executar({"intent": "ABRIR", "programa": "calculadora"})
        mock_popen.assert_called_once_with("calc.exe", shell=True)
        self.assertIn("aberto", resultado)

    @patch("computer.executor.subprocess.Popen")
    def test_abrir_programa_nao_autorizado_nao_executa_nada(self, mock_popen):
        resultado = self.executor.executar(
            {"intent": "ABRIR", "programa": "algo perigoso nao cadastrado"}
        )
        mock_popen.assert_not_called()
        self.assertIn("permissão", resultado)

    def test_intencao_desconhecida_nao_executa_nada(self):
        resultado = self.executor.executar({"intent": "DESCONHECIDO"})
        self.assertEqual(resultado, "Comando não reconhecido.")

    def test_sair_retorna_sentinela(self):
        resultado = self.executor.executar({"intent": "SAIR"})
        self.assertEqual(resultado, SAIR)


if __name__ == "__main__":
    unittest.main()
