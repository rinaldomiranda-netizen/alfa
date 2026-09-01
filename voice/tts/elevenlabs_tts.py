"""
Motor de voz ElevenLabs — alternativa de naturalidade e expressividade
emocional ainda maiores que a Azure (MOS de naturalidade mais alto e
controle fino de emoção em benchmarks de 2026), ao custo de uma API
mais cara (~US$100/milhão de caracteres) e sem vozes nativas
rotuladas como "pt-BR" (usa o modelo multilíngue).

Mantida atrás da mesma interface (voice/tts/base.py) que o motor
Azure para que trocar de voz seja só uma mudança de config, nunca de
código: veja config/alfa.json -> voz_saida.motor = "elevenlabs".

Implementado via REST direto (usando `requests`, já uma dependência
do projeto) em vez do SDK oficial `elevenlabs`, para não adicionar
mais uma dependência pesada só para isso.

Requer variáveis de ambiente ELEVENLABS_API_KEY e ELEVENLABS_VOICE_ID
(o voice_id de uma voz em português da sua conta ElevenLabs).
"""

import os

import numpy as np
import requests
import sounddevice as sd

from voice.tts.base import TTSEngine

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
SAMPLE_RATE = 24000

# A ElevenLabs não tem "estilos" nomeados como a Azure: a
# expressividade é controlada por voice_settings numéricos. Quanto
# menor a estabilidade e maior o "style", mais emocional/variável a
# entonação; mais estabilidade = fala mais uniforme e comedida.
MAPA_ESTILO = {
    "saudacao": {"stability": 0.55, "style": 0.45, "similarity_boost": 0.8},
    "confirmacao": {"stability": 0.55, "style": 0.40, "similarity_boost": 0.8},
    "descontraida": {"stability": 0.35, "style": 0.75, "similarity_boost": 0.8},
    "engracada": {"stability": 0.30, "style": 0.85, "similarity_boost": 0.8},
    "seria": {"stability": 0.75, "style": 0.15, "similarity_boost": 0.8},
    "empatica": {"stability": 0.60, "style": 0.35, "similarity_boost": 0.8},
    "neutra": {"stability": 0.60, "style": 0.30, "similarity_boost": 0.8},
}


class ElevenLabsTTSEngine(TTSEngine):
    nome = "elevenlabs"

    def __init__(
        self,
        chave_env="ELEVENLABS_API_KEY",
        voice_id_env="ELEVENLABS_VOICE_ID",
        modelo="eleven_flash_v2_5",
    ):
        self.chave = os.environ.get(chave_env)
        self.voice_id = os.environ.get(voice_id_env)
        self.modelo = modelo

        if not self.chave or not self.voice_id:
            raise RuntimeError(
                f"Configure as variáveis de ambiente {chave_env} e {voice_id_env} "
                "com sua chave de API e o voice_id (em português) da ElevenLabs "
                "(elevenlabs.io -> Voices)."
            )

    def falar(self, texto, estilo=None):
        voice_settings = MAPA_ESTILO.get(estilo, MAPA_ESTILO["neutra"])

        resposta = requests.post(
            API_URL.format(voice_id=self.voice_id),
            headers={"xi-api-key": self.chave, "Content-Type": "application/json"},
            params={"output_format": f"pcm_{SAMPLE_RATE}"},
            json={
                "text": texto,
                "model_id": self.modelo,
                "voice_settings": voice_settings,
            },
            timeout=20,
        )

        if resposta.status_code != 200:
            raise RuntimeError(
                f"Falha na síntese ElevenLabs ({resposta.status_code}): "
                f"{resposta.text[:200]}"
            )

        audio = np.frombuffer(resposta.content, dtype=np.int16)
        sd.play(audio, samplerate=SAMPLE_RATE)
        sd.wait()
