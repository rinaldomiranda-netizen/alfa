"""
Motor de voz (STT) do ALFA.

    microfone -> Windows Speech Recognition (SAPI) [principal]
              -> Whisper local (faster-whisper) [fallback]
              -> texto

O reconhecimento de voz nativo do Windows (SAPI - o mesmo motor usado
pelo "Reconhecimento de Voz do Windows"/Narrador) é tentado primeiro,
pois roda em tempo real, sem custo de carregar um modelo local. Se o
SAPI não estiver disponível, não retornar texto, ou falhar, o ALFA
cai automaticamente para o Whisper local (já usado no projeto), sem
encerrar o programa.
"""

import os
import re
import time

import numpy as np

try:
    import win32com.client
    import pythoncom
    _SAPI_IMPORT_OK = True
except Exception:
    _SAPI_IMPORT_OK = False


def _texto_parece_ruido(texto):
    """
    Detecta o padrão clássico de alucinação de transcrição em áudio
    ruim/silencioso: um mesmo trecho curto (1 a 3 palavras) repetido
    várias vezes seguidas (ex.: "e o que e o que e o que e o que").
    Uma frase real praticamente nunca repete a mesma sequência de
    palavras 4+ vezes seguidas — usado só para descartar a
    transcrição (ver VoiceEngine.listen), nunca para decidir se houve
    fala ou não.
    """
    palavras = texto.lower().split()
    total = len(palavras)
    if total < 6:
        return False

    for tamanho in (1, 2, 3):
        if total < tamanho * 4:
            continue
        for inicio in range(0, total - tamanho):
            trecho = palavras[inicio:inicio + tamanho]
            repeticoes = 1
            pos = inicio + tamanho
            while pos + tamanho <= total and palavras[pos:pos + tamanho] == trecho:
                repeticoes += 1
                pos += tamanho
            if repeticoes >= 4:
                return True
    return False


def _limpar_texto_transcrito(texto):
    """
    Limpeza leve do texto bruto que sai do Whisper/SAPI: só remove
    espaços duplicados e caracteres de controle/símbolos estranhos que
    a transcrição às vezes produz em trechos ruidosos. NÃO mexe em
    acentos nem em palavras — a normalização de domínio (remover
    acentos, pontuação etc. para casar com os padrões do
    IntentEngine) já existe em core/normalizer.py e continua sendo
    aplicada lá, sobre este texto já limpo.
    """
    if not texto:
        return ""
    texto = texto.strip()
    texto = re.sub(r"\s+", " ", texto)
    # Mantém letras (com acentos), números, espaço e pontuação básica
    # de fala; descarta o resto (lixo de encoding, símbolos soltos).
    texto = re.sub(r"[^\w À-ÿ.,!?'-]", "", texto, flags=re.UNICODE)
    return texto.strip()


def _transcricao_invalida(texto, duracao_audio_segundos):
    """
    Validação final antes de entregar o texto ao IntentEngine (ver
    core/alfa_core.py -> ciclo_unico). Rejeita:
      - texto vazio;
      - repetição anormal da mesma palavra/trecho (alucinação clássica
        de Whisper em silêncio/ruído, ver _texto_parece_ruido);
      - texto sem nenhuma letra (só sobrou pontuação/símbolo solto);
      - texto absurdamente longo para a duração de áudio capturada
        (fala normal em PT-BR fica em torno de 2-4 palavras/segundo;
        acima disso é sinal de alucinação, não de fala real).
    """
    if not texto:
        return True
    if _texto_parece_ruido(texto):
        return True
    if not any(c.isalpha() for c in texto):
        return True

    palavras = texto.split()
    if duracao_audio_segundos > 0.3:
        taxa = len(palavras) / duracao_audio_segundos
        if taxa > 6.0:
            return True

    return False


class WindowsSpeechUnavailable(Exception):
    """Erro sinalizando que o SAPI/Windows Speech não pode ser usado."""


class WindowsSpeechRecognizer:
    """
    Reconhecimento de voz usando o motor SAPI compartilhado do Windows
    (o mesmo mecanismo por trás do "Reconhecimento de Voz do Windows").

    Requer:
      - pywin32 instalado (já está no ambiente do projeto);
      - o serviço de reconhecimento de voz do Windows configurado/
        treinado pelo menos uma vez em Configurações > Acessibilidade
        > Reconhecimento de Voz, com o idioma português (Brasil)
        instalado, para transcrever corretamente.
    """

    class _EventSink:
        def __init__(self):
            self.text = None
            self.done = False

        def OnRecognition(self, StreamNumber, StreamPosition, RecognitionType, Result):
            try:
                resultado = win32com.client.Dispatch(Result)
                self.text = resultado.PhraseInfo.GetText()
            except Exception:
                self.text = None
            self.done = True

    def __init__(self, timeout_segundos=8):
        if not _SAPI_IMPORT_OK:
            raise WindowsSpeechUnavailable(
                "pywin32 (win32com/pythoncom) não está disponível."
            )
        self.timeout_segundos = timeout_segundos
        # Falha cedo se o SAPI não puder ser instanciado neste Windows.
        pythoncom.CoInitialize()
        try:
            win32com.client.Dispatch("SAPI.SpSharedRecoContext")
        except Exception as erro:
            raise WindowsSpeechUnavailable(
                f"Motor SAPI do Windows indisponível: {erro}"
            ) from erro
        finally:
            pythoncom.CoUninitialize()

    def listen(self):
        pythoncom.CoInitialize()
        try:
            contexto = win32com.client.Dispatch("SAPI.SpSharedRecoContext")
            gramatica = contexto.CreateGrammar()
            gramatica.DictationSetState(1)

            sink = win32com.client.WithEvents(contexto, WindowsSpeechRecognizer._EventSink)
            sink.done = False
            sink.text = None

            inicio = time.monotonic()
            while not sink.done and (time.monotonic() - inicio) < self.timeout_segundos:
                pythoncom.PumpWaitingMessages()
                time.sleep(0.05)

            try:
                gramatica.DictationSetState(0)
            except Exception:
                pass

            return (sink.text or "").strip()
        finally:
            pythoncom.CoUninitialize()


class WhisperFallbackRecognizer:
    """Reconhecimento local via faster-whisper, usado como fallback."""

    def __init__(self, model_size="base", sample_rate=16000, max_seconds=6, silence_seconds=0.5):
        self.model_size = model_size
        self.sample_rate = sample_rate
        self.max_seconds = max_seconds
        self.silence_seconds = silence_seconds
        self._model = None
        self._sd = None
        # Piso de ruído do modo contínuo (ver escutar_continuo) —
        # calibrado uma única vez e depois lentamente adaptado durante
        # trechos de silêncio, para não pagar ~0,6s de calibração a
        # cada tentativa (era o maior custo fixo do standby antigo).
        self._ruido_continuo = None

    def _detectar_device(self):
        """
        Detecta GPU NVIDIA compatível de verdade (via ctranslate2, o
        backend do faster-whisper) em vez de simplesmente assumir CPU
        ou GPU. Sem GPU utilizável, cai para CPU/int8 (mais leve,
        recomendado pelo próprio faster-whisper para CPU).
        """
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:
            pass
        return "cpu", "int8"

    def _garantir_modelo(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            import sounddevice as sd

            self._sd = sd
            device, compute_type = self._detectar_device()
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=max(2, (os.cpu_count() or 4) - 1),
            )
            print(
                f"[ALFA VOZ] Whisper carregado uma única vez: "
                f"modelo={self.model_size} device={device} compute_type={compute_type}"
            )

    def _rms(self, bloco):
        if bloco.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(bloco))))

    def listen(self, on_nivel=None, initial_prompt=None, max_seconds=None):
        """
        `on_nivel`, se fornecido, é chamado a cada bloco de áudio (já
        fora da janela de calibração) com o RMS bruto capturado —
        usado só para diagnóstico/indicador visual (ui/status_widget.py)
        mostrar o nível REAL de microfone; nunca influencia a decisão
        de "começou a falar" nem qualquer outra lógica de captura.

        `initial_prompt` é repassado ao Whisper (ver transcrever()) —
        usado pela detecção de palavra de ativação (ver
        core/alfa_core.py -> _ciclo_wake_word) para reduzir um erro de
        transcrição real e medido: "Beta" dita SOZINHA (sem mais
        nenhuma palavra na frase) costumava sair como "Bet." sem essa
        dica. Não é usado na escuta normal de comando (fica None).

        `max_seconds`, se fornecido, substitui self.max_seconds só
        nesta chamada — usado pelo standby (ver core/alfa_core.py) com
        uma janela mais curta, já que em SILÊNCIO TOTAL (ninguém fala)
        o laço abaixo sempre espera o teto inteiro antes de desistir
        (medido: ~6,1s por ciclo parado). Não muda a sensibilidade de
        detecção nem o corte por silêncio pós-fala (self.silence_seconds
        continua igual); só reduz quanto tempo se espera quando não há
        fala nenhuma.
        """
        self._garantir_modelo()
        sd = self._sd
        max_seconds_efetivo = self.max_seconds if max_seconds is None else max_seconds

        # Nem todo dispositivo/host de áudio aceita gravar direto em
        # 16000 Hz (o Whisper exige essa taxa). Confirma antes de
        # assumir — se não for possível, grava na taxa nativa do
        # dispositivo e reamostra para 16000 Hz depois (ver abaixo).
        taxa_gravacao = self.sample_rate
        precisa_reamostrar = False
        try:
            sd.check_input_settings(samplerate=self.sample_rate, channels=1, dtype="float32")
        except Exception:
            info_dispositivo = sd.query_devices(kind="input")
            taxa_gravacao = int(info_dispositivo["default_samplerate"])
            precisa_reamostrar = True
            print(
                f"[ALFA VOZ] Microfone não aceita {self.sample_rate} Hz direto; "
                f"gravando a {taxa_gravacao} Hz e reamostrando para {self.sample_rate} Hz."
            )

        bloco_tamanho = max(1, round(320 * taxa_gravacao / self.sample_rate))
        frames = []
        falando = False
        silencio = 0.0
        inicio = time.monotonic()
        calibracao = []
        # Calibração mais longa (~0,6s em vez de ~0,24s) para um piso
        # de ruído mais estável antes de fixar o limiar de fala.
        blocos_calibracao = 30

        with sd.InputStream(
            samplerate=taxa_gravacao,
            channels=1,
            dtype="float32",
            blocksize=bloco_tamanho,
        ) as stream:

            while time.monotonic() - inicio < max_seconds_efetivo:
                data, _ = stream.read(bloco_tamanho)
                bloco = data[:, 0].copy()
                rms = self._rms(bloco)

                if len(calibracao) < blocos_calibracao:
                    calibracao.append(rms)
                    continue

                # Pisos bem mais baixos que os originais (0.004/0.015):
                # medição real mostrou microfones com ganho baixo cujo
                # pico de fala normal fica por volta de 0.004-0.008 de
                # RMS — o limiar antigo de 0.015 nunca era ultrapassado,
                # então o ALFA nunca detectava "começou a falar" e
                # descartava a gravação (retornava "" sempre).
                ruido = max(0.0008, float(np.median(calibracao)))
                limite = max(0.0035, ruido * 3.0)

                if on_nivel is not None:
                    try:
                        on_nivel(rms)
                    except Exception:
                        pass

                if not falando:
                    if rms > limite:
                        falando = True
                        frames.append(bloco)
                else:
                    frames.append(bloco)
                    if rms < limite:
                        silencio += bloco_tamanho / taxa_gravacao
                    else:
                        silencio = 0.0
                    if silencio >= self.silence_seconds:
                        break

        t_fim_gravacao = time.monotonic()

        if not frames:
            return ""

        audio = np.concatenate(frames)
        texto = self.transcrever(audio, taxa_gravacao, initial_prompt=initial_prompt)
        print(f"[LATÊNCIA] (whisper) gravacao={t_fim_gravacao - inicio:.2f}s")
        return texto

    def transcrever(self, audio, taxa_amostragem, initial_prompt=None):
        """
        Reamostra (se necessário) e transcreve um áudio JÁ CAPTURADO —
        extraído de listen() para ser reaproveitado também pelo
        barge-in (ver voice/barge_in.py), que captura a fala que
        interrompeu a Beta e precisa transcrevê-la sem abrir um
        segundo modelo Whisper (ver item 16, baixo consumo:
        _garantir_modelo() só carrega o modelo uma vez).
        """
        self._garantir_modelo()

        if taxa_amostragem != self.sample_rate:
            duracao = audio.size / taxa_amostragem
            n_amostras_alvo = max(1, int(round(duracao * self.sample_rate)))
            eixo_original = np.linspace(0.0, duracao, num=audio.size, endpoint=False)
            eixo_alvo = np.linspace(0.0, duracao, num=n_amostras_alvo, endpoint=False)
            audio = np.interp(eixo_alvo, eixo_original, audio).astype(np.float32)

        duracao_audio_segundos = audio.size / self.sample_rate
        if duracao_audio_segundos <= 0:
            return ""

        # Este microfone (e provavelmente outros com ganho de captura
        # baixo) grava fala real com pico de amplitude bem abaixo do
        # que o Whisper espera (medido: ~0.004-0.008, ou seja, quase
        # -45 dB). Sem normalizar, o VAD interno do próprio Whisper
        # confunde a fala com silêncio e devolve transcrição vazia
        # mesmo quando a nossa detecção de fala (RMS acima) já
        # confirmou que havia voz. Amplifica para perto do full-scale
        # antes de transcrever — só ganho, não altera o conteúdo.
        pico = float(np.max(np.abs(audio))) if audio.size else 0.0
        if 0 < pico < 0.95:
            audio = np.clip(audio * (0.95 / pico), -1.0, 1.0).astype(np.float32)

        # beam_size=5 (revertido de 1): a medição anterior mostrou que
        # o TTS, não o Whisper, era o gargalo real de latência (ver
        # voice/tts/edge_tts_engine.py); reduzir o beam ganhava pouco
        # tempo e, no uso real, piorou a precisão do reconhecimento
        # (relato direto do usuário) — prioridade é entender
        # corretamente o que foi dito.
        t_inicio_transcricao = time.monotonic()
        segments, _ = self._model.transcribe(
            audio,
            language="pt",
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=initial_prompt,
        )

        texto_bruto = " ".join(
            seg.text.strip() for seg in segments if seg.text.strip()
        ).strip()
        print(f"[DEBUG] Texto transcrito: '{texto_bruto}'")
        print(f"[LATÊNCIA] (whisper) transcricao={time.monotonic() - t_inicio_transcricao:.2f}s")

        texto = _limpar_texto_transcrito(texto_bruto)

        if _transcricao_invalida(texto, duracao_audio_segundos):
            print("[WHISPER] Transcrição descartada: suspeita de ruído/repetição")
            return ""

        return texto

    def escutar_continuo(self, mic, initial_prompt=None, max_duracao_segmento=8.0, on_nivel=None):
        """
        Consome blocos de um MicrofoneContinuo (ver voice/continuous_mic.py)
        JÁ ABERTO — nunca abre/fecha o dispositivo aqui (item 10 do
        pedido de escuta contínua). Bloqueia até um trecho de fala
        COMPLETO (começo detectado por RMS -> fim por silêncio) estar
        pronto, e então transcreve com o MESMO Whisper já carregado.

        Retorna (texto, t_inicio_fala, t_fim_fala):
          - texto: "" se o trecho não rendeu transcrição válida;
          - t_inicio_fala: instante (time.monotonic()) em que a
            evidência de fala cruzou o limiar — usado para medir
            "tempo desde o início da fala até detectar a palavra"
            (ver core/alfa_core.py). None se o microfone não estava
            disponível.
          - t_fim_fala: instante em que o silêncio confirmou o fim do
            trecho (começo da transcrição).

        Nunca acumula ruído indefinidamente: se ninguém falar por
        `max_duracao_segmento` (contado só quando HÁ evidência de som,
        mesmo que abaixo do limiar de fala — nunca em silêncio real,
        que não gera bloco nenhum além dos já vazios), a função
        continua monitorando sem nunca "travar" — cada bloco lido é
        descartado assim que processado (privacidade, item 3).
        """
        self._garantir_modelo()

        bloco_tamanho = mic.bloco_tamanho_real
        taxa_gravacao = mic.taxa_real

        if self._ruido_continuo is None:
            calibracao = []
            blocos_calibracao = 30
            while len(calibracao) < blocos_calibracao:
                bloco = mic.ler_bloco(timeout=1.0)
                if bloco is None:
                    continue
                calibracao.append(self._rms(bloco))
            self._ruido_continuo = float(np.median(calibracao)) if calibracao else 0.0008

        frames = []
        falando = False
        silencio = 0.0
        t_inicio_fala = None
        duracao_com_som = 0.0

        while True:
            bloco = mic.ler_bloco(timeout=1.0)
            if bloco is None:
                continue

            rms = self._rms(bloco)
            limite = max(0.0035, self._ruido_continuo * 3.0)

            if on_nivel is not None:
                try:
                    on_nivel(rms)
                except Exception:
                    pass

            if not falando:
                # Adapta lentamente o piso de ruído em silêncio — evita
                # recalibrar do zero a cada trecho (ver __init__) e
                # acompanha mudanças reais de ambiente ao longo de uma
                # sessão longa (item 18: standby de ~1 minuto).
                self._ruido_continuo = 0.98 * self._ruido_continuo + 0.02 * rms
                if rms > limite:
                    falando = True
                    t_inicio_fala = time.monotonic()
                    frames.append(bloco)
                continue

            frames.append(bloco)
            duracao_com_som = time.monotonic() - t_inicio_fala
            if rms < limite:
                silencio += bloco_tamanho / taxa_gravacao
            else:
                silencio = 0.0

            if silencio >= self.silence_seconds or duracao_com_som >= max_duracao_segmento:
                break

        t_fim_fala = time.monotonic()
        audio = np.concatenate(frames)
        texto = self.transcrever(audio, taxa_gravacao, initial_prompt=initial_prompt)
        return texto, t_inicio_fala, t_fim_fala


class VoiceEngine:
    """
    Fachada única de reconhecimento de voz do ALFA.

    Tenta o reconhecimento de voz do Windows primeiro; se indisponível
    ou sem resultado, usa o Whisper local automaticamente.
    """

    def __init__(self, usar_windows_speech=True, modelo_whisper="base", timeout_segundos=8):
        self.timeout_segundos = timeout_segundos
        self._whisper = WhisperFallbackRecognizer(model_size=modelo_whisper)
        self._windows = None
        self.motor_ativo = "whisper"

        # UM único stream de microfone contínuo (ver
        # voice/continuous_mic.py), compartilhado pela detecção de
        # palavra de ativação, pela escuta de comando e pelo barge-in
        # — nunca abre/fecha o dispositivo repetidamente nem cria
        # streams concorrentes (itens 10/12 do pedido de escuta
        # contínua). Só é aberto de verdade quando algo chama
        # iniciar_escuta_continua() (ver core/alfa_core.py); enquanto
        # isso, não existe custo nenhum.
        from voice.continuous_mic import MicrofoneContinuo
        self.mic_continuo = MicrofoneContinuo(sample_rate=self._whisper.sample_rate)

        if usar_windows_speech:
            try:
                self._windows = WindowsSpeechRecognizer(timeout_segundos=timeout_segundos)
                self.motor_ativo = "windows_speech"
            except WindowsSpeechUnavailable as erro:
                print(f"[ALFA VOZ] Windows Speech indisponível ({erro}). Usando Whisper.")
                self._windows = None

    def iniciar_escuta_continua(self):
        """Abre o stream de microfone contínuo (idempotente — seguro
        chamar de novo se já estiver aberto). Retorna True se o
        microfone ficou disponível."""
        return self.mic_continuo.iniciar()

    def parar_escuta_continua(self):
        """Fecha o stream contínuo — usado só quando outra parte do
        sistema precisa do microfone sozinha (ex.: modo atendimento,
        ver core/atendimento.py) para nunca haver dois streams
        disputando o dispositivo ao mesmo tempo (item 10)."""
        self.mic_continuo.parar()

    def escutar_continuo(self, initial_prompt=None, max_duracao_segmento=8.0, on_nivel=None):
        """
        Fachada para WhisperFallbackRecognizer.escutar_continuo — usa
        o stream já aberto por iniciar_escuta_continua(). Retorna
        (texto, motor, t_inicio_fala, t_fim_fala); motor é sempre
        "whisper" aqui (o SAPI não participa da escuta contínua, só do
        caminho antigo de listen()).
        """
        if not self.mic_continuo.ativo():
            self.mic_continuo.iniciar()
        try:
            texto, t_inicio_fala, t_fim_fala = self._whisper.escutar_continuo(
                self.mic_continuo, initial_prompt=initial_prompt,
                max_duracao_segmento=max_duracao_segmento, on_nivel=on_nivel,
            )
            return texto, "whisper", t_inicio_fala, t_fim_fala
        except Exception as erro:
            print(f"[ALFA VOZ] Falha na escuta contínua: {erro}.")
            return "", "erro", None, None

    def transcrever_audio_capturado(self, audio, taxa_amostragem):
        """
        Transcreve um áudio JÁ CAPTURADO por outra parte do sistema —
        usado pelo barge-in (ver voice/barge_in.py) para transcrever a
        fala que interrompeu a Beta, sem carregar um segundo modelo
        Whisper (reaproveita o mesmo WhisperFallbackRecognizer). Nunca
        levanta exceção: devolve "" se algo falhar.
        """
        try:
            return self._whisper.transcrever(audio, taxa_amostragem)
        except Exception as erro:
            print(f"[ALFA VOZ] Falha ao transcrever áudio do barge-in: {erro}.")
            return ""

    def listen(self, on_nivel=None, initial_prompt=None, max_seconds=None):
        """
        Retorna (texto, motor_usado). Nunca levanta exceção para o
        chamador. `on_nivel`, se fornecido, recebe o RMS ao vivo
        durante a captura pelo Whisper — usado pelo indicador visual
        (ui/status_widget.py) para mostrar o nível real de microfone.
        O caminho do Windows Speech (SAPI) não expõe esse dado (a
        gramática de ditado não dá acesso ao áudio bruto), então
        `on_nivel` não é chamado nesse caso.

        `initial_prompt`, se fornecido, é repassado ao Whisper (ver
        WhisperFallbackRecognizer.transcrever) — usado pela detecção
        de palavra de ativação (ver core/alfa_core.py). O SAPI não tem
        esse conceito, então é ignorado nesse caminho.

        `max_seconds`, se fornecido, encurta a janela de gravação só
        nesta chamada (ver WhisperFallbackRecognizer.listen) — usado
        pelo standby para não esperar o teto inteiro em silêncio.
        """

        if self._windows is not None:
            try:
                texto = self._windows.listen()
                if texto and _texto_parece_ruido(texto):
                    print(f"[ALFA VOZ] Transcrição descartada por parecer ruído: {texto!r}")
                    return "", "windows_speech"
                if texto:
                    return texto, "windows_speech"
            except Exception as erro:
                print(f"[ALFA VOZ] Falha no Windows Speech: {erro}. Caindo para Whisper.")

        try:
            # A validação de ruído/repetição já acontece dentro do
            # WhisperFallbackRecognizer.listen (tem acesso à duração
            # real do áudio capturado, necessária para o filtro).
            texto = self._whisper.listen(on_nivel=on_nivel, initial_prompt=initial_prompt, max_seconds=max_seconds)
            return texto, "whisper"
        except Exception as erro:
            print(f"[ALFA VOZ] Falha no Whisper: {erro}.")
            return "", "erro"
