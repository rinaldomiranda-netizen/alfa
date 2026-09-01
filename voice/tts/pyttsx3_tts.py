"""
Motor de voz OFFLINE (SAPI5 via pyttsx3) — fallback de segurança.

Usado apenas quando os motores neurais em nuvem (Azure/ElevenLabs)
não estão configurados (sem chave de API) ou falham (sem internet,
cota excedida, serviço fora do ar). É o único motor sem naturalidade
neural — existe para o ALFA nunca ficar mudo, nunca para ser a voz
"definitiva" do assistente.
"""

import pyttsx3

from voice.tts.base import TTSEngine


class Pyttsx3TTSEngine(TTSEngine):
    nome = "pyttsx3"

    def __init__(self, taxa_fala=190, volume=1.0):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", taxa_fala)
        self.engine.setProperty("volume", volume)
        self._selecionar_voz_feminina_pt()

    def _selecionar_voz_feminina_pt(self):
        try:
            vozes = self.engine.getProperty("voices")
        except Exception:
            return

        for voz in vozes or []:
            nome = (voz.name or "").lower()
            idiomas = " ".join(str(l) for l in (voz.languages or [])).lower()
            if "pt" in idiomas or "brazil" in nome or "brasil" in nome or "maria" in nome:
                self.engine.setProperty("voice", voz.id)
                break

    def falar(self, texto, estilo=None):
        # pyttsx3/SAPI5 não tem controle de estilo/emoção; `estilo` é
        # aceito só para respeitar a interface comum.
        self.engine.say(texto)
        self.engine.runAndWait()
