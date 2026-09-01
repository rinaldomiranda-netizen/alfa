"""
VoiceOutput: fachada única de saída de voz do ALFA.

    PERSONALIDADE -> TEXTO + ESTILO -> [VoiceOutput] -> ÁUDIO

Isola o resto do sistema de qual motor de TTS está em uso.
core/alfa_core.py e core/personality.py só conhecem
`VoiceOutput.falar(texto, estilo)` — nunca importam Azure, ElevenLabs
ou pyttsx3 diretamente. Trocar de voz/motor é uma mudança em
config/alfa.json (`voz_saida.motor`), nunca no código do assistente.

Resiliência: se o motor principal falhar (sem internet, chave
inválida/ausente, cota excedida), o VoiceOutput cai automaticamente
para o motor de fallback (offline, pyttsx3) sem derrubar o ALFA.
"""

import importlib

from voice.tts.pyttsx3_tts import Pyttsx3TTSEngine

MOTORES = {
    "edge_tts": "voice.tts.edge_tts_engine.EdgeTTSEngine",
    "azure": "voice.tts.azure_tts.AzureTTSEngine",
    "elevenlabs": "voice.tts.elevenlabs_tts.ElevenLabsTTSEngine",
    "pyttsx3": "voice.tts.pyttsx3_tts.Pyttsx3TTSEngine",
}


def _carregar_classe(caminho_pontilhado):
    modulo_nome, classe_nome = caminho_pontilhado.rsplit(".", 1)
    modulo = importlib.import_module(modulo_nome)
    return getattr(modulo, classe_nome)


class VoiceOutput:
    def __init__(self, motor="azure", motor_fallback="pyttsx3", opcoes_motor=None):
        self.opcoes_motor = opcoes_motor or {}
        self._motor_fallback_nome = motor_fallback
        self._fallback = None

        self.motor_ativo = motor
        self.engine = self._instanciar(motor)

        if self.engine is None:
            print(f"[ALFA VOZ] Motor '{motor}' indisponível. Usando fallback offline por enquanto.")
            self.engine = self._garantir_fallback()
            self.motor_ativo = self._fallback_nome_efetivo

    def _instanciar(self, nome_motor):
        caminho = MOTORES.get(nome_motor)
        if not caminho:
            print(f"[ALFA VOZ] Motor de voz desconhecido: {nome_motor!r}")
            return None

        try:
            classe = _carregar_classe(caminho)
            return classe(**self.opcoes_motor.get(nome_motor, {}))
        except Exception as erro:
            print(f"[ALFA VOZ] Falha ao iniciar motor '{nome_motor}': {erro}")
            return None

    def _garantir_fallback(self):
        if self._fallback is None:
            self._fallback_nome_efetivo = self._motor_fallback_nome
            self._fallback = self._instanciar(self._motor_fallback_nome)
            if self._fallback is None:
                # Último recurso absoluto: pyttsx3 com parâmetros padrão.
                self._fallback_nome_efetivo = "pyttsx3"
                self._fallback = Pyttsx3TTSEngine()
        return self._fallback

    def parar(self):
        """Interrompe a fala em andamento (ver voice/barge_in.py) —
        repassa ao motor ativo; motores sem suporte real deixam o
        padrão (no-op, ver voice/tts/base.py). Nunca levanta exceção."""
        try:
            self.engine.parar()
        except Exception:
            pass

    def falar(self, texto, estilo=None):
        if not texto:
            return

        print(f"BETA [{self.motor_ativo}/{estilo or 'neutro'}]: {texto}")

        try:
            self.engine.falar(texto, estilo)
            return
        except Exception as erro:
            print(f"[ALFA VOZ] Motor '{self.motor_ativo}' falhou ({erro}). Caindo para fallback offline.")

        try:
            self._garantir_fallback().falar(texto, estilo)
        except Exception as erro:
            print(f"[ALFA VOZ] Fallback também falhou ({erro}). Resposta ficou só no texto acima.")
