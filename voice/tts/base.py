"""
Interface comum a todos os motores de TTS do ALFA.

Qualquer motor novo (Azure, ElevenLabs, Google, pyttsx3, ...) só
precisa implementar `falar(texto, estilo)`. O resto do ALFA nunca
importa um motor específico diretamente — sempre fala com
voice.voice_output.VoiceOutput, que decide qual motor usar. É essa
indireção que permite trocar de voz/motor no futuro sem tocar em
core/alfa_core.py, core/personality.py ou qualquer outro módulo.
"""

from abc import ABC, abstractmethod


class TTSEngine(ABC):
    nome = "desconhecido"

    @abstractmethod
    def falar(self, texto, estilo=None):
        """
        Sintetiza e reproduz `texto` em voz alta.

        `estilo` é uma das chaves de personalidade definidas em
        core/personality.py (ex.: "saudacao", "confirmacao",
        "descontraida", "engracada", "seria", "empatica", "neutra").
        Cada motor mapeia isso para o que tiver disponível (estilo
        SSML, voice_settings, ou simplesmente ignora, no caso de
        motores sem suporte a expressividade).

        Deve levantar exceção em caso de falha — quem decide cair
        para o motor de fallback é o VoiceOutput, não o motor em si.
        """
        raise NotImplementedError

    def parar(self):
        """
        Interrompe a fala em andamento (ver voice/barge_in.py) — motor
        sem suporte real a interrupção pode deixar o padrão (no-op): a
        Beta simplesmente termina de falar normalmente nesse caso,
        sem erro.
        """
        pass
