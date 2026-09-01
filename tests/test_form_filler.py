"""
Testes do FormFiller (computer/form_filler.py): a camada de
preenchimento orientada a ELEMENTOS, não a coordenadas fixas.

vision.ui_automation e vision.screen_vision são sempre mockados —
estes testes não dependem de nenhuma janela real aberta na tela.
"""

import unittest
from unittest.mock import patch

from computer.form_filler import ElementoNaoEncontrado, FormFiller

ELEMENTO_UIA = {"wrapper": object(), "nome": "Nome completo", "tipo": "Edit", "x": 100, "y": 200}


class TestFormFillerViaUIA(unittest.TestCase):

    def setUp(self):
        self.form_filler = FormFiller(pausa_entre_acoes=0)

    @patch("computer.form_filler.ui_automation.digitar_no_elemento", return_value=True)
    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=ELEMENTO_UIA)
    def test_preencher_texto_via_uia(self, mock_encontrar, mock_digitar):
        resultado = self.form_filler.preencher_texto("Nome completo", "João da Silva")

        mock_digitar.assert_called_once_with(ELEMENTO_UIA, "João da Silva")
        self.assertIn("Nome completo", resultado)
        self.assertIn("João da Silva", resultado)

    @patch("computer.form_filler.ui_automation.marcar_checkbox", return_value=True)
    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=ELEMENTO_UIA)
    def test_marcar_checkbox_via_uia(self, mock_encontrar, mock_marcar):
        self.form_filler.marcar_checkbox("Concordo", marcar=True)
        mock_marcar.assert_called_once_with(ELEMENTO_UIA, True)

    @patch("computer.form_filler.ui_automation.clicar_elemento", return_value=True)
    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=ELEMENTO_UIA)
    def test_clicar_botao_via_uia(self, mock_encontrar, mock_clicar):
        resultado = self.form_filler.clicar_botao("Salvar")
        mock_clicar.assert_called_once_with(ELEMENTO_UIA)
        self.assertIn("Salvar", resultado)

    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=None)
    def test_elemento_nao_encontrado_levanta_excecao(self, mock_encontrar):
        with patch("computer.form_filler.screen_vision.ocr_disponivel", return_value=False):
            with self.assertRaises(ElementoNaoEncontrado):
                self.form_filler.clicar_botao("Botão Fantasma")


class TestFormFillerFallbackOCR(unittest.TestCase):

    def setUp(self):
        self.form_filler = FormFiller(pausa_entre_acoes=0)

    @patch("computer.form_filler.pyautogui.click")
    @patch("computer.form_filler.pyautogui.write")
    @patch("computer.form_filler.pyautogui.hotkey")
    @patch("computer.form_filler.screen_vision.localizar_texto")
    @patch("computer.form_filler.screen_vision.ocr_disponivel", return_value=True)
    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=None)
    def test_preencher_texto_via_ocr_quando_uia_nao_encontra(
        self, mock_uia, mock_ocr_disp, mock_localizar, mock_hotkey, mock_write, mock_click
    ):
        mock_localizar.return_value = {"texto": "Nome", "x": 300, "y": 400, "largura": 50, "altura": 20}

        resultado = self.form_filler.preencher_texto("Nome", "Maria")

        # Achado via OCR = achou o RÓTULO, não o campo (um <input>
        # vazio não tem texto para o OCR ler); por isso o clique é
        # deslocado para baixo do rótulo (ver FormFiller.__init__).
        mock_click.assert_called_once_with(300, 400 + self.form_filler.deslocamento_rotulo_ocr)
        mock_write.assert_called_once_with("Maria", interval=0.01)
        self.assertIn("Nome", resultado)

    @patch("computer.form_filler.screen_vision.ocr_disponivel", return_value=False)
    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=None)
    def test_sem_uia_e_sem_ocr_levanta_excecao(self, mock_uia, mock_ocr_disp):
        with self.assertRaises(ElementoNaoEncontrado):
            self.form_filler.preencher_texto("Campo Inexistente", "valor")


class TestFormFillerNavegacao(unittest.TestCase):

    def setUp(self):
        self.form_filler = FormFiller(pausa_entre_acoes=0)

    @patch("computer.form_filler.screen_vision.ocr_disponivel", return_value=False)
    @patch("computer.form_filler.ui_automation.clicar_elemento", return_value=True)
    @patch("computer.form_filler.ui_automation.encontrar_elemento")
    def test_avancar_tenta_varios_nomes_de_botao(self, mock_encontrar, mock_clicar, mock_ocr):
        # só "Avançar" existe na tela, não "Próximo".
        def encontrar(nome, tipo_controle=None, janela=None):
            return ELEMENTO_UIA if nome == "Avançar" else None

        mock_encontrar.side_effect = encontrar

        resultado = self.form_filler.avancar()
        self.assertIn("Avançar", resultado)

    @patch("computer.form_filler.screen_vision.ocr_disponivel", return_value=False)
    @patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=None)
    def test_avancar_sem_nenhum_botao_disponivel_levanta_excecao(self, mock_encontrar, mock_ocr):
        with self.assertRaises(ElementoNaoEncontrado):
            self.form_filler.avancar()

    def test_localizar_sem_encontrar(self):
        with patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=None), \
             patch("computer.form_filler.screen_vision.ocr_disponivel", return_value=False):
            resultado = self.form_filler.localizar("Campo Fantasma")
            self.assertIn("Não encontrei", resultado)

    def test_localizar_encontrando_via_uia(self):
        with patch("computer.form_filler.ui_automation.encontrar_elemento", return_value=ELEMENTO_UIA):
            resultado = self.form_filler.localizar("Nome completo")
            self.assertIn("100", resultado)
            self.assertIn("200", resultado)


if __name__ == "__main__":
    unittest.main()
