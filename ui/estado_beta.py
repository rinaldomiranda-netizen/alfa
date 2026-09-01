"""
Estado central da BETA para fins de interface visual (ui/status_widget.py).

Um "barramento" simples e thread-safe: o núcleo (core/alfa_core.py) e o
motor de voz (voice/voice_engine.py) publicam aqui o estado REAL da
assistente; a janela de status (rodando em outra thread) só lê. Nunca
mostra "ouvindo" nem nível de microfone fabricados — quem publica um
estado é sempre o código que já sabe a verdade (ex.: core/alfa_core.py
só publica LISTENING no exato momento em que chama
voice_engine.listen(), e o nível de microfone só é atualizado de
dentro da captura de áudio real em voice_engine.py).
"""

import enum
import threading
import time


class EstadoBeta(enum.Enum):
    IDLE = "idle"
    # Vigiando só a palavra de ativação ("Beta") — ver
    # core/alfa_core.py -> _ciclo_wake_word. Distinto de LISTENING:
    # este é o estado de repouso normal, não deve pulsar como se
    # estivesse captando um comando de verdade.
    STANDBY = "standby"
    # Palavra de ativação (ou presença, no modo atendimento) acabou de
    # ser confirmada — flash breve antes de começar a ouvir o comando.
    ATIVANDO = "ativando"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    WORKING = "working"
    ERROR = "error"
    # Agente de computador (ver agente/orquestrador.py): planejando um
    # pedido composto, e executando uma etapa específica dele.
    PLANNING = "planning"
    EXECUTING = "executing"


class EstadoBetaBus:
    """Estado atual da BETA, compartilhado entre a thread de voz e a UI."""

    def __init__(self):
        self._lock = threading.Lock()
        self._estado = EstadoBeta.IDLE
        self._nivel_mic = 0.0
        # Texto curto opcional (ex.: "etapa 2/3") — só usado por
        # PLANNING/EXECUTING (ver agente/orquestrador.py). Aditivo: um
        # `obter()` com 3 valores continuaria funcionando em qualquer
        # chamador antigo que ainda não soubesse do 4º campo, mas para
        # simplicidade só existe uma assinatura agora (ver
        # ui/status_widget.py, já atualizado junto).
        self._detalhe = ""
        self._atualizado_em = time.monotonic()

    def definir_estado(self, estado, nivel_mic=None, detalhe=None):
        with self._lock:
            self._estado = estado
            if nivel_mic is not None:
                self._nivel_mic = max(0.0, min(1.0, nivel_mic))
            elif estado != EstadoBeta.LISTENING:
                # Fora do estado de escuta, nível de microfone não tem
                # sentido — zera para nunca mostrar atividade de áudio
                # "fantasma" enquanto o mic não está de fato ativo.
                self._nivel_mic = 0.0

            if detalhe is not None:
                self._detalhe = detalhe
            elif estado not in (EstadoBeta.PLANNING, EstadoBeta.EXECUTING):
                self._detalhe = ""

            self._atualizado_em = time.monotonic()

    def definir_nivel_mic(self, nivel_mic):
        with self._lock:
            self._nivel_mic = max(0.0, min(1.0, nivel_mic))
            self._atualizado_em = time.monotonic()

    def obter(self):
        with self._lock:
            return self._estado, self._nivel_mic, self._detalhe, self._atualizado_em


# Instância única compartilhada por todo o processo do ALFA.
estado_beta = EstadoBetaBus()
