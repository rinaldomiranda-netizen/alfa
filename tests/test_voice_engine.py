"""
Testes do motor de voz.

Não há microfone/hardware de áudio disponível neste ambiente de
execução automatizado, então estes testes validam a LÓGICA de
seleção e fallback (Windows Speech -> Whisper) via mocks, sem
capturar áudio real. Um teste manual com microfone físico é
necessário para validar a transcrição de ponta a ponta.
"""

import unittest
from unittest.mock import MagicMock, patch

from voice.voice_engine import VoiceEngine, WindowsSpeechUnavailable


class TestVoiceEngineFallback(unittest.TestCase):

    @patch("voice.voice_engine.WindowsSpeechRecognizer")
    def test_usa_windows_speech_quando_disponivel_e_com_resultado(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.listen.return_value = "mova o mouse para a direita"
        mock_cls.return_value = mock_instance

        engine = VoiceEngine(usar_windows_speech=True)
        texto, motor = engine.listen()

        self.assertEqual(texto, "mova o mouse para a direita")
        self.assertEqual(motor, "windows_speech")

    @patch("voice.voice_engine.WindowsSpeechRecognizer", side_effect=WindowsSpeechUnavailable("sem sapi"))
    def test_cai_para_whisper_quando_windows_speech_indisponivel(self, mock_cls):
        engine = VoiceEngine(usar_windows_speech=True)
        self.assertEqual(engine.motor_ativo, "whisper")

        engine._whisper = MagicMock()
        engine._whisper.listen.return_value = "abra a calculadora"

        texto, motor = engine.listen()

        self.assertEqual(texto, "abra a calculadora")
        self.assertEqual(motor, "whisper")

    @patch("voice.voice_engine.WindowsSpeechRecognizer")
    def test_cai_para_whisper_quando_windows_speech_nao_retorna_texto(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.listen.return_value = ""
        mock_cls.return_value = mock_instance

        engine = VoiceEngine(usar_windows_speech=True)
        engine._whisper = MagicMock()
        engine._whisper.listen.return_value = "clique"

        texto, motor = engine.listen()

        self.assertEqual(texto, "clique")
        self.assertEqual(motor, "whisper")

    @patch("voice.voice_engine.WindowsSpeechRecognizer")
    def test_erro_durante_escuta_do_windows_speech_cai_para_whisper(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.listen.side_effect = RuntimeError("erro de audio")
        mock_cls.return_value = mock_instance

        engine = VoiceEngine(usar_windows_speech=True)
        engine._whisper = MagicMock()
        engine._whisper.listen.return_value = "selecione tudo"

        texto, motor = engine.listen()

        self.assertEqual(texto, "selecione tudo")
        self.assertEqual(motor, "whisper")

    def test_erro_no_whisper_nao_propaga_excecao(self):
        engine = VoiceEngine(usar_windows_speech=False)
        engine._whisper = MagicMock()
        engine._whisper.listen.side_effect = RuntimeError("sem microfone")

        texto, motor = engine.listen()

        self.assertEqual(texto, "")
        self.assertEqual(motor, "erro")


if __name__ == "__main__":
    unittest.main()
