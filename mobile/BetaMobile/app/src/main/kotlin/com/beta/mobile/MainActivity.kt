package com.beta.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalConfiguration
import androidx.core.content.ContextCompat
import com.beta.mobile.avatar.MapeadorDeVisema
import com.beta.mobile.avatar.PerfilDesempenho
import com.beta.mobile.avatar.Visema
import com.beta.mobile.licensing.Conectividade
import com.beta.mobile.licensing.CredencialProprietario
import com.beta.mobile.licensing.GerenciadorLicenca
import com.beta.mobile.licensing.Modulo
import com.beta.mobile.licensing.Nivel
import com.beta.mobile.licensing.ResultadoAtivacao
import com.beta.mobile.ui.*
import kotlinx.coroutines.delay

/**
 * BETA Mobile — NOVA INTERFACE para a arquitetura já existente da
 * BETA (ver README.md desta pasta e api/contrato.py no núcleo
 * desktop). Nenhum "cérebro" novo aqui: Planner/Verifier/Tool
 * Registry/Skills/Permissões continuam sendo responsabilidade do
 * BETA Core (desktop) — este app só fala com essa camada através da
 * API (quando configurada) e, localmente, com o catálogo de teste e
 * os motores de voz nativos do Android.
 */
class MainActivity : ComponentActivity() {
    private lateinit var voz: VoiceController
    private lateinit var preferencias: Preferencias
    private lateinit var catalogo: Catalogo

    private val pedirPermissoes = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { /* resultado tratado via temPermissao() a cada uso — best-effort, nunca trava o app */ }

    // Importação de arquivo .beta-license (item do pedido: "sem código
    // manual de ativação") — o proprietário escolhe o arquivo recebido
    // do BETA_OWNER, em vez de copiar/colar um bloco de texto. Nunca lê
    // nada além do texto do arquivo escolhido pela própria pessoa.
    private var conteudoLicencaImportado by mutableStateOf<String?>(null)
    private val selecionarArquivoLicenca = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->
        if (uri != null) {
            try {
                contentResolver.openInputStream(uri)?.use { fluxo ->
                    conteudoLicencaImportado = fluxo.bufferedReader().readText()
                }
            } catch (e: Exception) {
                Log.w("BetaManutencao", "falha ao ler arquivo de licença importado")
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        voz = VoiceController(this)
        preferencias = Preferencias(this)
        catalogo = Catalogo(this)
        voz.iniciar {
            // Escolhe automaticamente a melhor voz feminina pt-BR
            // disponível (item do pedido) na primeira vez que o app
            // roda — depois disso, respeita sempre a escolha da pessoa.
            val vozSalva = preferencias.vozSelecionada
            if (vozSalva == null) {
                val melhor = voz.melhorVozFemininaPtBr()
                if (melhor != null) preferencias.vozSelecionada = melhor.name
            }
            voz.definirVoz(preferencias.vozSelecionada)
            voz.definirVelocidade(preferencias.velocidadeVoz)
            voz.definirTom(preferencias.tomVoz)
        }

        pedirPermissoes.launch(arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA))

        setContent {
            AppBeta(
                voz, preferencias, catalogo, ::temPermissaoMicrofone, ::temPermissaoCamera,
                conteudoLicencaImportado = conteudoLicencaImportado,
                aoConsumirLicencaImportada = { conteudoLicencaImportado = null },
                aoAbrirSeletorArquivoLicenca = { selecionarArquivoLicenca.launch("*/*") },
            )
        }
    }

    private fun temPermissaoMicrofone(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun temPermissaoCamera(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override fun onDestroy() {
        voz.liberar()
        super.onDestroy()
    }
}

private enum class Tela { SPLASH, SELETOR, DISCRETO, APLICATIVO, TOTEM, CONFIGURACOES, MANUTENCAO, DESENVOLVEDOR, PROPRIETARIO, INDISPONIVEL }

private const val LIMITE_TENTATIVAS_PIN = 5
private const val BLOQUEIO_PIN_MS = 30_000L

@Composable
private fun AppBeta(
    voz: VoiceController,
    preferencias: Preferencias,
    catalogo: Catalogo,
    temPermissaoMicrofone: () -> Boolean,
    temPermissaoCamera: () -> Boolean,
    conteudoLicencaImportado: String?,
    aoConsumirLicencaImportada: () -> Unit,
    aoAbrirSeletorArquivoLicenca: () -> Unit,
) {
    // Splash sempre aparece primeiro no toque do ícone (item 1 do
    // pedido de identidade), 100% offline, antes até do seletor de
    // modo — independe de haver modo salvo ou não.
    var tela by remember { mutableStateOf(Tela.SPLASH) }
    var estadoBeta by remember { mutableStateOf(EstadoBeta.PARADO) }
    var ultimaResposta by remember { mutableStateOf("") }
    var historico by remember { mutableStateOf(listOf<Pair<Boolean, String>>()) }
    var mostrarCamera by remember { mutableStateOf(false) }
    var tamanhoFonte by remember { mutableStateOf(preferencias.tamanhoFonte) }
    var altoContraste by remember { mutableStateOf(preferencias.altoContraste) }
    var perfilDesempenho by remember { mutableStateOf(preferencias.perfilDesempenho) }
    var mostrarDialogoMudarModo by remember { mutableStateOf(false) }
    // Pulso curto de "confirmação" do avatar (CONFIRMING) depois de
    // uma resposta falada com sucesso — não faz parte de EstadoBeta
    // porque não deve desabilitar nenhum botão (ver EstadoParaAvatar.kt).
    var confirmando by remember { mutableStateOf(false) }
    // Visema atual da boca — vem do TEXTO REAL sendo falado pelo TTS
    // naquele instante (ver VoiceController.falar/onRangeStart).
    var visemaAtual by remember { mutableStateOf(Visema.REST) }
    // Produtos da última resposta do catálogo — exibidos como "cards"
    // no Modo Aplicativo (item do pedido).
    var ultimosProdutos by remember { mutableStateOf(listOf<Produto>()) }
    var mostrarSobre by remember { mutableStateOf(false) }
    var mostrarHistorico by remember { mutableStateOf(false) }
    // Auditoria local (item do pedido: "AUDITORIA... nunca mostrar
    // senha/token/segredo") — mesmas strings já usadas nos Log.i/w
    // deste arquivo, nunca nada além disso; limitada em memória, não
    // é um substituto de um log de auditoria remoto de verdade.
    val auditoria = remember { mutableStateListOf<RegistroAuditoria>() }
    val formatadorHoraAuditoria = remember { java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale("pt", "BR")) }
    fun registrar(acao: String, resultado: String, aviso: Boolean = false) {
        if (aviso) Log.w("BetaManutencao", "$acao: $resultado") else Log.i("BetaManutencao", "$acao: $resultado")
        auditoria.add(RegistroAuditoria(formatadorHoraAuditoria.format(java.util.Date()), acao, resultado))
        if (auditoria.size > 200) auditoria.removeAt(0)
    }
    // Modo de Manutenção do Totem (item do pedido): só alcançável via
    // botão discreto "⚙ MANUTENÇÃO" + PIN correto — nunca só "esconder
    // botão". Tentativas erradas são limitadas (item "segurança").
    var mostrarDialogoPin by remember { mutableStateOf(false) }
    var erroPinManutencao by remember { mutableStateOf(false) }
    var tentativasPinErradas by remember { mutableIntStateOf(0) }
    var bloqueadoAte by remember { mutableStateOf(0L) }
    var ultimaAtividadeManutencao by remember { mutableStateOf(0L) }
    var mostrarCatalogoAdministrativo by remember { mutableStateOf(false) }
    var mostrarDispositivo by remember { mutableStateOf(false) }
    // Segundo nível (DEVELOPER) — PIN SEPARADO do operador (item do
    // pedido: "OPERATOR nunca vira DEVELOPER somente com o PIN
    // operacional"). Mesmo mecanismo de limite de tentativas.
    var mostrarDialogoPinDev by remember { mutableStateOf(false) }
    var erroPinDev by remember { mutableStateOf(false) }
    var tentativasPinDevErradas by remember { mutableIntStateOf(0) }
    var bloqueadoDevAte by remember { mutableStateOf(0L) }

    // Terceiro nível (BETA_OWNER) — autoridade máxima sobre
    // licenciamento e liberação de módulos (item do pedido). Sem
    // senha hardcoded: a primeira definida com sucesso é a que vale
    // (ver CredencialProprietario/DialogoSenhaProprietario).
    val licenciamento = remember { GerenciadorLicenca(preferencias) }
    // Muda toda vez que uma ativação/revogação acontece, só pra forçar
    // a recomposição dos módulos autorizados (licencaAtual() sempre
    // reverifica a assinatura na hora — nunca confia em cache).
    var licencaVersao by remember { mutableIntStateOf(0) }
    val modulosAutorizados = remember(licencaVersao) { Modulo.values().filter { licenciamento.moduloAutorizado(it) }.toSet() }
    var mostrarDialogoSenhaProprietario by remember { mutableStateOf(false) }
    var erroSenhaProprietario by remember { mutableStateOf(false) }
    var tentativasSenhaProprietarioErradas by remember { mutableIntStateOf(0) }
    var bloqueadoProprietarioAte by remember { mutableStateOf(0L) }
    var resultadoAtivacaoLicenca by remember { mutableStateOf<ResultadoAtivacao?>(null) }

    // Tablet (item 12): mesma tela, mas com áreas de toque e
    // tipografia levemente maiores — nunca um app separado.
    val larguraDp = LocalConfiguration.current.screenWidthDp
    val ehTablet = larguraDp >= 600

    // Item 24 do pedido: "se o Totem não estiver autorizado, mostrar
    // somente a frase genérica, nunca código técnico" — vale para
    // qualquer modo, não só o Totem.
    fun trocarModo(modo: ModoBeta) {
        mostrarDialogoMudarModo = false
        if (moduloDoModo(modo) !in modulosAutorizados) {
            tela = Tela.INDISPONIVEL
            return
        }
        preferencias.modo = modo
        tela = telaDoModo(modo)
    }

    fun falarResposta(resposta: String, comHistorico: Boolean) {
        ultimaResposta = resposta
        if (comHistorico) historico = historico + (false to resposta)
        // A atendente só volta pra PARADO quando o TTS realmente
        // termina (callback real do motor, ver VoiceController.falar) —
        // antes disso o estado ficava FALANDO por um instante e voltava
        // pra PARADO na hora, sem nunca acompanhar a fala de verdade.
        estadoBeta = EstadoBeta.FALANDO
        voz.falar(
            resposta,
            aoTerminar = {
                estadoBeta = EstadoBeta.PARADO
                confirmando = true
            },
            aoTrechoFalado = { trecho -> visemaAtual = MapeadorDeVisema.doTrecho(trecho) },
        )
    }

    fun abrirCatalogo() {
        estadoBeta = EstadoBeta.PROCESSANDO
        ultimosProdutos = catalogo.produtos
        falarResposta("No catálogo de teste temos: " + listaProdutosLegivel(catalogo.produtos), comHistorico = false)
    }

    fun abrirAjuda() {
        estadoBeta = EstadoBeta.PROCESSANDO
        falarResposta(
            "Toque no círculo ou no botão para falar comigo. Você pode perguntar sobre produtos do catálogo, ou usar MUDAR MODO para trocar entre Discreto, Aplicativo e Totem.",
            comHistorico = false,
        )
    }

    fun registrarAtividadeManutencao() { ultimaAtividadeManutencao = System.currentTimeMillis() }

    /** Botão discreto "⚙ MANUTENÇÃO" do Totem — NUNCA concede acesso
     * direto, só abre o pedido de PIN (a não ser que esteja em
     * cooldown por tentativas erradas demais). */
    fun abrirManutencao() {
        val agora = System.currentTimeMillis()
        registrar("botão de manutenção", "tocado")
        if (agora < bloqueadoAte) return
        erroPinManutencao = false
        mostrarDialogoPin = true
    }

    /** Confere o PIN (nunca loga o valor — item "segurança: PIN
     * exposto/PIN em log"). Limita tentativas: depois de
     * LIMITE_TENTATIVAS_PIN erradas, impõe um cooldown antes de
     * aceitar nova tentativa. */
    fun confirmarPinManutencao(pin: String) {
        if (pin == preferencias.pinAdministrativo) {
            registrar("acesso de manutenção", "concedido")
            tentativasPinErradas = 0
            mostrarDialogoPin = false
            erroPinManutencao = false
            registrarAtividadeManutencao()
            tela = Tela.MANUTENCAO
        } else {
            registrar("acesso de manutenção", "tentativa de PIN incorreta", aviso = true)
            tentativasPinErradas++
            if (tentativasPinErradas >= LIMITE_TENTATIVAS_PIN) {
                bloqueadoAte = System.currentTimeMillis() + BLOQUEIO_PIN_MS
                tentativasPinErradas = 0
                mostrarDialogoPin = false
            } else {
                erroPinManutencao = true
            }
        }
    }

    fun abrirAreaDesenvolvedor() {
        val agora = System.currentTimeMillis()
        registrar("área do desenvolvedor", "tocado")
        if (agora < bloqueadoDevAte) return
        erroPinDev = false
        mostrarDialogoPinDev = true
    }

    fun confirmarPinDev(pin: String) {
        if (pin == preferencias.pinDesenvolvedor) {
            registrar("acesso de desenvolvedor", "concedido")
            tentativasPinDevErradas = 0
            mostrarDialogoPinDev = false
            erroPinDev = false
            registrarAtividadeManutencao()
            tela = Tela.DESENVOLVEDOR
        } else {
            registrar("acesso de desenvolvedor", "tentativa de PIN incorreta", aviso = true)
            tentativasPinDevErradas++
            if (tentativasPinDevErradas >= LIMITE_TENTATIVAS_PIN) {
                bloqueadoDevAte = System.currentTimeMillis() + BLOQUEIO_PIN_MS
                tentativasPinDevErradas = 0
                mostrarDialogoPinDev = false
            } else {
                erroPinDev = true
            }
        }
    }

    /** Botão "Área do proprietário" (dentro do painel do
     * desenvolvedor) — abre só o pedido de senha, nunca o painel
     * direto (mesmo padrão de segurança do Operator/Developer). */
    fun abrirAreaProprietario() {
        val agora = System.currentTimeMillis()
        registrar("área do proprietário", "tocado")
        if (agora < bloqueadoProprietarioAte) return
        erroSenhaProprietario = false
        resultadoAtivacaoLicenca = null
        mostrarDialogoSenhaProprietario = true
    }

    /** Confere a senha do proprietário (nunca loga o valor). Sem hash
     * salvo ainda, a senha digitada agora DEFINE a senha (item do
     * pedido: "nunca senha hardcoded" — não existe uma de fábrica). */
    fun confirmarSenhaProprietario(senha: String) {
        val hashSalvo = preferencias.senhaProprietarioHash
        val salSalvo = preferencias.senhaProprietarioSal
        if (hashSalvo == null || salSalvo == null) {
            val novoSal = CredencialProprietario.gerarSal()
            preferencias.senhaProprietarioSal = novoSal
            preferencias.senhaProprietarioHash = CredencialProprietario.hash(senha, novoSal)
            registrar("senha de proprietário", "definida pela primeira vez")
            tentativasSenhaProprietarioErradas = 0
            mostrarDialogoSenhaProprietario = false
            registrarAtividadeManutencao()
            tela = Tela.PROPRIETARIO
        } else if (CredencialProprietario.confere(senha, salSalvo, hashSalvo)) {
            registrar("acesso de proprietário", "concedido")
            tentativasSenhaProprietarioErradas = 0
            mostrarDialogoSenhaProprietario = false
            erroSenhaProprietario = false
            registrarAtividadeManutencao()
            tela = Tela.PROPRIETARIO
        } else {
            registrar("acesso de proprietário", "tentativa de senha incorreta", aviso = true)
            tentativasSenhaProprietarioErradas++
            if (tentativasSenhaProprietarioErradas >= LIMITE_TENTATIVAS_PIN) {
                bloqueadoProprietarioAte = System.currentTimeMillis() + BLOQUEIO_PIN_MS
                tentativasSenhaProprietarioErradas = 0
                mostrarDialogoSenhaProprietario = false
            } else {
                erroSenhaProprietario = true
            }
        }
    }

    fun ativarLicencaLocal(conteudoArquivo: String) {
        resultadoAtivacaoLicenca = licenciamento.ativarLocal(conteudoArquivo)
        val resultado = resultadoAtivacaoLicenca
        registrar("ativação de licença local", resultado?.javaClass?.simpleName ?: "?")
        if (resultado is ResultadoAtivacao.Sucesso) licencaVersao++
    }

    fun revogarLicencaLocal() {
        registrar("licença local", "revogada pelo proprietário")
        licenciamento.revogarLocal()
        resultadoAtivacaoLicenca = null
        licencaVersao++
    }

    /** Nome pra saudação personalizada (item do pedido: "esse é o
     * Marcelo, apresente-se para ele") — usado só na hora, NUNCA
     * salvo (item do pedido: "não salvar automaticamente
     * relacionamento pessoal"). */
    fun nomeParaApresentacao(t: String): String? {
        Regex("apresente-?se para (?:o |a )?([a-zà-úü]+)").find(t)?.groupValues?.get(1)?.let {
            return it.replaceFirstChar { c -> c.uppercase() }
        }
        Regex("ess[ae] [eé] [oa] ([a-zà-úü]+)").find(t)?.groupValues?.get(1)?.let {
            return it.replaceFirstChar { c -> c.uppercase() }
        }
        return null
    }

    /** Comandos de acessibilidade por VOZ (item do pedido) — "Beta,
     * aumente o texto"/"ative o alto contraste"/"preciso de ajuda"/
     * "fale tudo para mim" funcionam em qualquer modo, sem precisar de
     * nenhum painel visual. Retorna true se reconheceu um comando (e
     * já respondeu), false se deve seguir pro catálogo normalmente. */
    fun tentarComandoDeAcessibilidade(pergunta: String): Boolean {
        val t = pergunta.lowercase()
        return when {
            // Comando de silêncio (item do pedido) — para a fala JÁ EM
            // ANDAMENTO na hora, real (VoiceController.pararDeFalar),
            // nunca só um efeito visual. Nunca responde depois de
            // parar — isso contrariaria o próprio pedido de silêncio.
            t == "pare" || "pare de falar" in t || "fique em silencio" in t || "fique em silêncio" in t ||
                t == "silencio" || t == "silêncio" || "cale-se" in t || "cale se" in t ||
                "nao fale" in t || "não fale" in t -> {
                voz.pararDeFalar(); estadoBeta = EstadoBeta.PARADO; true
            }
            "fale mais alto" in t -> {
                voz.aumentarVolume(); falarResposta("Beleza, aumentei o volume.", comHistorico = false); true
            }
            "fale mais baixo" in t -> {
                voz.diminuirVolume(); falarResposta("Certo, diminuí o volume.", comHistorico = false); true
            }
            // Modo Apresentação (item do pedido) — nunca salva o nome
            // informado, só usa na saudação da vez.
            nomeParaApresentacao(t) != null -> {
                falarResposta("Olá, ${nomeParaApresentacao(t)}! Eu sou a BETA, assistente virtual do Sistema Alpha, da RMD.", comHistorico = false)
                true
            }
            "apresente-se" in t || "apresente se" in t -> {
                falarResposta(
                    "Olá! Eu sou a BETA, assistente virtual do Sistema Alpha, da RMD. Posso ajudar com o catálogo, acessibilidade e no que mais precisar.",
                    comHistorico = false,
                )
                true
            }
            "iniciar demonstracao" in t || "iniciar demonstração" in t -> {
                falarResposta(
                    "Vou mostrar rapidamente o que já funciona: o catálogo de demonstração de uma farmácia, com mais de cem produtos. " +
                        "Você pode perguntar, por exemplo: quero uma dipirona, qual é a mais barata, quero três unidades, ou quanto fica tudo.",
                    comHistorico = false,
                )
                true
            }
            "aument" in t && ("texto" in t || "fonte" in t || "letra" in t) -> {
                tamanhoFonte = TamanhoFonte.GRANDE; preferencias.tamanhoFonte = TamanhoFonte.GRANDE
                falarResposta("Deixei o texto maior.", comHistorico = false); true
            }
            "diminu" in t && ("texto" in t || "fonte" in t || "letra" in t) -> {
                tamanhoFonte = TamanhoFonte.PEQUENA; preferencias.tamanhoFonte = TamanhoFonte.PEQUENA
                falarResposta("Deixei o texto menor.", comHistorico = false); true
            }
            ("ativ" in t || "liga" in t) && ("acessibilidade" in t || "contraste" in t) -> {
                altoContraste = true; preferencias.altoContraste = true
                falarResposta("Ativei o alto contraste.", comHistorico = false); true
            }
            ("desativ" in t || "desliga" in t) && ("acessibilidade" in t || "contraste" in t) -> {
                altoContraste = false; preferencias.altoContraste = false
                falarResposta("Desativei o alto contraste.", comHistorico = false); true
            }
            "preciso de ajuda" in t || "me ajude" in t || "pode me ajudar" in t -> {
                abrirAjuda(); true
            }
            "fale tudo" in t || "leia tudo" in t || "leia pra mim" in t || "leia para mim" in t -> {
                ultimosProdutos = catalogo.produtos
                falarResposta("Aqui está o que temos: " + listaProdutosLegivel(catalogo.produtos), comHistorico = false)
                true
            }
            else -> false
        }
    }

    fun processarPergunta(pergunta: String) {
        historico = historico + (true to pergunta)
        estadoBeta = EstadoBeta.PROCESSANDO
        if (tentarComandoDeAcessibilidade(pergunta)) return
        // Consulta LOCAL ao catálogo de teste (ver Catalogo.kt) — nunca
        // inventa produto/preço, entende a frase inteira e mantém
        // contexto entre turnos (produto em foco, última busca). Quando
        // a API do BETA-CLOUD estiver configurada e autenticada, esta é
        // a camada que passaria a rotear pra lá também (ver BetaCloudApi.kt).
        val resposta = catalogo.responderPergunta(pergunta, licenciamento.emModoDemo())
        ultimosProdutos = resposta.produtos
        falarResposta(resposta.texto, comHistorico = true)
    }

    fun aoTocarMicrofone() {
        if (!temPermissaoMicrofone()) {
            estadoBeta = EstadoBeta.ERRO
            ultimaResposta = "Preciso da permissão de microfone para te ouvir."
            return
        }
        estadoBeta = EstadoBeta.OUVINDO
        voz.ouvirUmaVez(
            aoResultado = { texto ->
                estadoBeta = EstadoBeta.PARADO
                if (texto.isNotBlank()) processarPergunta(texto)
            },
            aoErro = { erro ->
                estadoBeta = EstadoBeta.ERRO
                ultimaResposta = erro
            },
        )
    }

    // ERRO é passageiro — some sozinho depois de alguns segundos pra
    // não travar o botão de toque (ele só aceita toque em PARADO).
    LaunchedEffect(estadoBeta) {
        if (estadoBeta == EstadoBeta.ERRO) {
            delay(2500)
            estadoBeta = EstadoBeta.PARADO
        }
    }

    // CONFIRMING também é passageiro — um sorriso rápido depois da
    // resposta, não um estado permanente.
    LaunchedEffect(confirmando) {
        if (confirmando) {
            delay(900)
            confirmando = false
        }
    }

    // Importação de arquivo .beta-license (item do pedido: "sem código
    // manual de ativação") — quando a Activity devolve o texto do
    // arquivo escolhido, ativa exatamente como se tivesse sido colado.
    LaunchedEffect(conteudoLicencaImportado) {
        val conteudo = conteudoLicencaImportado
        if (conteudo != null) {
            ativarLicencaLocal(conteudo)
            aoConsumirLicencaImportada()
        }
    }

    // Timeout do Modo de Manutenção (item do pedido) — depois de um
    // tempo sem nenhuma ação administrativa, volta sozinho pro Totem
    // público e exige PIN de novo na próxima entrada.
    LaunchedEffect(tela) {
        if (tela == Tela.MANUTENCAO) {
            while (true) {
                delay(2000)
                if (System.currentTimeMillis() - ultimaAtividadeManutencao > preferencias.timeoutManutencaoMs) {
                    tela = Tela.TOTEM
                    break
                }
            }
        }
    }

    val escalaBase = escalaFonte(tamanhoFonte) * if (ehTablet) 1.15f else 1f

    BetaTheme(altoContraste = altoContraste, escala = escalaBase) {
        when (tela) {
            Tela.SPLASH -> SplashScreen(
                duracaoMs = preferencias.duracaoSplashMs,
                aoTerminar = {
                    val modoSalvo = preferencias.modo
                    tela = when {
                        modoSalvo == null -> Tela.SELETOR
                        moduloDoModo(modoSalvo) !in modulosAutorizados -> Tela.INDISPONIVEL
                        else -> telaDoModo(modoSalvo)
                    }
                },
            )

            Tela.SELETOR -> SeletorModoScreen(modulosAutorizados = modulosAutorizados, aoEscolher = { modo -> trocarModo(modo) })

            Tela.INDISPONIVEL -> TelaRecursoIndisponivel(aoVoltar = { tela = Tela.SELETOR })

            Tela.DISCRETO -> ModoDiscretoScreen(
                estado = estadoBeta,
                ultimaResposta = ultimaResposta,
                visema = visemaAtual,
                perfil = perfilDesempenho,
                aoTocarMicrofone = ::aoTocarMicrofone,
                aoMudarModo = { mostrarDialogoMudarModo = true },
            )

            Tela.APLICATIVO -> ModoAplicativoScreen(
                estado = estadoBeta,
                ultimaResposta = ultimaResposta,
                historico = historico,
                mostrarCamera = mostrarCamera && temPermissaoCamera(),
                produtosEmDestaque = ultimosProdutos,
                visema = visemaAtual,
                perfil = perfilDesempenho,
                confirmando = confirmando,
                aoTocarMicrofone = ::aoTocarMicrofone,
                aoEnviarTexto = { processarPergunta(it) },
                aoAlternarCamera = { mostrarCamera = !mostrarCamera },
                aoAbrirConfiguracoes = { tela = Tela.CONFIGURACOES },
                aoMudarModo = { mostrarDialogoMudarModo = true },
                aoAbrirCatalogo = ::abrirCatalogo,
                aoAbrirHistorico = { mostrarHistorico = true },
                aoAbrirSobre = { mostrarSobre = true },
            )

            Tela.TOTEM -> ModoTotemScreen(
                estado = estadoBeta,
                ultimaResposta = ultimaResposta,
                produtosEmDestaque = ultimosProdutos,
                visema = visemaAtual,
                perfil = perfilDesempenho,
                confirmando = confirmando,
                aoTocarTela = ::aoTocarMicrofone,
                aoAbrirAjuda = ::abrirAjuda,
                aoAbrirManutencao = ::abrirManutencao,
            )

            Tela.MANUTENCAO -> PainelManutencaoScreen(
                aoIrParaTotem = { registrarAtividadeManutencao(); trocarModo(ModoBeta.TOTEM) },
                aoIrParaAplicativo = { registrarAtividadeManutencao(); trocarModo(ModoBeta.APLICATIVO) },
                aoIrParaDiscreto = { registrarAtividadeManutencao(); trocarModo(ModoBeta.DISCRETO) },
                aoAbrirCatalogoAdministrativo = { registrarAtividadeManutencao(); mostrarCatalogoAdministrativo = true },
                aoAbrirConfiguracoes = { registrarAtividadeManutencao(); tela = Tela.CONFIGURACOES },
                aoAbrirAcessibilidade = { registrarAtividadeManutencao(); tela = Tela.CONFIGURACOES },
                aoAbrirDispositivo = { registrarAtividadeManutencao(); mostrarDispositivo = true },
                aoAbrirSobre = { registrarAtividadeManutencao(); mostrarSobre = true },
                aoAbrirAreaDesenvolvedor = ::abrirAreaDesenvolvedor,
                aoVoltarAoTotem = { tela = Tela.TOTEM },
            )

            Tela.DESENVOLVEDOR -> {
                val contextoControle = androidx.compose.ui.platform.LocalContext.current
                val possuiInternetDev = remember(tela) { Conectividade.possuiInternet(contextoControle) }
                PainelBetaControlScreen(
                    nivel = Nivel.BETA_DEVELOPER,
                    deviceId = preferencias.deviceId,
                    plataforma = "Android ${Build.VERSION.RELEASE ?: "?"} (${Build.MANUFACTURER} ${Build.MODEL})",
                    modelo = "${Build.MANUFACTURER} ${Build.MODEL}",
                    versaoAndroid = Build.VERSION.RELEASE ?: "desconhecida",
                    versaoApp = BuildConfig.VERSION_NAME,
                    possuiInternet = possuiInternetDev,
                    emModoDemo = licenciamento.emModoDemo(),
                    modulosAtivos = modulosAutorizados,
                    estadoModulo = { modulo -> licenciamento.estadoDoModulo(modulo) },
                    licenca = licenciamento.licencaAtual(),
                    resultadoAtivacao = null,
                    auditoria = auditoria,
                    aoAtivar = {},
                    aoImportarArquivo = {},
                    aoRevogar = {},
                    aoAbrirConfiguracoes = { tela = Tela.CONFIGURACOES },
                    aoAbrirAreaProprietario = ::abrirAreaProprietario,
                    aoVoltar = { tela = Tela.MANUTENCAO },
                )
            }

            Tela.PROPRIETARIO -> {
                val contextoControle = androidx.compose.ui.platform.LocalContext.current
                val possuiInternet = remember(tela) { Conectividade.possuiInternet(contextoControle) }
                PainelBetaControlScreen(
                    nivel = Nivel.BETA_OWNER,
                    deviceId = preferencias.deviceId,
                    plataforma = "Android ${Build.VERSION.RELEASE ?: "?"} (${Build.MANUFACTURER} ${Build.MODEL})",
                    modelo = "${Build.MANUFACTURER} ${Build.MODEL}",
                    versaoAndroid = Build.VERSION.RELEASE ?: "desconhecida",
                    versaoApp = BuildConfig.VERSION_NAME,
                    possuiInternet = possuiInternet,
                    emModoDemo = licenciamento.emModoDemo(),
                    modulosAtivos = modulosAutorizados,
                    estadoModulo = { modulo -> licenciamento.estadoDoModulo(modulo) },
                    licenca = licenciamento.licencaAtual(),
                    resultadoAtivacao = resultadoAtivacaoLicenca,
                    auditoria = auditoria,
                    aoAtivar = { conteudo -> registrarAtividadeManutencao(); ativarLicencaLocal(conteudo) },
                    aoImportarArquivo = { registrarAtividadeManutencao(); aoAbrirSeletorArquivoLicenca() },
                    aoRevogar = { registrarAtividadeManutencao(); revogarLicencaLocal() },
                    aoAbrirConfiguracoes = { tela = Tela.CONFIGURACOES },
                    aoAbrirAreaProprietario = null,
                    aoVoltar = { tela = Tela.DESENVOLVEDOR },
                )
            }

            Tela.CONFIGURACOES -> {
                val vozes = remember(tela) { voz.vozesDisponiveis() }
                val opcoesVoz = remember(vozes) { vozes.map { VozOpcao(it.name, rotuloAmigavelDaVoz(vozes, it), generoDaVoz(it)) } }
                val temVozPtBr = remember(tela) { voz.possuiVozPtBr() }
                var vozSelecionada by remember { mutableStateOf(preferencias.vozSelecionada) }
                var velocidadeVoz by remember { mutableStateOf(preferencias.velocidadeVoz) }
                var tomVoz by remember { mutableStateOf(preferencias.tomVoz) }
                ConfiguracoesScreen(
                    tamanhoFonte = tamanhoFonte,
                    altoContraste = altoContraste,
                    vozes = opcoesVoz,
                    vozSelecionada = vozSelecionada,
                    possuiVozPtBr = temVozPtBr,
                    velocidadeVoz = velocidadeVoz,
                    tomVoz = tomVoz,
                    perfilDesempenho = perfilDesempenho,
                    aoMudarTamanho = { tamanhoFonte = it; preferencias.tamanhoFonte = it },
                    aoMudarContraste = { altoContraste = it; preferencias.altoContraste = it },
                    aoSelecionarVoz = { nome ->
                        vozSelecionada = nome
                        preferencias.vozSelecionada = nome
                        voz.definirVoz(nome)
                    },
                    aoTestarVoz = { voz.falar("Olá! Eu sou a BETA, sua assistente virtual.") },
                    aoMudarVelocidade = { velocidadeVoz = it; preferencias.velocidadeVoz = it; voz.definirVelocidade(it) },
                    aoMudarTom = { tomVoz = it; preferencias.tomVoz = it; voz.definirTom(it) },
                    aoMudarPerfilDesempenho = { perfilDesempenho = it; preferencias.perfilDesempenho = it },
                    pinAdministrativo = preferencias.pinAdministrativo,
                    aoMudarPin = { preferencias.pinAdministrativo = it },
                    timeoutManutencaoMs = preferencias.timeoutManutencaoMs,
                    aoMudarTimeoutManutencao = { preferencias.timeoutManutencaoMs = it },
                    aoTrocarModo = { mostrarDialogoMudarModo = true },
                    aoVoltar = { tela = telaDoModo(preferencias.modo ?: ModoBeta.APLICATIVO) },
                )
            }
        }

        // Diálogo de troca de modo (item 10) — flutua sobre qualquer
        // tela de modo, nunca encerra nem reinicia a Activity.
        if (mostrarDialogoMudarModo) {
            DialogoMudarModo(
                modulosAutorizados = modulosAutorizados,
                aoEscolher = { modo -> trocarModo(modo) },
                aoCancelar = { mostrarDialogoMudarModo = false },
            )
        }
        if (mostrarSobre) {
            DialogoSobre(aoFechar = { mostrarSobre = false })
        }
        if (mostrarHistorico) {
            DialogoHistorico(historico = historico, aoFechar = { mostrarHistorico = false })
        }
        if (mostrarDialogoPin) {
            DialogoPinManutencao(
                erro = erroPinManutencao,
                bloqueado = System.currentTimeMillis() < bloqueadoAte,
                aoConfirmar = { pin -> confirmarPinManutencao(pin) },
                aoCancelar = { mostrarDialogoPin = false; erroPinManutencao = false },
            )
        }
        if (mostrarCatalogoAdministrativo) {
            DialogoCatalogoAdministrativo(
                produtos = catalogo.produtos,
                aoFechar = { mostrarCatalogoAdministrativo = false },
            )
        }
        if (mostrarDispositivo) {
            DialogoDispositivo(
                modelo = "${Build.MANUFACTURER} ${Build.MODEL}",
                versaoAndroid = Build.VERSION.RELEASE ?: "desconhecida",
                versaoApp = BuildConfig.VERSION_NAME,
                aoFechar = { mostrarDispositivo = false },
            )
        }
        if (mostrarDialogoPinDev) {
            DialogoPinManutencao(
                erro = erroPinDev,
                bloqueado = System.currentTimeMillis() < bloqueadoDevAte,
                titulo = "ÁREA DO DESENVOLVEDOR",
                subtitulo = "Digite o PIN de desenvolvedor (diferente do PIN de manutenção).",
                aoConfirmar = { pin -> confirmarPinDev(pin) },
                aoCancelar = { mostrarDialogoPinDev = false; erroPinDev = false },
            )
        }
        if (mostrarDialogoSenhaProprietario) {
            DialogoSenhaProprietario(
                primeiraVez = preferencias.senhaProprietarioHash == null,
                erro = erroSenhaProprietario,
                bloqueado = System.currentTimeMillis() < bloqueadoProprietarioAte,
                aoConfirmar = { senha -> confirmarSenhaProprietario(senha) },
                aoCancelar = { mostrarDialogoSenhaProprietario = false; erroSenhaProprietario = false },
            )
        }
    }
}

private fun telaDoModo(modo: ModoBeta): Tela = when (modo) {
    ModoBeta.DISCRETO -> Tela.DISCRETO
    ModoBeta.APLICATIVO -> Tela.APLICATIVO
    ModoBeta.TOTEM -> Tela.TOTEM
}
