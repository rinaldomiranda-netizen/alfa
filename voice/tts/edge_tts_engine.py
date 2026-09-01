"""
Motor de voz neural via Microsoft Edge Read Aloud (edge-tts) — MOTOR
PRINCIPAL do ALFA.

edge-tts fala com o mesmo serviço neural que também está por trás da
Azure AI Speech, mas através do endpoint público e gratuito usado
pelo recurso de leitura em voz alta do navegador Edge — sem exigir
nenhuma chave de assinatura (nem AZURE_SPEECH_KEY, nem
ELEVENLABS_API_KEY). É por isso que virou o motor principal: voz
neural real em português do Brasil, funcionando "out of the box",
para qualquer pessoa que rodar o projeto.

Requer:
    pip install edge-tts pygame   (já instalados no venv)
    conexão com a internet (o serviço roda nos servidores da Microsoft).

Se a internet cair ou o serviço ficar indisponível, VoiceOutput cai
sozinho para o motor offline (pyttsx3) — ver voice/voice_output.py.
Os motores Azure/ElevenLabs continuam disponíveis e podem ser
escolhidos no lugar deste a qualquer momento via
config/alfa.json -> voz_saida.motor, caso o usuário prefira investir
em uma chave paga.
"""

import asyncio
import os
import re
import tempfile
import threading
import time

from voice.tts.base import TTSEngine

VOZ_PADRAO = "pt-BR-FranciscaNeural"
TIMEOUT_SINTESE_SEGUNDOS = 15

# edge-tts não tem "estilos" nomeados (isso é exclusivo da Azure
# Speech "de assinatura"): a expressividade aqui é obtida ajustando
# velocidade, volume e tom (pitch) da própria voz. Cada eixo é um
# deslocamento relativo ("+8%", "-20Hz") somado ao valor base
# configurado pelo usuário (voz_saida.opcoes_motor.edge_tts).
MAPA_ESTILO = {
    "saudacao":     {"rate": "+0%",  "volume": "+0%", "pitch": "+0Hz"},
    "confirmacao":  {"rate": "+0%",  "volume": "+0%", "pitch": "+0Hz"},
    "descontraida": {"rate": "+8%",  "volume": "+0%", "pitch": "+20Hz"},
    "engracada":    {"rate": "+10%", "volume": "+0%", "pitch": "+30Hz"},
    "seria":        {"rate": "-6%",  "volume": "+0%", "pitch": "-20Hz"},
    "empatica":     {"rate": "-4%",  "volume": "-5%", "pitch": "-10Hz"},
    "neutra":       {"rate": "+0%",  "volume": "+0%", "pitch": "+0Hz"},
}

_PADRAO_OFFSET = re.compile(r"^([+-])(\d+(?:\.\d+)?)(%|Hz)$")
_QUEBRA_SENTENCA = re.compile(r"(?<=[.!?])\s+")


def _dividir_em_frases(texto):
    """
    Quebra o texto em frases/parágrafos para sintetizar e tocar um de
    cada vez, em vez de esperar o texto inteiro (respostas
    institucionais mais longas, ver
    core/personality.py -> identidade_historia, chegam a ter vários
    parágrafos) ser sintetizado de uma só vez antes do primeiro som
    sair — medido em ~40s de silêncio total antes da fala começar.
    Não muda o que é dito nem a voz, só QUANDO cada trecho é ouvido.
    Uma resposta curta (a maioria) sempre teve 1 frase só, então esta
    função devolve exatamente o texto original nesse caso — mesmo
    comportamento de antes.
    """
    partes = []
    for paragrafo in texto.split("\n"):
        paragrafo = paragrafo.strip()
        if not paragrafo:
            continue
        partes.extend(p.strip() for p in _QUEBRA_SENTENCA.split(paragrafo) if p.strip())
    return partes or [texto]


def _somar_offsets(base, ajuste):
    """Soma dois deslocamentos no formato do edge-tts (ex.: "+5%" + "+8%" = "+13%")."""

    m_base = _PADRAO_OFFSET.match(base.strip())
    m_ajuste = _PADRAO_OFFSET.match(ajuste.strip())

    if not m_base or not m_ajuste or m_base.group(3) != m_ajuste.group(3):
        # Formato inesperado: não arrisca combinar, usa só o ajuste do estilo.
        return ajuste

    unidade = m_base.group(3)
    valor_base = float(m_base.group(2)) * (1 if m_base.group(1) == "+" else -1)
    valor_ajuste = float(m_ajuste.group(2)) * (1 if m_ajuste.group(1) == "+" else -1)
    total = valor_base + valor_ajuste

    sinal = "+" if total >= 0 else "-"
    magnitude = abs(total)
    texto_magnitude = f"{magnitude:.0f}" if unidade == "Hz" else f"{magnitude:.0f}"
    return f"{sinal}{texto_magnitude}{unidade}"


class EdgeTTSEngine(TTSEngine):
    nome = "edge_tts"

    def __init__(self, voz=VOZ_PADRAO, taxa_base="+0%", volume_base="+0%"):
        try:
            import edge_tts
        except ImportError as erro:
            raise RuntimeError(
                "edge-tts não está instalado. Rode: pip install edge-tts"
            ) from erro

        try:
            import pygame
        except ImportError as erro:
            raise RuntimeError(
                "pygame não está instalado (necessário para tocar o áudio "
                "gerado pelo Edge TTS). Rode: pip install pygame"
            ) from erro

        self._edge_tts = edge_tts
        self._pygame = pygame
        self.voz = voz
        self.taxa_base = taxa_base
        self.volume_base = volume_base
        self._interromper = threading.Event()

        if not pygame.mixer.get_init():
            pygame.mixer.init()

    async def _sintetizar(self, texto, rate, volume, pitch, caminho_saida):
        communicate = self._edge_tts.Communicate(
            texto, voice=self.voz, rate=rate, volume=volume, pitch=pitch
        )
        await communicate.save(caminho_saida)

    def _sintetizar_com_timeout(self, *args):
        asyncio.run(asyncio.wait_for(self._sintetizar(*args), timeout=TIMEOUT_SINTESE_SEGUNDOS))

    def parar(self):
        """Interrompe a fala em andamento (ver voice/barge_in.py) —
        sinaliza para parar entre frases e corta a reprodução atual
        na hora, sem esperar a frase inteira terminar."""
        self._interromper.set()
        try:
            self._pygame.mixer.music.stop()
        except Exception:
            pass

    def falar(self, texto, estilo=None):
        self._interromper.clear()
        parametros = MAPA_ESTILO.get(estilo, MAPA_ESTILO["neutra"])
        rate = _somar_offsets(self.taxa_base, parametros["rate"])
        volume = _somar_offsets(self.volume_base, parametros["volume"])
        pitch = _somar_offsets("+0Hz", parametros["pitch"])

        t_inicio_falar = time.monotonic()
        for indice, frase in enumerate(_dividir_em_frases(texto)):
            if self._interromper.is_set():
                break

            arquivo_tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            caminho_tmp = arquivo_tmp.name
            arquivo_tmp.close()

            try:
                self._sintetizar_com_timeout(frase, rate, volume, pitch, caminho_tmp)
                if self._interromper.is_set():
                    break
                if indice == 0:
                    print(f"[LATÊNCIA] (tts) primeiro_som_em={time.monotonic() - t_inicio_falar:.2f}s")
                self._tocar(caminho_tmp)
            finally:
                try:
                    os.remove(caminho_tmp)
                except OSError:
                    pass

    def _tocar(self, caminho_mp3):
        pygame = self._pygame
        pygame.mixer.music.load(caminho_mp3)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if self._interromper.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)
        pygame.mixer.music.unload()
