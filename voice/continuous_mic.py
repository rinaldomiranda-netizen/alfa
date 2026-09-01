"""
UM ÚNICO stream de microfone, aberto uma vez e mantido continuamente
— compartilhado pela detecção de palavra de ativação, pela escuta de
comando (modo ACTIVE) e pelo barge-in (ver voice/barge_in.py). Nunca
abre/fecha o dispositivo repetidamente e nunca deixa dois listeners
disputando o mesmo microfone ao mesmo tempo (itens 10 e 12 do pedido
de escuta contínua).

    sd.InputStream (aberto em iniciar(), fechado só em parar())
        -> callback de baixíssimo custo, só copia o bloco pra uma fila
        -> queue.Queue em memória (nunca em disco)

Privacidade (item 3): a fila guarda só os últimos blocos ainda não
consumidos — nenhum áudio é salvo em arquivo, e quem consome (ver
voice/voice_engine.py -> VoiceEngine.escutar_continuo) descarta o
que não vira comando reconhecido.
"""

import queue
import threading


class MicrofoneContinuo:
    """Stream de microfone persistente com uma fila de blocos brutos.

    `iniciar()` é seguro de chamar mais de uma vez (não faz nada se já
    estiver rodando) — evita criar um segundo stream por engano.
    """

    # ~200 blocos de 20ms ~= 4s de áudio — teto para o buffer nunca
    # crescer sem limite se ninguém consumir por um tempo (ex.:
    # durante um atendimento em andamento, que usa seu próprio
    # caminho de escuta, ver core/atendimento.py, e não lê deste
    # stream) — item 3 do pedido: só buffer temporário, nunca retenção
    # longa.
    TAMANHO_MAXIMO_FILA = 200

    def __init__(self, sample_rate=16000, bloco_tamanho=320):
        self.sample_rate = sample_rate
        self.bloco_tamanho_alvo = bloco_tamanho
        self.taxa_real = sample_rate
        self.bloco_tamanho_real = bloco_tamanho
        self.precisa_reamostrar = False

        self._stream = None
        self._fila = queue.Queue(maxsize=self.TAMANHO_MAXIMO_FILA)
        self._lock = threading.Lock()

    def ativo(self):
        return self._stream is not None

    def iniciar(self):
        with self._lock:
            if self._stream is not None:
                return True
            try:
                import sounddevice as sd
            except Exception as erro:
                print(f"[MIC] Não foi possível importar sounddevice: {erro}.")
                return False

            taxa = self.sample_rate
            precisa_reamostrar = False
            try:
                sd.check_input_settings(samplerate=taxa, channels=1, dtype="float32")
            except Exception:
                try:
                    info = sd.query_devices(kind="input")
                    taxa = int(info["default_samplerate"])
                    precisa_reamostrar = True
                except Exception as erro:
                    print(f"[MIC] Nenhum microfone disponível: {erro}.")
                    return False

            bloco = max(1, round(self.bloco_tamanho_alvo * taxa / self.sample_rate))
            self.taxa_real = taxa
            self.bloco_tamanho_real = bloco
            self.precisa_reamostrar = precisa_reamostrar

            def _callback(indata, frames, time_info, status):
                # Callback do PortAudio: tem que ser rápido e nunca
                # bloquear. Se a fila encher (ninguém consumindo há
                # segundos — ver TAMANHO_MAXIMO_FILA), descarta o bloco
                # mais ANTIGO em vez de travar ou crescer sem limite.
                try:
                    self._fila.put_nowait(indata[:, 0].copy())
                except queue.Full:
                    try:
                        self._fila.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._fila.put_nowait(indata[:, 0].copy())
                    except queue.Full:
                        pass

            try:
                self._stream = sd.InputStream(
                    samplerate=taxa, channels=1, dtype="float32",
                    blocksize=bloco, callback=_callback,
                )
                self._stream.start()
            except Exception as erro:
                print(f"[MIC] Falha ao abrir o microfone: {erro}.")
                self._stream = None
                return False

            print(f"[MIC] Stream contínuo iniciado (taxa={taxa}Hz, bloco={bloco} amostras).")
            return True

    def parar(self):
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self.limpar_fila()

    def ler_bloco(self, timeout=0.5):
        """Bloqueia até um novo bloco chegar (ou timeout). Retorna
        None se nada chegou a tempo — nunca levanta exceção."""
        try:
            return self._fila.get(timeout=timeout)
        except queue.Empty:
            return None

    def limpar_fila(self):
        """Descarta áudio já capturado e ainda não consumido — usado
        sempre que uma tentativa termina (com ou sem palavra de
        ativação), para nunca reter áudio antigo (item 3: privacidade
        — sem gravação contínua retida)."""
        with self._fila.mutex:
            self._fila.queue.clear()
