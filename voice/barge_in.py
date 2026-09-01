"""
Barge-in: permite interromper a fala da BETA com a voz.

    BETA fala -> usuário começa a falar -> evidência sustentada de
    fala detectada -> TTS é interrompido -> a fala captada a partir
    da interrupção é devolvida para ser processada como o próximo
    comando (ver core/alfa_core.py -> _falar).

Só dispara com evidência SUSTENTADA de voz (RMS acima do limiar de
ruído por vários blocos seguidos — a mesma ideia de detecção de fala
já usada em voice/voice_engine.py) — nunca por um clique, uma batida
ou um ruído curto (item 3 do pedido). Sem essa evidência, a Beta
termina a fala normalmente.

Roda em uma thread própria, só enquanto a Beta está falando; nunca
fica rodando fora disso (ver parar()). Reaproveita o MESMO
reconhecedor Whisper já carregado (nunca abre um segundo modelo — item
16, baixo consumo) E o MESMO stream de microfone contínuo (ver
voice/continuous_mic.py) usado pela detecção de palavra de ativação —
nunca abre um segundo stream concorrente (item 10/12 do pedido de
escuta contínua).

Limitação conhecida (sem cancelamento de eco): em computadores sem
fone de ouvido, a própria voz da Beta saindo pelo alto-falante pode
ser captada pelo microfone. O limiar de detecção aqui é
deliberadamente mais alto que o do reconhecimento normal de comando
para reduzir esse risco, mas sem um fone ou cancelamento de eco de
verdade, uma interrupção falsa ocasional em volume alto é possível —
ver limitação registrada no relatório desta tarefa.
"""

import threading
import time

import numpy as np


class BargeInListener:
    def __init__(
        self, voice_engine, voice_output, sample_rate=16000,
        blocos_sustentados=8, silencio_final_segundos=0.6,
    ):
        """
        `voice_output` é avisado (voice_output.parar()) DIRETO da
        thread de monitoramento assim que a interrupção é detectada —
        precisa ser assíncrono porque a thread principal está travada
        dentro de voice_output.falar() enquanto a Beta fala (ver
        core/alfa_core.py -> _falar).

        `blocos_sustentados`: blocos SEGUIDOS de RMS acima do limiar
        exigidos antes de considerar "evidência razoável de fala"
        (cada bloco tem ~20ms) — 8 blocos são ~160ms de voz sustentada,
        o bastante para distinguir de um clique/batida sem exigir uma
        frase inteira. Mais alto que o limiar usado no reconhecimento
        normal de comando, de propósito: aqui o alto-falante está
        ativo, então a barra para "é voz de verdade" é mais exigente.
        """
        self.voice_engine = voice_engine
        self.voice_output = voice_output
        self.sample_rate = sample_rate
        self.blocos_sustentados = blocos_sustentados
        self.silencio_final_segundos = silencio_final_segundos

        self._interromper = threading.Event()
        self._parar_monitor = threading.Event()
        self._thread = None
        self._frames_capturados = []
        self._audio_resultado = None

    def iniciar(self):
        """Começa a monitorar o microfone em paralelo — chamar só
        enquanto a Beta estiver falando (ver core/alfa_core.py)."""
        self._interromper.clear()
        self._parar_monitor.clear()
        self._frames_capturados = []
        self._audio_resultado = None
        self._thread = threading.Thread(target=self._monitorar, daemon=True)
        self._thread.start()

    def parar(self):
        """
        Encerra o monitoramento (a Beta terminou de falar, com ou sem
        interrupção) — nunca deixa a thread rodando depois disso (ver
        item 20, sem thread órfã).
        """
        self._parar_monitor.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
        self._thread = None

    def foi_interrompida(self):
        return self._interromper.is_set()

    def texto_da_interrupcao(self):
        """
        Transcreve (via o MESMO Whisper já carregado) o áudio captado
        a partir do instante da interrupção — inclui a fala que
        causou a interrupção, para não perder a primeira palavra (ver
        item 4). Retorna "" se nada foi capturado ou a transcrição
        ficou vazia.
        """
        if self._audio_resultado is None or self._audio_resultado.size == 0:
            return ""
        return self.voice_engine.transcrever_audio_capturado(self._audio_resultado, self.sample_rate)

    def _monitorar(self):
        mic = self.voice_engine.mic_continuo
        if not mic.ativo() and not mic.iniciar():
            print("[BARGE-IN] Microfone indisponível para monitorar interrupção.")
            return

        try:
            consecutivos = 0
            calibracao = []
            blocos_calibracao = 15
            silencio_pos_deteccao = 0.0
            bloco_tamanho = mic.bloco_tamanho_real
            taxa = mic.taxa_real

            while not self._parar_monitor.is_set():
                bloco = mic.ler_bloco(timeout=0.5)
                if bloco is None:
                    continue
                rms = float(np.sqrt(np.mean(np.square(bloco)))) if bloco.size else 0.0

                if len(calibracao) < blocos_calibracao:
                    calibracao.append(rms)
                    continue

                # Limiar mais alto que o do reconhecimento normal de
                # propósito (ver docstring do módulo): reduz o risco de
                # a própria voz da Beta, vazando do alto-falante para o
                # microfone, disparar uma falsa interrupção.
                limite = max(0.012, float(np.median(calibracao)) * 5.0)

                if not self._interromper.is_set():
                    if rms > limite:
                        consecutivos += 1
                        self._frames_capturados.append(bloco)
                    else:
                        consecutivos = 0
                        self._frames_capturados = []

                    if consecutivos >= self.blocos_sustentados:
                        self._interromper.set()
                        # Avisa a Beta AGORA (thread separada) — a
                        # thread principal está travada dentro de
                        # voice_output.falar() até isso rodar.
                        try:
                            self.voice_output.parar()
                        except Exception:
                            pass
                    continue

                # Já interrompeu: continua capturando a fala real até
                # um silêncio curto confirmar o fim dela.
                self._frames_capturados.append(bloco)
                if rms <= limite:
                    silencio_pos_deteccao += bloco_tamanho / taxa
                    if silencio_pos_deteccao >= self.silencio_final_segundos:
                        break
                else:
                    silencio_pos_deteccao = 0.0

            if self._interromper.is_set() and self._frames_capturados:
                self._audio_resultado = np.concatenate(self._frames_capturados)
        except Exception as erro:
            print(f"[BARGE-IN] Monitoramento interrompido por erro: {erro}.")
        finally:
            # Nunca deixa a fila do stream compartilhado com áudio
            # desta janela acumulado para o próximo consumidor (item 3:
            # sem retenção; item 10: quem usa o stream depois — wake
            # word — começa limpo).
            mic.limpar_fila()
