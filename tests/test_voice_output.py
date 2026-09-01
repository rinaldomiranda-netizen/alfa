"""
Testes da fachada VoiceOutput (voice/voice_output.py).

Usam motores falsos injetados via mock — nunca chamam Azure,
ElevenLabs ou até pyttsx3 de verdade nestes testes (exceto quando
propositalmente deixamos o pyttsx3 real ser instanciado como último
recurso, o que só cria o objeto, sem nunca chamar `.falar()`).
"""

import unittest
from unittest.mock import MagicMock, patch

from voice.voice_output import VoiceOutput


class FakeEngine:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chamadas = []

    def falar(self, texto, estilo=None):
        self.chamadas.append((texto, estilo))


class FakeEngineFalhaNaConstrucao:
    def __init__(self, **kwargs):
        raise RuntimeError("sem credenciais configuradas")


class FakeEngineFalhaAoFalar:
    def __init__(self, **kwargs):
        self.chamadas = []

    def falar(self, texto, estilo=None):
        raise RuntimeError("serviço de voz fora do ar")


class TestVoiceOutput(unittest.TestCase):

    @patch("voice.voice_output._carregar_classe", return_value=FakeEngine)
    def test_usa_motor_principal_quando_disponivel(self, mock_carregar):
        vo = VoiceOutput(motor="azure", motor_fallback="pyttsx3")
        vo.falar("Olá", "saudacao")

        self.assertEqual(vo.motor_ativo, "azure")
        self.assertEqual(vo.engine.chamadas, [("Olá", "saudacao")])

    @patch("voice.voice_output._carregar_classe")
    def test_cai_para_fallback_quando_motor_principal_nao_inicializa(self, mock_carregar):
        def escolher(caminho):
            return FakeEngineFalhaNaConstrucao if "azure" in caminho else FakeEngine

        mock_carregar.side_effect = escolher

        vo = VoiceOutput(motor="azure", motor_fallback="pyttsx3")

        self.assertEqual(vo.motor_ativo, "pyttsx3")
        vo.falar("Oi", "confirmacao")
        self.assertEqual(vo.engine.chamadas, [("Oi", "confirmacao")])

    @patch("voice.voice_output._carregar_classe")
    def test_cai_para_fallback_quando_motor_principal_falha_ao_falar(self, mock_carregar):
        def escolher(caminho):
            return FakeEngineFalhaAoFalar if "azure" in caminho else FakeEngine

        mock_carregar.side_effect = escolher

        vo = VoiceOutput(motor="azure", motor_fallback="pyttsx3")
        self.assertEqual(vo.motor_ativo, "azure")

        # Não deve levantar exceção para quem chamou.
        vo.falar("Teste", "neutra")

        fallback_usado = vo._garantir_fallback()
        self.assertEqual(fallback_usado.chamadas, [("Teste", "neutra")])

    @patch("voice.voice_output._carregar_classe")
    def test_quando_fallback_tambem_falha_na_construcao_usa_pyttsx3_direto(self, mock_carregar):
        def escolher(caminho):
            if "azure" in caminho:
                return FakeEngineFalhaNaConstrucao
            if "elevenlabs" in caminho:
                return FakeEngineFalhaNaConstrucao
            return FakeEngine  # pyttsx3

        mock_carregar.side_effect = escolher

        vo = VoiceOutput(motor="azure", motor_fallback="elevenlabs")
        # Motor principal falhou -> __init__ cai para o fallback
        # configurado (elevenlabs), que também falha -> último
        # recurso absoluto: Pyttsx3TTSEngine real (só a instanciação,
        # nenhuma fala é emitida neste teste).
        self.assertEqual(vo.motor_ativo, "pyttsx3")

    def test_motor_desconhecido_cai_para_fallback_pyttsx3_real(self):
        vo = VoiceOutput(motor="motor-que-nao-existe", motor_fallback="pyttsx3")
        self.assertEqual(vo.motor_ativo, "pyttsx3")

    def test_falar_com_texto_vazio_nao_chama_nenhum_motor(self):
        vo = VoiceOutput(motor="motor-que-nao-existe", motor_fallback="pyttsx3")
        vo.engine = MagicMock()
        vo.falar("")
        vo.falar(None)
        vo.engine.falar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
