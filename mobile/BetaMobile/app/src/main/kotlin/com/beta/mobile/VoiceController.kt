package com.beta.mobile

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.util.Log
import java.util.Locale
import java.util.UUID

/**
 * Voz do BETA Mobile — reaproveita os motores JÁ EMBUTIDOS no Android
 * (SpeechRecognizer para entrada, TextToSpeech para saída) em vez de
 * empacotar um Whisper/Edge TTS separado no celular ("não duplicar o
 * Whisper sem necessidade", ver pedido do mobile). Continua
 * funcionando localmente mesmo sem BETA-CLOUD configurada.
 *
 * "Wake word" contínua não está implementada nesta primeira versão
 * (Android não expõe um mecanismo leve de hotword sempre-ativo para
 * apps de terceiros sem hardware/DSP dedicado) — o v1 usa captura
 * sob demanda (botão), que já cobre "microfone"/"captura de voz"/
 * "resposta por voz" pedidos na primeira entrega. Dentro de UMA
 * captura, se a pessoa disser "Beta, ..." o prefixo é removido (ver
 * `removerPalavraDeAtivacao`) pra não perder o resto da frase.
 */
class VoiceController(private val context: Context) {
    private var reconhecedor: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var prontoParaFalar = false
    private val handlerPrincipal = Handler(Looper.getMainLooper())

    private var aoComecarFala: (() -> Unit)? = null
    private var aoTerminarFala: (() -> Unit)? = null
    private var aoTrechoFalado: ((String) -> Unit)? = null
    private var textoFalaAtual: String = ""
    private var recebeuRangeStart = false
    private var indiceFallback = 0

    // Nem todo motor/voz de TTS chama onRangeStart (só é chamado "se o
    // motor fornecer informação de tempo" — ver documentação do
    // Android). Quando isso não acontece, esta troca simples de letras
    // mantém a boca se movendo em vez de ficar travada — é o único
    // mecanismo de fallback que resta (ver pedido: pode manter só como
    // reserva, nunca como caminho principal).
    private val letrasFallback = listOf("a", "m", "o", "e", "i")
    private val fallbackRunnable = object : Runnable {
        override fun run() {
            aoTrechoFalado?.invoke(letrasFallback[indiceFallback % letrasFallback.size])
            indiceFallback++
            handlerPrincipal.postDelayed(this, 160)
        }
    }

    fun iniciar(aoPronto: () -> Unit = {}) {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale("pt", "BR")
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        recebeuRangeStart = false
                        handlerPrincipal.postDelayed({
                            if (!recebeuRangeStart) handlerPrincipal.post(fallbackRunnable)
                        }, 250)
                        handlerPrincipal.post { aoComecarFala?.invoke() }
                    }

                    override fun onRangeStart(utteranceId: String?, start: Int, end: Int, frame: Int) {
                        recebeuRangeStart = true
                        handlerPrincipal.removeCallbacks(fallbackRunnable)
                        val fim = end.coerceIn(start, textoFalaAtual.length)
                        val inicio = start.coerceIn(0, fim)
                        val trecho = textoFalaAtual.substring(inicio, fim)
                        handlerPrincipal.post { aoTrechoFalado?.invoke(trecho) }
                    }

                    override fun onDone(utteranceId: String?) {
                        handlerPrincipal.removeCallbacks(fallbackRunnable)
                        handlerPrincipal.post {
                            aoTrechoFalado?.invoke("")
                            aoTerminarFala?.invoke()
                        }
                    }

                    @Deprecated("Deprecated in Java")
                    override fun onError(utteranceId: String?) {
                        Log.w("BetaVoice", "Erro no TTS para utterance $utteranceId")
                        handlerPrincipal.removeCallbacks(fallbackRunnable)
                        handlerPrincipal.post {
                            aoTrechoFalado?.invoke("")
                            aoTerminarFala?.invoke()
                        }
                    }
                })
                prontoParaFalar = true
                handlerPrincipal.post { aoPronto() }
            }
        }
    }

    fun liberar() {
        handlerPrincipal.removeCallbacks(fallbackRunnable)
        reconhecedor?.destroy()
        reconhecedor = null
        tts?.stop()
        tts?.shutdown()
        tts = null
    }

    fun disponivelParaOuvir(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    /** Remove um "Beta" (ou "Ei Beta"/"Oi Beta") do começo da frase
     * reconhecida, preservando o resto — ver pedido: "Beta, abra o
     * aplicativo" não pode perder "abra o aplicativo". Não é wake
     * word contínua (ver docstring da classe), só limpeza do texto de
     * UMA captura já feita. */
    private fun removerPalavraDeAtivacao(texto: String): String {
        val semAcento = texto.trim()
        val regex = Regex("^(ei |oi |e ai )?beta[,:]?\\s+", RegexOption.IGNORE_CASE)
        return regex.replace(semAcento, "").ifBlank { semAcento }
    }

    /**
     * Captura UMA fala (não é escuta contínua) — chama `aoResultado`
     * com o texto reconhecido (string vazia se nada foi entendido) ou
     * `aoErro` com uma mensagem HUMANA e amigável (nunca um código
     * técnico — isso vai só pro Log, ver pedido de erros). Nunca grava
     * áudio em disco.
     */
    fun ouvirUmaVez(aoResultado: (String) -> Unit, aoErro: (String) -> Unit) {
        if (!disponivelParaOuvir()) {
            aoErro("O reconhecimento de voz não está disponível neste aparelho.")
            return
        }

        reconhecedor?.destroy()
        val instancia = SpeechRecognizer.createSpeechRecognizer(context)
        reconhecedor = instancia

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        }

        instancia.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle) {
                val lista = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val bruto = lista?.firstOrNull() ?: ""
                aoResultado(if (bruto.isBlank()) bruto else removerPalavraDeAtivacao(bruto))
            }

            override fun onError(error: Int) {
                Log.w("BetaVoice", "Erro no reconhecimento de voz, código $error")
                aoErro("Desculpe, não consegui entender. Pode repetir, por favor?")
            }

            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        instancia.startListening(intent)
    }

    fun pararDeOuvir() {
        reconhecedor?.stopListening()
    }

    /**
     * Fala o texto e avisa início/fim/trecho-sendo-falado via
     * callback. `aoTrechoFalado` recebe o pedaço de TEXTO que o motor
     * está falando NAQUELE instante (via `onRangeStart`, real, do
     * próprio áudio tocando — não é um relógio artificial) para a
     * camada de UI decidir o visema da boca (ver
     * com.beta.mobile.avatar.MapeadorDeVisema); recebe string vazia
     * quando a fala termina/erra, para o avatar voltar ao repouso.
     * `aoTerminar` sempre é chamado, mesmo em erro, para o avatar
     * nunca ficar "preso" no estado FALANDO.
     */
    fun falar(texto: String, aoComecar: () -> Unit = {}, aoTerminar: () -> Unit = {}, aoTrechoFalado: (String) -> Unit = {}) {
        if (!prontoParaFalar || texto.isBlank()) {
            aoTerminar()
            return
        }
        textoFalaAtual = texto
        indiceFallback = 0
        aoComecarFala = aoComecar
        aoTerminarFala = aoTerminar
        this.aoTrechoFalado = aoTrechoFalado
        tts?.speak(texto, TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString())
    }

    fun definirVelocidade(velocidade: Float) { tts?.setSpeechRate(velocidade.coerceIn(0.5f, 2f)) }
    fun definirTom(tom: Float) { tts?.setPitch(tom.coerceIn(0.5f, 2f)) }

    /** Comando de silêncio (item do pedido: "pare"/"pare de falar"/
     * "fique em silêncio"/"cale-se"/"não fale") — para a fala JÁ EM
     * ANDAMENTO imediatamente, real (TextToSpeech.stop()), não é só
     * um efeito visual no avatar. */
    fun pararDeFalar() { tts?.stop() }

    /** Volume real do fluxo de mídia (item do pedido: "fale mais
     * alto"/"fale mais baixo") — o TextToSpeech deste app fala no
     * STREAM_MUSIC por padrão, então isto é volume de verdade, não um
     * ajuste só de tom/velocidade disfarçado de volume. Respeita
     * sempre o limite real do aparelho (nunca ultrapassa o máximo do
     * sistema, nunca vai abaixo de zero). */
    private fun gerenciadorDeAudio() = context.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager

    fun aumentarVolume() {
        val gerenciador = gerenciadorDeAudio() ?: return
        gerenciador.adjustStreamVolume(android.media.AudioManager.STREAM_MUSIC, android.media.AudioManager.ADJUST_RAISE, 0)
    }

    fun diminuirVolume() {
        val gerenciador = gerenciadorDeAudio() ?: return
        gerenciador.adjustStreamVolume(android.media.AudioManager.STREAM_MUSIC, android.media.AudioManager.ADJUST_LOWER, 0)
    }

    /** Vozes instaladas no aparelho, só em português do BRASIL (item
     * do pedido: "não apresentar en-US/es/fr/...pt-PT"), femininas
     * antes de masculinas. Nunca inventa vozes — só filtra/ordena o
     * que o TextToSpeech relata de verdade. */
    fun vozesDisponiveis(): List<Voice> =
        tts?.voices
            ?.filterNotNull()
            ?.filter { ehPtBr(it) }
            ?.sortedWith(compareBy({ generoDaVoz(it) != "Feminina" }, { it.name }))
            ?: emptyList()

    /** true se existir pelo menos uma voz pt-BR instalada (contando a
     * padrão do motor) — usado pra avisar quando falta instalar uma. */
    fun possuiVozPtBr(): Boolean =
        vozesDisponiveis().isNotEmpty() || tts?.defaultVoice?.let { ehPtBr(it) } == true

    private fun ehPtBr(voz: Voice): Boolean {
        val locale = voz.locale ?: return false
        val lingua = locale.language.lowercase()
        if (lingua != "pt" && lingua != "por") return false
        val pais = locale.country.uppercase()
        return pais.isBlank() || pais == "BR" || pais == "BRA"
    }

    /** Melhor voz feminina pt-BR disponível — usada como padrão
     * automático (item do pedido) quando a pessoa ainda não escolheu
     * nenhuma voz. */
    fun melhorVozFemininaPtBr(): Voice? =
        vozesDisponiveis().firstOrNull { generoDaVoz(it) == "Feminina" } ?: vozesDisponiveis().firstOrNull()

    fun definirVoz(nomeVoz: String?) {
        val motor = tts ?: return
        if (nomeVoz == null) {
            motor.voice = motor.defaultVoice ?: return
            return
        }
        val alvo = motor.voices?.firstOrNull { it.name == nomeVoz } ?: return
        motor.voice = alvo
    }

    fun nomeDaVozAtual(): String? = tts?.voice?.name
}

/** Pista de gênero a partir do NOME da voz do motor — Android não
 * expõe um campo oficial de gênero em `Voice`, então isso é só uma
 * dica textual (funciona bem no motor do Google, "Padrão" quando não
 * há pista nenhuma no nome). */
fun generoDaVoz(voz: Voice): String {
    val nome = voz.name.lowercase()
    return when {
        "female" in nome -> "Feminina"
        "male" in nome -> "Masculina"
        else -> "Padrão"
    }
}

/** Rótulo amigável e numerado ("Voz Feminina", "Voz Feminina 2"...)
 * pedido explicitamente, a partir da posição da voz dentro do seu
 * próprio grupo de gênero — nunca inventa nome de voz. */
fun rotuloAmigavelDaVoz(vozes: List<Voice>, voz: Voice): String {
    val genero = generoDaVoz(voz)
    val doMesmoGenero = vozes.filter { generoDaVoz(it) == genero }
    val posicao = doMesmoGenero.indexOf(voz) + 1
    val base = if (genero == "Padrão") "Voz do sistema" else "Voz $genero"
    return if (posicao > 1) "$base $posicao" else base
}
