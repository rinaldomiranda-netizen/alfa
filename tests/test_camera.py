"""
Testes do fluxo de consentimento da câmera (vision/camera.py).

cv2.VideoCapture é sempre mockado — estes testes nunca acessam uma
câmera de verdade. O foco é a REGRA DE PRIVACIDADE: nenhuma foto é
capturada sem consentimento, e nenhuma foto é associada a um
atendimento sem consentimento E confirmação da prévia.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from vision import camera


class TestConsentimentoObrigatorio(unittest.TestCase):

    def test_capturar_foto_sem_consentimento_levanta_permission_error(self):
        sessao = camera.SessaoCamera()
        with self.assertRaises(PermissionError):
            sessao.capturar_foto()

    def test_associar_sem_consentimento_e_confirmacao_levanta_permission_error(self):
        sessao = camera.SessaoCamera()
        with self.assertRaises(PermissionError):
            sessao.associar_ao_atendimento("atendimento-123")

    @patch("vision.camera.detectar_camera", return_value=True)
    @patch("vision.camera.cv2.VideoCapture")
    def test_associar_apenas_com_consentimento_sem_confirmacao_falha(self, mock_video, mock_detectar):
        mock_captura = MagicMock()
        mock_captura.read.return_value = (True, "frame-fake")
        mock_video.return_value = mock_captura

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(camera, "PASTA_TEMP", tmp), \
                 patch("vision.camera.cv2.imwrite", return_value=True):
                sessao = camera.SessaoCamera()
                sessao.registrar_consentimento(True)
                sessao.capturar_foto()

                with self.assertRaises(PermissionError):
                    sessao.associar_ao_atendimento("atendimento-123")


class TestFluxoCompletoComConsentimento(unittest.TestCase):

    @patch("vision.camera.detectar_camera", return_value=True)
    @patch("vision.camera.cv2.VideoCapture")
    @patch("vision.camera.cv2.imwrite")
    def test_fluxo_completo_ate_associar(self, mock_imwrite, mock_video, mock_detectar):
        # cv2.imwrite é mockado (não escreve JPEG de verdade), mas
        # precisa deixar um arquivo real no caminho para que os
        # checks de os.path.exists() do fluxo de consentimento passem.
        mock_imwrite.side_effect = lambda caminho, frame: open(caminho, "wb").close()

        mock_captura = MagicMock()
        mock_captura.read.return_value = (True, "frame-fake")
        mock_video.return_value = mock_captura

        with tempfile.TemporaryDirectory() as tmp_temp, tempfile.TemporaryDirectory() as tmp_atend:
            with patch.object(camera, "PASTA_TEMP", tmp_temp), \
                 patch.object(camera, "PASTA_ATENDIMENTOS", tmp_atend), \
                 patch("os.replace", side_effect=lambda origem, destino: open(destino, "wb").close()):

                sessao = camera.SessaoCamera()
                sessao.registrar_consentimento(True)
                caminho_preview = sessao.capturar_foto()
                self.assertTrue(caminho_preview.endswith(".jpg"))

                sessao.confirmar(True)
                destino = sessao.associar_ao_atendimento("atendimento-123")

                self.assertTrue(destino.endswith("atendimento-123_foto.jpg"))

    def test_recusar_a_previa_apaga_o_arquivo_temporario(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho_fake = os.path.join(tmp, "preview_fake.jpg")
            with open(caminho_fake, "wb") as arquivo:
                arquivo.write(b"fake")

            sessao = camera.SessaoCamera()
            sessao.registrar_consentimento(True)
            sessao.caminho_preview = caminho_fake

            sessao.confirmar(False)

            self.assertFalse(os.path.exists(caminho_fake))
            self.assertIsNone(sessao.caminho_preview)

    def test_detectar_camera_indisponivel(self):
        with patch("vision.camera.cv2.VideoCapture") as mock_video:
            mock_instancia = MagicMock()
            mock_instancia.isOpened.return_value = False
            mock_video.return_value = mock_instancia

            self.assertFalse(camera.detectar_camera())


if __name__ == "__main__":
    unittest.main()
