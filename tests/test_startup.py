"""
Testes da inicialização automática com o Windows.

IMPORTANTE: `_pasta_inicializacao` é sempre mockada para apontar para
um diretório temporário. Isso garante que estes testes NUNCA criem
ou removam nada na pasta real de Inicialização do usuário
(shell:startup) — a ativação real só deve acontecer quando o usuário
rodar `python main.py --instalar-inicializacao` manualmente.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import startup


class TestStartupSeguro(unittest.TestCase):

    def test_nao_instalado_por_padrao_em_pasta_vazia(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("core.startup._pasta_inicializacao", return_value=tmp):
                self.assertFalse(startup.esta_instalado())

    def test_remover_sem_instalacao_previa_retorna_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("core.startup._pasta_inicializacao", return_value=tmp):
                self.assertFalse(startup.remover())

    def test_remover_apaga_atalho_existente(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, startup.NOME_ATALHO)
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write("atalho de teste")

            with patch("core.startup._pasta_inicializacao", return_value=tmp):
                self.assertTrue(startup.esta_instalado())
                self.assertTrue(startup.remover())
                self.assertFalse(os.path.exists(caminho))

    def test_instalar_cria_atalho_via_com_mockado_em_pasta_temporaria(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho_esperado = os.path.join(tmp, startup.NOME_ATALHO)

            shell_mock = MagicMock()
            atalho_mock = MagicMock()
            shell_mock.CreateShortCut.return_value = atalho_mock

            with patch("core.startup._pasta_inicializacao", return_value=tmp), \
                 patch("win32com.client.Dispatch", return_value=shell_mock):
                resultado = startup.instalar()

            shell_mock.CreateShortCut.assert_called_once_with(caminho_esperado)
            self.assertEqual(atalho_mock.TargetPath, "wscript.exe")
            atalho_mock.Save.assert_called_once()
            self.assertEqual(resultado, caminho_esperado)

    def test_instalar_falha_se_vbs_nao_existir(self):
        with patch("core.startup.VBS_PATH", "C:\\caminho\\que\\nao\\existe.vbs"):
            with self.assertRaises(FileNotFoundError):
                startup.instalar()


if __name__ == "__main__":
    unittest.main()
