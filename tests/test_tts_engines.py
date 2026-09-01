"""
Testes dos motores de TTS neurais (Azure e ElevenLabs).

Nunca fazem uma chamada de rede de verdade: requests/SDK são sempre
mockados. Cobrem (1) falha clara quando faltam credenciais e (2) a
lógica própria de cada motor (montagem de SSML, mapeamento de estilo,
tratamento de erro da API) — não a qualidade do áudio em si, que só
pode ser avaliada ouvindo de verdade com uma chave real.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

TONS_DA_PERSONALIDADE = {
    "saudacao", "confirmacao", "descontraida",
    "engracada", "seria", "empatica", "neutra",
}


class TestAzureTTSEngineSemCredenciais(unittest.TestCase):

    @patch.dict(os.environ, {}, clear=False)
    def test_falha_com_mensagem_clara_sem_chave_ou_regiao(self):
        os.environ.pop("AZURE_SPEECH_KEY", None)
        os.environ.pop("AZURE_SPEECH_REGION", None)

        from voice.tts.azure_tts import AzureTTSEngine

        with self.assertRaises(RuntimeError) as ctx:
            AzureTTSEngine()

        self.assertIn("AZURE_SPEECH_KEY", str(ctx.exception))


class TestAzureTTSEngineSSML(unittest.TestCase):
    """Testa a lógica pura de montagem de SSML, sem precisar do SDK/credenciais."""

    def _engine_sem_init(self):
        from voice.tts.azure_tts import AzureTTSEngine

        engine = AzureTTSEngine.__new__(AzureTTSEngine)
        engine.voz = "pt-BR-ThalitaMultilingualNeural"
        return engine

    def test_montar_ssml_sem_estilo(self):
        engine = self._engine_sem_init()
        ssml = engine._montar_ssml("Olá, Rinaldo!", None)

        self.assertIn('<voice name="pt-BR-ThalitaMultilingualNeural">', ssml)
        self.assertIn("Olá, Rinaldo!", ssml)
        self.assertNotIn("express-as", ssml)

    def test_montar_ssml_com_estilo(self):
        engine = self._engine_sem_init()
        ssml = engine._montar_ssml("Que bom!", "cheerful")

        self.assertIn('style="cheerful"', ssml)
        self.assertIn("Que bom!", ssml)

    def test_escapar_ssml_caracteres_especiais(self):
        from voice.tts.azure_tts import _escapar_ssml

        self.assertEqual(
            _escapar_ssml("Tom & Jerry <riso>"),
            "Tom &amp; Jerry &lt;riso&gt;",
        )

    def test_mapa_estilo_cobre_todos_os_tons_da_personalidade(self):
        from voice.tts.azure_tts import MAPA_ESTILO

        self.assertEqual(set(MAPA_ESTILO.keys()), TONS_DA_PERSONALIDADE)

    @patch.dict(os.environ, {"AZURE_SPEECH_KEY": "chave-fake", "AZURE_SPEECH_REGION": "brazilsouth"})
    @patch("voice.tts.azure_tts.speechsdk")
    def test_falar_monta_ssml_e_chama_speak_ssml_async(self, speechsdk_mock):
        speechsdk_mock.ResultReason.SynthesizingAudioCompleted = "OK"

        resultado_sintese = MagicMock()
        resultado_sintese.reason = "OK"

        synthesizer_mock = MagicMock()
        synthesizer_mock.speak_ssml_async.return_value.get.return_value = resultado_sintese
        speechsdk_mock.SpeechSynthesizer.return_value = synthesizer_mock

        from voice.tts.azure_tts import AzureTTSEngine

        engine = AzureTTSEngine()
        engine.falar("Pode deixar comigo.", "descontraida")

        synthesizer_mock.speak_ssml_async.assert_called_once()
        ssml_enviado = synthesizer_mock.speak_ssml_async.call_args[0][0]
        self.assertIn("Pode deixar comigo.", ssml_enviado)
        self.assertIn('style="cheerful"', ssml_enviado)


class TestElevenLabsTTSEngineSemCredenciais(unittest.TestCase):

    @patch.dict(os.environ, {}, clear=False)
    def test_falha_com_mensagem_clara_sem_chave_ou_voice_id(self):
        os.environ.pop("ELEVENLABS_API_KEY", None)
        os.environ.pop("ELEVENLABS_VOICE_ID", None)

        from voice.tts.elevenlabs_tts import ElevenLabsTTSEngine

        with self.assertRaises(RuntimeError) as ctx:
            ElevenLabsTTSEngine()

        self.assertIn("ELEVENLABS_API_KEY", str(ctx.exception))


class TestElevenLabsTTSEngineComCredenciais(unittest.TestCase):

    def setUp(self):
        self._patcher_env = patch.dict(
            os.environ,
            {"ELEVENLABS_API_KEY": "chave-fake", "ELEVENLABS_VOICE_ID": "voz-fake"},
        )
        self._patcher_env.start()
        self.addCleanup(self._patcher_env.stop)

    def test_mapa_estilo_cobre_todos_os_tons_da_personalidade(self):
        from voice.tts.elevenlabs_tts import MAPA_ESTILO

        self.assertEqual(set(MAPA_ESTILO.keys()), TONS_DA_PERSONALIDADE)

    @patch("voice.tts.elevenlabs_tts.sd.wait")
    @patch("voice.tts.elevenlabs_tts.sd.play")
    @patch("voice.tts.elevenlabs_tts.requests.post")
    def test_falar_chama_api_e_reproduz_audio(self, mock_post, mock_play, mock_wait):
        mock_resposta = MagicMock()
        mock_resposta.status_code = 200
        mock_resposta.content = np.zeros(100, dtype=np.int16).tobytes()
        mock_post.return_value = mock_resposta

        from voice.tts.elevenlabs_tts import ElevenLabsTTSEngine

        engine = ElevenLabsTTSEngine()
        engine.falar("Oi, Rinaldo!", "descontraida")

        mock_post.assert_called_once()
        corpo_enviado = mock_post.call_args.kwargs["json"]
        self.assertEqual(corpo_enviado["text"], "Oi, Rinaldo!")
        self.assertAlmostEqual(corpo_enviado["voice_settings"]["style"], 0.75)

        mock_play.assert_called_once()
        mock_wait.assert_called_once()

    @patch("voice.tts.elevenlabs_tts.requests.post")
    def test_falar_levanta_erro_em_status_diferente_de_200(self, mock_post):
        mock_resposta = MagicMock()
        mock_resposta.status_code = 401
        mock_resposta.text = "unauthorized"
        mock_post.return_value = mock_resposta

        from voice.tts.elevenlabs_tts import ElevenLabsTTSEngine

        engine = ElevenLabsTTSEngine()
        with self.assertRaises(RuntimeError):
            engine.falar("teste")


if __name__ == "__main__":
    unittest.main()
