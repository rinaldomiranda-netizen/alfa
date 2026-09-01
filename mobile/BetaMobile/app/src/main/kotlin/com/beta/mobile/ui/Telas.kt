package com.beta.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.beta.mobile.ModoBeta
import com.beta.mobile.Produto
import com.beta.mobile.TamanhoFonte
import com.beta.mobile.avatar.AvatarState
import com.beta.mobile.avatar.BetaAvatar
import com.beta.mobile.avatar.PerfilDesempenho
import com.beta.mobile.avatar.Visema
import com.beta.mobile.licensing.Modulo

enum class EstadoBeta { PARADO, OUVINDO, PROCESSANDO, FALANDO, ERRO }

/** Opção de voz do TTS para a tela de Configurações — o "gênero" é
 * apenas uma pista textual do nome da voz do motor (Android não expõe
 * gênero oficialmente na API de TTS), por isso o rótulo "Padrão"
 * quando não há pista nenhuma. Nunca inventamos vozes que o aparelho
 * não tem instaladas. */
data class VozOpcao(val nome: String, val rotulo: String, val genero: String)

// Glifos simples (sem dependência de ícones estendidos) para não
// adicionar peso/risco de build por causa de 3 ícones — mesmo
// espírito do "⚙" já usado em ModoAplicativoScreen.
private data class OpcaoModo(val modo: ModoBeta, val rotulo: String, val descricao: String, val glifo: String)

private val OPCOES_MODO = listOf(
    OpcaoModo(ModoBeta.DISCRETO, "Modo Discreto", "Tela mínima, só a BETA e o microfone", "◎"),
    OpcaoModo(ModoBeta.APLICATIVO, "Modo Aplicativo", "Conversa completa, texto, voz e câmera", "▤"),
    OpcaoModo(ModoBeta.TOTEM, "Modo Totem", "Tela cheia para atendimento", "⛶"),
)

/** Cada modo de uso corresponde a um módulo licenciável (item do
 * pedido "23. Mobile: o Mobile deve consultar os módulos
 * autorizados"). ASSISTENTE é o nome do módulo pro que o app chama de
 * "Modo Discreto" — mesma coisa, nomes diferentes por contexto. */
fun moduloDoModo(modo: ModoBeta): Modulo = when (modo) {
    ModoBeta.DISCRETO -> Modulo.ASSISTENTE
    ModoBeta.APLICATIVO -> Modulo.APLICATIVO
    ModoBeta.TOTEM -> Modulo.TOTEM
}

@Composable
fun SeletorModoScreen(modulosAutorizados: Set<Modulo>, aoEscolher: (ModoBeta) -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Como você deseja usar a BETA?", style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
        Spacer(Modifier.height(32.dp))
        // Só oferece modos autorizados pela licença (item do pedido:
        // "o seletor não deve oferecer o módulo não autorizado") —
        // nunca lista algo que o toque levaria a uma recusa.
        OPCOES_MODO.filter { moduloDoModo(it.modo) in modulosAutorizados }.forEach { opcao ->
            Card(
                onClick = { aoEscolher(opcao.modo) },
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(opcao.glifo, color = AzulNeon, fontSize = 28.sp)
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(opcao.rotulo, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                        Text(opcao.descricao, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        Spacer(Modifier.height(16.dp))
        Text("Você pode trocar de modo a qualquer momento.", style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(24.dp))
        Text("SISTEMA ALPHA · RMD", style = MaterialTheme.typography.labelSmall, color = DouradoDiscreto)
    }
}

/** Diálogo reutilizável de troca de modo (item 10 do pedido) — nunca
 * encerra o app, só troca o estado de navegação; usável a partir de
 * qualquer uma das 3 telas de modo. */
@Composable
fun DialogoMudarModo(modulosAutorizados: Set<Modulo>, aoEscolher: (ModoBeta) -> Unit, aoCancelar: () -> Unit) {
    AlertDialog(
        onDismissRequest = aoCancelar,
        title = { Text("Como você deseja usar a BETA?") },
        text = {
            Column {
                OPCOES_MODO.filter { moduloDoModo(it.modo) in modulosAutorizados }.forEach { opcao ->
                    TextButton(
                        onClick = { aoEscolher(opcao.modo) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(opcao.glifo, color = AzulNeon, fontSize = 18.sp)
                            Spacer(Modifier.width(12.dp))
                            Text(opcao.rotulo)
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = aoCancelar) { Text("Cancelar") } },
    )
}

private fun rotuloDoEstado(estado: EstadoBeta): String = when (estado) {
    EstadoBeta.PARADO -> "Toque para falar"
    EstadoBeta.OUVINDO -> "OUVINDO"
    EstadoBeta.PROCESSANDO -> "Pensando..."
    EstadoBeta.FALANDO -> "FALANDO"
    EstadoBeta.ERRO -> "Não entendi, pode repetir?"
}

/** Texto principal mostrado ao lado da atendente: a última resposta
 * (ou erro) quando existir, senão a saudação padrão da tela — nunca
 * fica vazio (item de acessibilidade: nunca depender só da animação
 * para passar informação). */
private fun textoDaAtendente(estado: EstadoBeta, ultimaResposta: String, saudacao: String): String = when {
    estado == EstadoBeta.PROCESSANDO -> "Pensando..."
    ultimaResposta.isNotBlank() -> ultimaResposta
    else -> saudacao
}

/** Cor curta do estado — só para o "pontinho" indicador do Modo
 * Discreto (equivalente móvel do indicador "empresa/desktop" pedido:
 * discreto, sem o avatar grande). Nunca é a ÚNICA informação — sempre
 * acompanhada do rótulo em texto de `rotuloDoEstado`. */
private fun corDoPontinho(estado: EstadoBeta): Color? = when (estado) {
    EstadoBeta.OUVINDO -> Color(0xFF3B82F6)
    EstadoBeta.PROCESSANDO -> Color(0xFFF59E0B)
    EstadoBeta.FALANDO -> Color(0xFFA855F7)
    else -> null
}

/** Indicador de estado + avatar interativo da atendente BETA — usado
 * nos 3 modos como o "toque aqui para falar". A expressão do avatar já
 * muda por estado (ver avatar/AvatarRenderer.kt); o rótulo textual
 * abaixo garante que a informação nunca dependa só da animação
 * (acessibilidade). */
@Composable
fun IndicadorEstado(
    estado: EstadoBeta,
    tamanho: Int = 72,
    visema: Visema = Visema.REST,
    perfil: PerfilDesempenho = PerfilDesempenho.BALANCEADO,
    confirmando: Boolean = false,
    aoTocar: () -> Unit,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .size(tamanho.dp)
                .clickableSeParado(estado) { aoTocar() },
            contentAlignment = Alignment.Center,
        ) {
            BetaAvatar(estado = avatarStateDe(estado, confirmando), visema = visema, perfil = perfil, tamanho = tamanho)
        }
        Spacer(Modifier.height(8.dp))
        Text(rotuloDoEstado(estado), fontWeight = FontWeight.Bold)
    }
}

private fun Modifier.clickableSeParado(estado: EstadoBeta, aoClicar: () -> Unit): Modifier =
    this.clickable(enabled = estado == EstadoBeta.PARADO, onClick = aoClicar)

@Composable
fun ModoDiscretoScreen(
    estado: EstadoBeta,
    ultimaResposta: String,
    visema: Visema = Visema.REST,
    perfil: PerfilDesempenho = PerfilDesempenho.BALANCEADO,
    aoTocarMicrofone: () -> Unit,
    aoMudarModo: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        // Equivalente móvel do "modo empresa/discreto" pedido: avatar
        // pequeno, nunca telão — o pontinho colorido é só um reforço
        // visual extra, o texto do rótulo continua sendo a informação
        // real (acessibilidade).
        Box {
            IndicadorEstado(estado, tamanho = 48, visema = visema, perfil = perfil, aoTocar = aoTocarMicrofone)
            corDoPontinho(estado)?.let { cor ->
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .size(10.dp)
                        .background(cor, CircleShape),
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        if (ultimaResposta.isNotBlank()) {
            Text(ultimaResposta, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
        }
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = aoMudarModo) { Text("MUDAR MODO") }
    }
}

/** Item do menu do Modo Aplicativo — glifo + rótulo em texto (item do
 * pedido: "Menu: Conversar/Catálogo/Histórico/Câmera/Acessibilidade/
 * Configurações/Sobre"), nunca só o ícone sozinho (acessibilidade). */
@Composable
private fun ItemMenu(glifo: String, rotulo: String, ativo: Boolean = false, aoClicar: () -> Unit) {
    val cor = if (ativo) AzulNeon else Color(0xFFCBD5E1)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = aoClicar)
            .padding(vertical = 10.dp)
            .semantics { contentDescription = rotulo },
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(glifo, fontSize = 18.sp, color = cor)
        Spacer(Modifier.height(2.dp))
        Text(rotulo, fontSize = 10.sp, color = cor, textAlign = TextAlign.Center)
    }
}

/** "Card" de produto (item do pedido: "Cards: resultados/produtos") —
 * nunca inventa dado, só mostra o que veio do catálogo local. */
@Composable
private fun CardProduto(produto: Produto) {
    Column(
        modifier = Modifier
            .width(150.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(FundoBeta)
            .padding(12.dp),
    ) {
        Text(produto.nome, fontWeight = FontWeight.Bold, fontSize = 13.sp, maxLines = 2)
        Spacer(Modifier.height(4.dp))
        Text("R$ ${"%.2f".format(produto.preco)}", color = AzulNeon, fontWeight = FontWeight.Bold, fontSize = 15.sp)
        Text(produto.categoria, style = MaterialTheme.typography.labelSmall, color = DouradoDiscreto)
    }
}

@Composable
fun ModoAplicativoScreen(
    estado: EstadoBeta,
    ultimaResposta: String,
    historico: List<Pair<Boolean, String>>,
    mostrarCamera: Boolean,
    produtosEmDestaque: List<Produto> = emptyList(),
    visema: Visema = Visema.REST,
    perfil: PerfilDesempenho = PerfilDesempenho.BALANCEADO,
    confirmando: Boolean = false,
    aoTocarMicrofone: () -> Unit,
    aoEnviarTexto: (String) -> Unit,
    aoAlternarCamera: () -> Unit,
    aoAbrirConfiguracoes: () -> Unit,
    aoMudarModo: () -> Unit,
    aoAbrirCatalogo: () -> Unit = {},
    aoAbrirHistorico: () -> Unit = {},
    aoAbrirSobre: () -> Unit = {},
) {
    var textoDigitado by remember { mutableStateOf("") }

    // Layout "app profissional de verdade" pedido: topo (BETA+status+
    // configurações) + menu lateral com rótulos + avatar+conversa+
    // cards+microfone, tudo em painéis arredondados sobre fundo escuro
    // (identidade premium) — não é mais uma tela simples de demonstração.
    Column(modifier = Modifier.fillMaxSize().background(FundoBeta).padding(12.dp)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(SuperficieBeta)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("BETA", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = AzulNeon)
            Text(rotuloDoEstado(estado), style = MaterialTheme.typography.labelMedium, color = DouradoDiscreto)
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = aoMudarModo) { Text("MUDAR MODO") }
                IconButton(onClick = aoAbrirConfiguracoes, modifier = Modifier.semantics { contentDescription = "Configurações" }) {
                    Text("⚙", fontSize = 20.sp)
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        Row(modifier = Modifier.weight(1f).fillMaxWidth()) {
            Column(
                modifier = Modifier
                    .fillMaxHeight()
                    .width(84.dp)
                    .clip(RoundedCornerShape(20.dp))
                    .background(SuperficieBeta)
                    .padding(vertical = 12.dp)
                    .verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                ItemMenu("◉", "Conversar", ativo = true, aoClicar = {})
                ItemMenu("▤", "Catálogo", aoClicar = aoAbrirCatalogo)
                ItemMenu("◷", "Histórico", aoClicar = aoAbrirHistorico)
                ItemMenu("▣", "Câmera", ativo = mostrarCamera, aoClicar = aoAlternarCamera)
                ItemMenu("♿", "Acessibilidade", aoClicar = aoAbrirConfiguracoes)
                ItemMenu("⚙", "Config.", aoClicar = aoAbrirConfiguracoes)
                ItemMenu("ℹ", "Sobre", aoClicar = aoAbrirSobre)
            }

            Spacer(Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f).fillMaxHeight()) {
                // Painel da atendente — permanece visível o tempo todo
                // (item do pedido), avatar em tamanho relevante (não
                // minúsculo), com hierarquia BETA/estado/resposta.
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(20.dp))
                        .background(SuperficieBeta)
                        .padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Box(
                        modifier = Modifier.size(132.dp).clickableSeParado(estado) { aoTocarMicrofone() },
                        contentAlignment = Alignment.Center,
                    ) {
                        BetaAvatar(estado = avatarStateDe(estado, confirmando), visema = visema, perfil = perfil, tamanho = 132)
                    }
                    Text(
                        textoDaAtendente(estado, ultimaResposta, "Olá! Como posso ajudar?"),
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                }

                if (produtosEmDestaque.isNotEmpty()) {
                    Spacer(Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        produtosEmDestaque.forEach { CardProduto(it) }
                    }
                }

                if (mostrarCamera) {
                    Spacer(Modifier.height(12.dp))
                    Box(modifier = Modifier.clip(RoundedCornerShape(16.dp))) { CameraPreview() }
                }

                Spacer(Modifier.height(12.dp))
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(20.dp))
                        .background(SuperficieBeta)
                        .padding(12.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    historico.forEach { (deUsuario, texto) ->
                        Text(
                            text = (if (deUsuario) "Você: " else "BETA: ") + texto,
                            modifier = Modifier.padding(vertical = 4.dp),
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = textoDigitado,
                        onValueChange = { textoDigitado = it },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(16.dp),
                        placeholder = { Text("Escreva ou fale...") },
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(
                        onClick = { if (textoDigitado.isNotBlank()) { aoEnviarTexto(textoDigitado); textoDigitado = "" } },
                        shape = RoundedCornerShape(16.dp),
                    ) { Text("Enviar") }
                }
            }
        }
    }
}

/** Diálogo de PIN de manutenção do Totem (item do pedido: "nunca
 * confiar somente em ocultar botão") — só pede o PIN, nunca mostra
 * nenhum controle administrativo antes de confirmar. `bloqueado`
 * cobre o cooldown depois de várias tentativas erradas (item do
 * pedido: "limitar tentativas"). */
@Composable
fun DialogoPinManutencao(
    erro: Boolean,
    bloqueado: Boolean,
    titulo: String = "ACESSO DE MANUTENÇÃO",
    subtitulo: String = "Digite seu PIN de manutenção.",
    aoConfirmar: (String) -> Unit,
    aoCancelar: () -> Unit,
) {
    var pin by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = aoCancelar,
        title = { Text(titulo) },
        text = {
            Column {
                if (bloqueado) {
                    Text(
                        "Muitas tentativas erradas. Aguarde um pouco antes de tentar de novo.",
                        color = MaterialTheme.colorScheme.error,
                    )
                } else {
                    Text(subtitulo)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = pin,
                        onValueChange = { if (it.length <= 8) pin = it.filter { c -> c.isDigit() } },
                        label = { Text("PIN") },
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword),
                    )
                    if (erro) Text("PIN incorreto. Tente novamente.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            if (!bloqueado) TextButton(onClick = { aoConfirmar(pin) }) { Text("ENTRAR") }
        },
        dismissButton = { TextButton(onClick = aoCancelar) { Text("CANCELAR") } },
    )
}

@Composable
fun ModoTotemScreen(
    estado: EstadoBeta,
    ultimaResposta: String,
    produtosEmDestaque: List<Produto> = emptyList(),
    visema: Visema = Visema.REST,
    perfil: PerfilDesempenho = PerfilDesempenho.BALANCEADO,
    confirmando: Boolean = false,
    aoTocarTela: () -> Unit,
    aoAbrirAjuda: () -> Unit = {},
    aoAbrirManutencao: () -> Unit = {},
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .clickableSeParado(estado) { aoTocarTela() },
        contentAlignment = Alignment.Center,
    ) {
        // Avatar dimensionado PROPORCIONALMENTE à tela (item do
        // pedido: "não usar avatar fixo se isso deixar pequeno em
        // tablets") — ~52% do menor lado, dentro de uma faixa segura
        // pra não estourar em telas muito pequenas nem gigantes.
        val ladoAvatar = (minOf(maxWidth, maxHeight) * 0.52f).coerceIn(180.dp, 520.dp)

        // A atendente é o elemento visual principal do Totem (pedido
        // explícito: "não utilizar somente uma esfera/ponto") — o
        // avatar ocupa uma área grande da tela, como recepção virtual.
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.fillMaxSize().padding(32.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text("BETA", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Bold)
            Text("SISTEMA ALPHA", color = Color.White.copy(alpha = 0.7f), fontSize = 13.sp)
            Spacer(Modifier.height(16.dp))
            Box(
                modifier = Modifier.size(ladoAvatar).clickableSeParado(estado) { aoTocarTela() },
                contentAlignment = Alignment.Center,
            ) {
                BetaAvatar(
                    estado = avatarStateDe(estado, confirmando),
                    visema = visema,
                    perfil = perfil,
                    tamanho = with(LocalDensity.current) { ladoAvatar.roundToPx() },
                )
            }
            Spacer(Modifier.height(24.dp))
            Text(
                textoDaAtendente(estado, ultimaResposta, "Olá! Como posso ajudar você hoje?"),
                color = Color.White,
                fontSize = 26.sp,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(12.dp))
            Text(rotuloDoEstado(estado), color = AzulNeon, fontSize = 16.sp, fontWeight = FontWeight.Bold)

            // Card do produto — só aparece quando o usuário pergunta
            // (item do pedido: "produto só aparece quando o usuário
            // perguntar"), nunca inventado, só o que o catálogo local
            // realmente tem.
            if (produtosEmDestaque.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    produtosEmDestaque.take(3).forEach { p ->
                        Column(
                            modifier = Modifier
                                .width(160.dp)
                                .clip(RoundedCornerShape(14.dp))
                                .background(SuperficieBeta)
                                .padding(12.dp),
                        ) {
                            Text(p.nome, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 14.sp, maxLines = 2)
                            Text("R$ ${"%.2f".format(p.preco)}", color = AzulNeon, fontWeight = FontWeight.Bold)
                            Text(p.categoria, color = DouradoDiscreto, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }

            Spacer(Modifier.height(24.dp))
            Button(
                onClick = aoTocarTela,
                enabled = estado == EstadoBeta.PARADO,
                modifier = Modifier.height(64.dp),
            ) { Text("FALE COM A BETA", fontSize = 18.sp) }
            Spacer(Modifier.height(16.dp))

            // Ao visitante público SÓ isso é mostrado (item do pedido:
            // "nunca mostrar catálogo administrativo/configurações/
            // mudar modo/estoque/edição/desenvolvimento"). O botão de
            // manutenção fica pequeno no canto, sem interferir no
            // atendimento (ver abaixo).
            OutlinedButton(onClick = aoAbrirAjuda, colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.White)) { Text("AJUDA") }
        }

        // Botão discreto de manutenção (item 1 do pedido) — canto
        // inferior, pequeno, texto baixo-contraste, nunca "CONFIGURAÇÕES"
        // como rótulo principal. Tocar aqui NUNCA concede acesso
        // direto — sempre abre o pedido de PIN (ver MainActivity).
        TextButton(
            onClick = aoAbrirManutencao,
            modifier = Modifier.align(Alignment.BottomStart).padding(8.dp),
        ) {
            Text("⚙ MANUTENÇÃO", color = Color.White.copy(alpha = 0.35f), fontSize = 11.sp)
        }

        // Identidade RMD/ALPHA discreta no rodapé (item do pedido:
        // "BETA • SISTEMA ALPHA • RMD, de maneira discreta") — nunca
        // compete visualmente com o avatar/BETA principal.
        Text(
            "BETA • SISTEMA ALPHA • RMD",
            color = DouradoDiscreto,
            fontSize = 12.sp,
            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 12.dp),
        )
    }
}

/** Painel de Modo de Manutenção (item do pedido) — só alcançável a
 * partir do botão discreto + PIN correto no Totem. Nunca aparece
 * sozinho. "VOLTAR AO TOTEM" sempre disponível e sempre funciona sem
 * fechar o app. */
@Composable
fun PainelManutencaoScreen(
    aoIrParaTotem: () -> Unit,
    aoIrParaAplicativo: () -> Unit,
    aoIrParaDiscreto: () -> Unit,
    aoAbrirCatalogoAdministrativo: () -> Unit,
    aoAbrirConfiguracoes: () -> Unit,
    aoAbrirAcessibilidade: () -> Unit,
    aoAbrirDispositivo: () -> Unit,
    aoAbrirSobre: () -> Unit,
    aoAbrirAreaDesenvolvedor: () -> Unit,
    aoVoltarAoTotem: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().background(FundoBeta).padding(20.dp).verticalScroll(rememberScrollState()),
    ) {
        Text("MODO DE MANUTENÇÃO", style = MaterialTheme.typography.headlineSmall, color = AzulNeon, fontWeight = FontWeight.Bold)
        Text("Acesso restrito ao responsável pelo Totem (nível OPERADOR).", style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(20.dp))

        listOf(
            "MODO TOTEM" to aoIrParaTotem,
            "MODO APLICATIVO" to aoIrParaAplicativo,
            "MODO DISCRETO" to aoIrParaDiscreto,
            "CATÁLOGO" to aoAbrirCatalogoAdministrativo,
            "CONFIGURAÇÕES" to aoAbrirConfiguracoes,
            "ACESSIBILIDADE" to aoAbrirAcessibilidade,
            "DISPOSITIVO" to aoAbrirDispositivo,
            "SOBRE" to aoAbrirSobre,
        ).forEach { (rotulo, aoClicar) ->
            OutlinedButton(
                onClick = aoClicar,
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
            ) { Text(rotulo) }
        }

        Spacer(Modifier.height(12.dp))
        // Segundo nível — SEPARADO do operador (item do pedido:
        // "OPERATOR nunca vira DEVELOPER somente com o PIN
        // operacional") — pede um PIN diferente (ver MainActivity).
        TextButton(onClick = aoAbrirAreaDesenvolvedor, modifier = Modifier.fillMaxWidth()) {
            Text("ÁREA DO DESENVOLVEDOR", color = DouradoDiscreto)
        }

        Spacer(Modifier.height(24.dp))
        Button(onClick = aoVoltarAoTotem, modifier = Modifier.fillMaxWidth().height(56.dp)) {
            Text("VOLTAR AO TOTEM", fontSize = 16.sp)
        }

        Spacer(Modifier.height(24.dp))
        Text("BETA • SISTEMA ALPHA • RMD", color = DouradoDiscreto, style = MaterialTheme.typography.labelSmall)
    }
}

/** Guarda de licença (item 24 do pedido) — nunca mostra código
 * técnico pro usuário público, só esta frase, com um jeito de voltar
 * ao seletor de modos autorizados. */
@Composable
fun TelaRecursoIndisponivel(aoVoltar: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().background(FundoBeta).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            "Este recurso não está disponível para esta licença.",
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
        Button(onClick = aoVoltar) { Text("VOLTAR") }
    }
}

/** Diálogo de senha do BETA_OWNER (item do pedido: "autoridade máxima
 * sobre licenciamento... nunca senha hardcoded"). Não existe senha
 * padrão de fábrica — quando `primeiraVez` é true, o valor digitado
 * com sucesso AGORA é o que passa a valer daqui pra frente (bootstrap
 * na primeira utilização, nunca um segredo fixo no código). */
@Composable
fun DialogoSenhaProprietario(
    primeiraVez: Boolean,
    erro: Boolean,
    bloqueado: Boolean,
    aoConfirmar: (String) -> Unit,
    aoCancelar: () -> Unit,
) {
    var senha by remember { mutableStateOf("") }
    var confirmacao by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = aoCancelar,
        title = { Text(if (primeiraVez) "DEFINIR SENHA DO PROPRIETÁRIO" else "ACESSO DO PROPRIETÁRIO") },
        text = {
            Column {
                if (bloqueado) {
                    Text(
                        "Muitas tentativas erradas. Aguarde um pouco antes de tentar de novo.",
                        color = MaterialTheme.colorScheme.error,
                    )
                } else {
                    Text(
                        if (primeiraVez)
                            "Nenhuma senha de proprietário foi definida ainda. Crie uma agora — ela não pode ser recuperada se for esquecida."
                        else
                            "Digite a senha do proprietário para gerenciar a licença deste aparelho.",
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = senha,
                        onValueChange = { senha = it },
                        label = { Text("Senha") },
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                    )
                    if (primeiraVez) {
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = confirmacao,
                            onValueChange = { confirmacao = it },
                            label = { Text("Confirme a senha") },
                            visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                        )
                        if (senha.isNotEmpty() && confirmacao.isNotEmpty() && senha != confirmacao) {
                            Text("As senhas não coincidem.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    if (erro) Text("Senha incorreta. Tente novamente.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            if (!bloqueado) {
                val habilitado = if (primeiraVez) senha.length >= 4 && senha == confirmacao else senha.isNotEmpty()
                TextButton(onClick = { aoConfirmar(senha) }, enabled = habilitado) { Text(if (primeiraVez) "DEFINIR" else "ENTRAR") }
            }
        },
        dismissButton = { TextButton(onClick = aoCancelar) { Text("CANCELAR") } },
    )
}

/** Catálogo ADMINISTRATIVO (item do pedido: "somente dentro de
 * MANUTENÇÃO") — lista completa, só leitura (não existe backend de
 * edição real; ver limitações do relatório), nunca inventa produto. */
@Composable
fun DialogoCatalogoAdministrativo(produtos: List<Produto>, aoFechar: () -> Unit) {
    AlertDialog(
        onDismissRequest = aoFechar,
        title = { Text("Catálogo (administrativo)") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                produtos.forEach { p ->
                    Column(modifier = Modifier.padding(vertical = 6.dp)) {
                        Text(p.nome, fontWeight = FontWeight.Bold)
                        Text("R$ ${"%.2f".format(p.preco)} — ${p.categoria}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = aoFechar) { Text("Fechar") } },
    )
}

/** Informações do aparelho (item do pedido: "DISPOSITIVO") — só dados
 * reais do próprio Android, nunca inventados. */
@Composable
fun DialogoDispositivo(modelo: String, versaoAndroid: String, versaoApp: String, aoFechar: () -> Unit) {
    AlertDialog(
        onDismissRequest = aoFechar,
        title = { Text("Dispositivo") },
        text = {
            Column {
                Text("Modelo: $modelo")
                Text("Android: $versaoAndroid")
                Text("Versão do app: $versaoApp")
            }
        },
        confirmButton = { TextButton(onClick = aoFechar) { Text("Fechar") } },
    )
}

@Composable
fun ConfiguracoesScreen(
    tamanhoFonte: TamanhoFonte,
    altoContraste: Boolean,
    vozes: List<VozOpcao>,
    vozSelecionada: String?,
    possuiVozPtBr: Boolean,
    velocidadeVoz: Float,
    tomVoz: Float,
    perfilDesempenho: PerfilDesempenho,
    pinAdministrativo: String,
    timeoutManutencaoMs: Long,
    aoMudarTamanho: (TamanhoFonte) -> Unit,
    aoMudarContraste: (Boolean) -> Unit,
    aoSelecionarVoz: (String?) -> Unit,
    aoTestarVoz: () -> Unit,
    aoMudarVelocidade: (Float) -> Unit,
    aoMudarTom: (Float) -> Unit,
    aoMudarPerfilDesempenho: (PerfilDesempenho) -> Unit,
    aoMudarPin: (String) -> Unit,
    aoMudarTimeoutManutencao: (Long) -> Unit,
    aoTrocarModo: () -> Unit,
    aoVoltar: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp).verticalScroll(rememberScrollState())) {
        Text("Configurações", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(24.dp))

        Text("Tamanho da fonte")
        Row {
            TamanhoFonte.entries.forEach { tamanho ->
                FilterChip(
                    selected = tamanho == tamanhoFonte,
                    onClick = { aoMudarTamanho(tamanho) },
                    label = { Text(tamanho.name.lowercase()) },
                    modifier = Modifier.padding(end = 8.dp),
                )
            }
        }

        Spacer(Modifier.height(16.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Alto contraste")
            Spacer(Modifier.width(8.dp))
            Switch(checked = altoContraste, onCheckedChange = aoMudarContraste)
        }

        Spacer(Modifier.height(24.dp))
        Text("Voz da BETA (Português do Brasil)")
        if (!possuiVozPtBr) {
            Text(
                "Não encontrei nenhuma voz em português do Brasil instalada neste aparelho. " +
                    "Instale uma voz pt-BR em Configurações do Android > Acessibilidade > Conversão de texto em voz.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        } else if (vozes.isEmpty()) {
            Text("Usando a voz padrão do aparelho (pt-BR).", style = MaterialTheme.typography.bodySmall)
        } else {
            Column(modifier = Modifier.padding(vertical = 8.dp)) {
                // Voz do sistema (padrão do motor TTS) — sempre disponível.
                LinhaVoz(rotulo = "Padrão do sistema", genero = null, selecionada = vozSelecionada == null) {
                    aoSelecionarVoz(null)
                }
                vozes.forEach { voz ->
                    LinhaVoz(rotulo = voz.rotulo, genero = voz.genero, selecionada = voz.nome == vozSelecionada) {
                        aoSelecionarVoz(voz.nome)
                    }
                }
            }
        }
        if (possuiVozPtBr) {
            OutlinedButton(onClick = aoTestarVoz) { Text("Testar voz") }

            Spacer(Modifier.height(16.dp))
            Text("Velocidade da fala")
            Slider(value = velocidadeVoz, onValueChange = aoMudarVelocidade, valueRange = 0.5f..2f)
            Text("Tom da voz")
            Slider(value = tomVoz, onValueChange = aoMudarTom, valueRange = 0.5f..2f)
        }

        Spacer(Modifier.height(24.dp))
        Text("Qualidade da animação da atendente")
        Row {
            listOf(
                PerfilDesempenho.ECO to "eco",
                PerfilDesempenho.BALANCEADO to "balanceado",
                PerfilDesempenho.AVANCADO to "avançado",
            ).forEach { (perfil, rotulo) ->
                FilterChip(
                    selected = perfil == perfilDesempenho,
                    onClick = { aoMudarPerfilDesempenho(perfil) },
                    label = { Text(rotulo) },
                    modifier = Modifier.padding(end = 8.dp),
                )
            }
        }
        Text(
            "Use \"eco\" em aparelhos mais fracos para reduzir animação.",
            style = MaterialTheme.typography.bodySmall,
        )

        Spacer(Modifier.height(24.dp))
        Text("PIN de manutenção do Totem")
        var pinDigitado by remember(pinAdministrativo) { mutableStateOf(pinAdministrativo) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = pinDigitado,
                onValueChange = { if (it.length <= 8) pinDigitado = it.filter { c -> c.isDigit() } },
                modifier = Modifier.width(120.dp),
                visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword),
            )
            Spacer(Modifier.width(8.dp))
            TextButton(onClick = { if (pinDigitado.isNotBlank()) aoMudarPin(pinDigitado) }) { Text("Salvar") }
        }
        Text(
            "Usado para entrar no Modo de Manutenção pelo botão discreto do Totem.",
            style = MaterialTheme.typography.bodySmall,
        )

        Spacer(Modifier.height(16.dp))
        Text("Timeout do Modo de Manutenção")
        Row {
            listOf(30_000L to "30s", 60_000L to "60s", 120_000L to "2 min").forEach { (ms, rotulo) ->
                FilterChip(
                    selected = timeoutManutencaoMs == ms,
                    onClick = { aoMudarTimeoutManutencao(ms) },
                    label = { Text(rotulo) },
                    modifier = Modifier.padding(end = 8.dp),
                )
            }
        }

        Spacer(Modifier.height(32.dp))
        Button(onClick = aoTrocarModo) { Text("Trocar modo de uso") }
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = aoVoltar) { Text("Voltar") }
    }
}

@Composable
private fun LinhaVoz(rotulo: String, genero: String?, selecionada: Boolean, aoSelecionar: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable(onClick = aoSelecionar).padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selecionada, onClick = aoSelecionar)
        Spacer(Modifier.width(4.dp))
        Column {
            Text(rotulo)
            if (genero != null) Text(genero, style = MaterialTheme.typography.labelSmall)
        }
    }
}

fun listaProdutosLegivel(produtos: List<Produto>): String =
    produtos.joinToString("\n") { "${it.nome} — R$ ${"%.2f".format(it.preco)} (${it.categoria})" }

/** Diálogo "Sobre" do menu do Modo Aplicativo (item do pedido) —
 * hierarquia de identidade: BETA (programa) / SISTEMA ALPHA (projeto)
 * / RMD (empresa). */
@Composable
fun DialogoSobre(aoFechar: () -> Unit) {
    AlertDialog(
        onDismissRequest = aoFechar,
        title = { Text("Sobre a BETA") },
        text = {
            Column {
                Text("BETA", fontWeight = FontWeight.Bold, fontSize = 20.sp, color = AzulNeon)
                Text("Assistente virtual", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
                Text("Projeto: SISTEMA ALPHA")
                Text("Desenvolvido por: RMD")
                Spacer(Modifier.height(8.dp))
                Text(
                    "Desenvolvido pela RMD para transformar informação em inteligência.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        },
        confirmButton = { TextButton(onClick = aoFechar) { Text("Fechar") } },
    )
}

/** Diálogo "Histórico" do menu do Modo Aplicativo (item do pedido) —
 * mostra a conversa inteira da sessão atual (nunca persiste em disco
 * nem envia a lugar nenhum). */
@Composable
fun DialogoHistorico(historico: List<Pair<Boolean, String>>, aoFechar: () -> Unit) {
    AlertDialog(
        onDismissRequest = aoFechar,
        title = { Text("Histórico da conversa") },
        text = {
            if (historico.isEmpty()) {
                Text("Ainda não há nenhuma conversa nesta sessão.")
            } else {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    historico.forEach { (deUsuario, texto) ->
                        Text(
                            (if (deUsuario) "Você: " else "BETA: ") + texto,
                            modifier = Modifier.padding(vertical = 4.dp),
                        )
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = aoFechar) { Text("Fechar") } },
    )
}
