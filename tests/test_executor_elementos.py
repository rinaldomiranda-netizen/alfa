"""
Testes das capacidades adicionadas ao Executor nesta etapa: arquivos/
pastas, teclas avulsas/atalhos, sinais de atendimento e delegação ao
FormFiller (ação orientada a elementos).
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from computer.executor import (
    ENCERRAR_ATENDIMENTO_SINAL,
    Executor,
    INICIAR_ATENDIMENTO_SINAL,
)


class TestExecutorArquivosEPastas(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.os.startfile")
    def test_abrir_pasta_por_caminho_absoluto(self, mock_startfile):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = self.executor.executar({"intent": "ABRIR_PASTA", "nome": tmp})
            mock_startfile.assert_called_once_with(tmp)
            self.assertIn("aberta", resultado)

    @patch("computer.executor.os.startfile")
    def test_abrir_pasta_conhecida_por_nome(self, mock_startfile):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("computer.executor.PASTAS_CONHECIDAS", {"downloads": tmp}):
                resultado = self.executor.executar({"intent": "ABRIR_PASTA", "nome": "downloads"})
                mock_startfile.assert_called_once_with(tmp)
                self.assertIn("downloads", resultado.lower())

    def test_abrir_pasta_nao_encontrada(self):
        with patch.dict("computer.executor.PASTAS_CONHECIDAS", {}, clear=True):
            resultado = self.executor.executar(
                {"intent": "ABRIR_PASTA", "nome": "pasta-que-nao-existe-em-lugar-nenhum"}
            )
            self.assertIn("não encontrei", resultado.lower())

    @patch("computer.executor.os.startfile")
    def test_abrir_arquivo_por_caminho_absoluto(self, mock_startfile):
        with tempfile.NamedTemporaryFile(delete=False) as arquivo_tmp:
            caminho = arquivo_tmp.name
        try:
            resultado = self.executor.executar({"intent": "ABRIR_ARQUIVO", "nome": caminho})
            mock_startfile.assert_called_once_with(caminho)
            self.assertIn("aberto", resultado)
        finally:
            os.remove(caminho)

    def test_abrir_arquivo_sem_nome(self):
        resultado = self.executor.executar({"intent": "ABRIR_ARQUIVO", "nome": None})
        self.assertIn("não entendi", resultado.lower())


class TestExecutorTeclasEAtalhos(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    @patch("computer.executor.pyautogui.press")
    def test_pressionar_tecla(self, mock_press):
        resultado = self.executor.executar({"intent": "PRESSIONAR_TECLA", "tecla": "delete"})
        mock_press.assert_called_once_with("delete")
        self.assertIn("delete", resultado)

    def test_pressionar_tecla_sem_tecla(self):
        resultado = self.executor.executar({"intent": "PRESSIONAR_TECLA", "tecla": None})
        self.assertIn("não entendi", resultado.lower())

    @patch("computer.executor.pyautogui.hotkey")
    def test_atalho_salvar(self, mock_hotkey):
        resultado = self.executor.executar(
            {"intent": "ATALHO", "nome": "salvar", "teclas": ("ctrl", "s")}
        )
        mock_hotkey.assert_called_once_with("ctrl", "s")
        self.assertIn("Atalho", resultado)


class TestExecutorSinaisDeAtendimento(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    def test_iniciar_atendimento_retorna_sinal(self):
        resultado = self.executor.executar({"intent": "INICIAR_ATENDIMENTO"})
        self.assertEqual(resultado, INICIAR_ATENDIMENTO_SINAL)

    def test_encerrar_atendimento_retorna_sinal(self):
        resultado = self.executor.executar({"intent": "ENCERRAR_ATENDIMENTO"})
        self.assertEqual(resultado, ENCERRAR_ATENDIMENTO_SINAL)


class TestExecutorDelegacaoFormFiller(unittest.TestCase):

    def test_sem_form_filler_retorna_mensagem_clara(self):
        executor = Executor(form_filler=None)
        resultado = executor.executar(
            {"intent": "PREENCHER_CAMPO", "campo": "Nome", "valor": "Ana"}
        )
        self.assertIn("não está disponível", resultado.lower())

    def test_preencher_campo_delega_para_form_filler(self):
        form_filler = MagicMock()
        form_filler.preencher_texto.return_value = "Preenchi 'Nome' com 'Ana'."
        executor = Executor(form_filler=form_filler)

        resultado = executor.executar(
            {"intent": "PREENCHER_CAMPO", "campo": "Nome", "valor": "Ana"}
        )

        form_filler.preencher_texto.assert_called_once_with("Nome", "Ana")
        self.assertEqual(resultado, "Preenchi 'Nome' com 'Ana'.")

    def test_clicar_elemento_delega_para_clicar_botao(self):
        form_filler = MagicMock()
        form_filler.clicar_botao.return_value = "Cliquei em 'Salvar'."
        executor = Executor(form_filler=form_filler)

        resultado = executor.executar({"intent": "CLICAR_ELEMENTO", "nome": "Salvar"})

        form_filler.clicar_botao.assert_called_once_with("Salvar")
        self.assertEqual(resultado, "Cliquei em 'Salvar'.")

    def test_marcar_caixa_delega_com_flag_correta(self):
        form_filler = MagicMock()
        executor = Executor(form_filler=form_filler)

        executor.executar({"intent": "MARCAR_CAIXA", "campo": "Concordo", "marcar": False})

        form_filler.marcar_checkbox.assert_called_once_with("Concordo", False)

    def test_selecionar_opcao_delega(self):
        form_filler = MagicMock()
        executor = Executor(form_filler=form_filler)

        executor.executar({"intent": "SELECIONAR_OPCAO", "campo": "Gênero", "opcao": "Masculino"})

        form_filler.selecionar_opcao.assert_called_once_with("Gênero", "Masculino")

    def test_localizar_delega(self):
        form_filler = MagicMock()
        form_filler.localizar.return_value = "Encontrei 'Salvar' na tela, na posição 10 por 20."
        executor = Executor(form_filler=form_filler)

        resultado = executor.executar({"intent": "LOCALIZAR", "alvo": "Salvar"})

        form_filler.localizar.assert_called_once_with("Salvar")
        self.assertIn("Encontrei", resultado)

    def test_erro_no_form_filler_nao_propaga_excecao(self):
        form_filler = MagicMock()
        form_filler.preencher_texto.side_effect = RuntimeError("campo sumiu")
        executor = Executor(form_filler=form_filler)

        resultado = executor.executar(
            {"intent": "PREENCHER_CAMPO", "campo": "Nome", "valor": "Ana"}
        )

        self.assertIn("não consegui", resultado.lower())


if __name__ == "__main__":
    unittest.main()
