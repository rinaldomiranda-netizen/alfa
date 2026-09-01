package com.beta.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.beta.mobile.licensing.EstadoModulo
import com.beta.mobile.licensing.Licenca
import com.beta.mobile.licensing.Modulo
import com.beta.mobile.licensing.Nivel
import com.beta.mobile.licensing.ResultadoAtivacao
import com.beta.mobile.licensing.SolicitacaoAtivacao
import java.time.Instant
import java.time.format.DateTimeParseException

/**
 * BETA CONTROL — casca visual profissional do painel de
 * proprietário/desenvolvedor (item do pedido: "não criar uma tela
 * simples de configurações... deve parecer um aplicativo profissional
 * de administração"). Reaproveita EXATAMENTE a mesma lógica de
 * licenciamento/autenticação já existente e testada nesta sessão —
 * isto é só a apresentação, nunca um "cérebro" novo.
 *
 * Escopo por nível (item "26. ADMINISTRAÇÃO" do pedido):
 * BETA_DEVELOPER vê tudo em modo LEITURA (diagnóstico, integrações,
 * BETA-CLOUD, atualizações, segurança, auditoria); só BETA_OWNER pode
 * mexer na licença (ativar/importar/revogar) e gerar pedidos de
 * ativação — o mesmo grau de separação de autoridade já usado no
 * resto do app (PIN operador ≠ PIN desenvolvedor ≠ senha proprietário).
 *
 * Seções pedidas que NÃO existem aqui (Clientes, Dispositivos em
 * frota, Licenças em frota, Solicitações de outros aparelhos, Skills,
 * BETA Portátil, frota de Mobile/Totem, ambientes de demo por
 * segmento, MFA, central de notificações, relatórios, identidade de
 * empresa) dependem de um backend multiempresa real no BETA-CLOUD que
 * não existe nesta instalação (fora do escopo autorizado desta
 * sessão) — nunca fabricadas aqui com dado de mentira; ver
 * limitações do relatório e docs/LICENSING.md.
 */
enum class SecaoControle(val rotulo: String, val icone: String) {
    DASHBOARD("Dashboard", "◧"),
    DISPOSITIVO("Dispositivo", "▣"),
    LICENCA("Licença", "◆"),
    MODULOS("Módulos", "▦"),
    SOLICITACAO("Solicitação", "✎"),
    SEGURANCA("Segurança", "◈"),
    AUDITORIA("Auditoria", "≡"),
    INTEGRACOES("Integrações", "⇄"),
    BETA_CLOUD("BETA-CLOUD", "☁"),
    ATUALIZACOES("Atualizações", "↑"),
    SOBRE("Sobre", "ℹ"),
}

/** Um evento administrativo local (item do pedido: "AUDITORIA...
 * nunca mostrar senha/token/CVV/segredo"). As strings de `acao` e
 * `resultado` são exatamente as mesmas já usadas nos `Log.i/w` desse
 * app — nunca incluem PIN, senha, assinatura ou conteúdo de licença. */
data class RegistroAuditoria(
    val quando: String,
    val acao: String,
    val resultado: String,
)

private val SuperficieCartao = Color(0xFF13233B)
private val BordaCartao = Color(0xFF223755)

@Composable
private fun BadgeAmbiente(emModoDemo: Boolean) {
    val cor = if (emModoDemo) DouradoDiscreto else AzulNeon
    Surface(color = cor.copy(alpha = 0.16f), shape = RoundedCornerShape(20.dp)) {
        Text(
            if (emModoDemo) "AMBIENTE: DEMO" else "AMBIENTE: LICENCIADO",
            color = cor,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
        )
    }
}

@Composable
fun CartaoControle(titulo: String, modifier: Modifier = Modifier, conteudo: @Composable ColumnScope.() -> Unit) {
    Surface(
        color = SuperficieCartao,
        shape = RoundedCornerShape(18.dp),
        modifier = modifier.fillMaxWidth(),
        shadowElevation = 3.dp,
        border = BorderStroke(1.dp, BordaCartao),
    ) {
        Column(Modifier.padding(18.dp)) {
            Text(titulo, style = MaterialTheme.typography.titleMedium, color = DouradoDiscreto, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(10.dp))
            conteudo()
        }
    }
}

@Composable
private fun CartaoIndicador(rotulo: String, valor: String, destaque: Color = AzulNeon, modifier: Modifier = Modifier) {
    Surface(
        color = SuperficieCartao,
        shape = RoundedCornerShape(16.dp),
        modifier = modifier,
        border = BorderStroke(1.dp, BordaCartao),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(rotulo, style = MaterialTheme.typography.labelMedium, color = Color(0xFF9CA9C0))
            Spacer(Modifier.height(6.dp))
            Text(valor, style = MaterialTheme.typography.titleLarge, color = destaque, fontWeight = FontWeight.Bold)
        }
    }
}

private fun diasParaExpirar(licenca: Licenca?): Long? {
    val expiraTexto = licenca?.expiresAt ?: return null
    return try {
        val instante = Instant.parse(expiraTexto)
        (instante.epochSecond - Instant.now().epochSecond) / 86_400
    } catch (e: DateTimeParseException) {
        null
    }
}

/** Casca profissional (item do pedido: sidebar/topbar/cards, nunca
 * uma tela genérica de configurações). Responsivo por largura real —
 * item "32. DESIGN RESPONSIVO": >=700dp usa trilha lateral com
 * rótulo (tablet grande/desktop), 460–700dp usa trilha só com ícone,
 * abaixo disso vira uma barra de chips no topo (celular). Só foi
 * testado de verdade na largura do Vaio TL10 (tablet); as outras
 * faixas foram verificadas por lógica/BoxWithConstraints, não em um
 * celular físico real — ver limitações do relatório. */
@Composable
fun PainelBetaControlScreen(
    nivel: Nivel,
    deviceId: String,
    plataforma: String,
    modelo: String,
    versaoAndroid: String,
    versaoApp: String,
    possuiInternet: Boolean,
    emModoDemo: Boolean,
    modulosAtivos: Set<Modulo>,
    estadoModulo: (Modulo) -> EstadoModulo,
    licenca: Licenca?,
    resultadoAtivacao: ResultadoAtivacao?,
    auditoria: List<RegistroAuditoria>,
    aoAtivar: (String) -> Unit,
    aoImportarArquivo: () -> Unit,
    aoRevogar: () -> Unit,
    aoAbrirConfiguracoes: () -> Unit,
    aoAbrirAreaProprietario: (() -> Unit)?,
    aoVoltar: () -> Unit,
) {
    var secaoAtual by remember { mutableStateOf(SecaoControle.DASHBOARD) }
    val ehProprietario = nivel == Nivel.BETA_OWNER

    BoxWithConstraints(modifier = Modifier.fillMaxSize().background(FundoBeta)) {
        val trilhaCompleta = maxWidth >= 700.dp
        val trilhaIcones = !trilhaCompleta && maxWidth >= 460.dp
        val barraSuperior = !trilhaCompleta && !trilhaIcones

        Column(Modifier.fillMaxSize()) {
            // Topbar (item do pedido)
            Column(Modifier.fillMaxWidth().padding(20.dp, 18.dp, 20.dp, 10.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Column {
                        Text("BETA CONTROL", style = MaterialTheme.typography.headlineSmall, color = AzulNeon, fontWeight = FontWeight.Bold)
                        Text(
                            if (ehProprietario) "Painel do Proprietário" else "Painel do Desenvolvedor",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFB6C2D9),
                        )
                    }
                    BadgeAmbiente(emModoDemo)
                }
                Spacer(Modifier.height(4.dp))
                Text("BETA · SISTEMA ALPHA · RMD", style = MaterialTheme.typography.labelSmall, color = DouradoDiscreto)
            }

            if (barraSuperior) {
                BarraDeSecoesCompacta(nivel, secaoAtual) { secaoAtual = it }
            }

            Row(Modifier.weight(1f).fillMaxWidth()) {
                if (trilhaCompleta || trilhaIcones) {
                    TrilhaLateral(nivel, secaoAtual, trilhaCompleta) { secaoAtual = it }
                }

                Column(
                    Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()).padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    when (secaoAtual) {
                        SecaoControle.DASHBOARD -> SecaoDashboard(deviceId, plataforma, possuiInternet, emModoDemo, modulosAtivos, licenca, auditoria)
                        SecaoControle.DISPOSITIVO -> SecaoDispositivo(deviceId, plataforma, modelo, versaoAndroid, versaoApp)
                        SecaoControle.LICENCA -> SecaoLicenca(licenca, resultadoAtivacao, ehProprietario, aoAtivar, aoImportarArquivo, aoRevogar)
                        SecaoControle.MODULOS -> SecaoModulos(modulosAtivos, estadoModulo)
                        SecaoControle.SOLICITACAO -> SecaoSolicitacao(deviceId, plataforma, ehProprietario)
                        SecaoControle.SEGURANCA -> SecaoSeguranca(auditoria)
                        SecaoControle.AUDITORIA -> SecaoAuditoria(auditoria)
                        SecaoControle.INTEGRACOES -> SecaoIntegracoes()
                        SecaoControle.BETA_CLOUD -> SecaoBetaCloud()
                        SecaoControle.ATUALIZACOES -> SecaoAtualizacoes(versaoApp)
                        SecaoControle.SOBRE -> SecaoSobre(modelo, versaoAndroid, versaoApp, aoAbrirConfiguracoes)
                    }

                    if (!ehProprietario && aoAbrirAreaProprietario != null) {
                        OutlinedButton(onClick = aoAbrirAreaProprietario, modifier = Modifier.fillMaxWidth()) {
                            Text("ÁREA DO PROPRIETÁRIO")
                        }
                    }
                    Button(onClick = aoVoltar, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("VOLTAR") }
                    Spacer(Modifier.height(8.dp))
                }
            }
        }
    }
}

private fun secoesParaNivel(nivel: Nivel): List<SecaoControle> {
    val base = listOf(
        SecaoControle.DASHBOARD, SecaoControle.DISPOSITIVO, SecaoControle.LICENCA, SecaoControle.MODULOS,
    )
    val exclusivoProprietario = if (nivel == Nivel.BETA_OWNER) listOf(SecaoControle.SOLICITACAO) else emptyList()
    val resto = listOf(
        SecaoControle.SEGURANCA, SecaoControle.AUDITORIA, SecaoControle.INTEGRACOES,
        SecaoControle.BETA_CLOUD, SecaoControle.ATUALIZACOES, SecaoControle.SOBRE,
    )
    return base + exclusivoProprietario + resto
}

@Composable
private fun TrilhaLateral(nivel: Nivel, secaoAtual: SecaoControle, comRotulo: Boolean, aoSelecionar: (SecaoControle) -> Unit) {
    Column(
        Modifier.fillMaxHeight().width(if (comRotulo) 190.dp else 72.dp).background(SuperficieBeta).padding(vertical = 12.dp),
    ) {
        secoesParaNivel(nivel).forEach { secao ->
            val selecionado = secao == secaoAtual
            Surface(
                color = if (selecionado) AzulNeon.copy(alpha = 0.16f) else Color.Transparent,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 3.dp),
                shape = RoundedCornerShape(12.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().clickable { aoSelecionar(secao) }.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(secao.icone, color = if (selecionado) AzulNeon else Color(0xFF9CA9C0), style = MaterialTheme.typography.titleMedium)
                    if (comRotulo) {
                        Spacer(Modifier.width(10.dp))
                        Text(
                            secao.rotulo,
                            color = if (selecionado) AzulNeon else Color(0xFFCBD5E1),
                            fontWeight = if (selecionado) FontWeight.Bold else FontWeight.Normal,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun BarraDeSecoesCompacta(nivel: Nivel, secaoAtual: SecaoControle, aoSelecionar: (SecaoControle) -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        secoesParaNivel(nivel).forEach { secao ->
            val selecionado = secao == secaoAtual
            FilterChip(
                selected = selecionado,
                onClick = { aoSelecionar(secao) },
                label = { Text(secao.rotulo) },
                leadingIcon = { Text(secao.icone) },
            )
        }
    }
}

@Composable
private fun SecaoDashboard(
    deviceId: String,
    plataforma: String,
    possuiInternet: Boolean,
    emModoDemo: Boolean,
    modulosAtivos: Set<Modulo>,
    licenca: Licenca?,
    auditoria: List<RegistroAuditoria>,
) {
    val diasExpira = diasParaExpirar(licenca)
    val tentativasIncorretasRecentes = auditoria.takeLast(20).count { "incorreta" in it.resultado }

    FlowLinhas {
        CartaoIndicador("Este dispositivo", deviceId.take(8) + "…", modifier = Modifier.weight(1f))
        CartaoIndicador("Licença", if (emModoDemo) "DEMO" else "Ativa", destaque = if (emModoDemo) DouradoDiscreto else AzulNeon, modifier = Modifier.weight(1f))
        CartaoIndicador("Módulos ativos", "${modulosAtivos.size} de ${Modulo.values().size}", modifier = Modifier.weight(1f))
    }
    FlowLinhas {
        CartaoIndicador("Conectividade", if (possuiInternet) "Online" else "Offline", destaque = if (possuiInternet) AzulNeon else Color(0xFFF59E0B), modifier = Modifier.weight(1f))
        CartaoIndicador("Tentativas incorretas recentes", "$tentativasIncorretasRecentes", destaque = if (tentativasIncorretasRecentes > 0) Color(0xFFEF4444) else AzulNeon, modifier = Modifier.weight(1f))
        CartaoIndicador("Plataforma", plataforma.take(14), modifier = Modifier.weight(1f))
    }
    CartaoControle("Alertas") {
        if (diasExpira != null && diasExpira in 0..30) {
            Text("A licença expira em $diasExpira dia(s).", color = Color(0xFFF59E0B), fontWeight = FontWeight.Bold)
        } else if (diasExpira != null && diasExpira < 0) {
            Text("A licença já expirou.", color = Color(0xFFEF4444), fontWeight = FontWeight.Bold)
        } else {
            Text("Nenhum alerta de segurança no momento.", color = Color(0xFF9CA9C0))
        }
    }
}

/** Substituto simples de um "grid" (item do pedido: cards) sem trazer
 * uma dependência de layout nova — uma Row que já quebra bem em
 * telas largas; em telas estreitas os cards só ficam mais altos
 * (Column dentro de Row com weight ainda empilha o conteúdo). */
@Composable
private fun FlowLinhas(conteudo: @Composable RowScope.() -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), content = conteudo)
}

@Composable
private fun SecaoDispositivo(deviceId: String, plataforma: String, modelo: String, versaoAndroid: String, versaoApp: String) {
    CartaoControle("Identidade do aparelho") {
        Text("device_id: $deviceId", style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
        Text("Plataforma: $plataforma")
        Text("Modelo: $modelo")
        Text("Android: $versaoAndroid")
        Text("Versão do app: $versaoApp")
    }
}

@Composable
private fun SecaoLicenca(
    licenca: Licenca?,
    resultadoAtivacao: ResultadoAtivacao?,
    ehProprietario: Boolean,
    aoAtivar: (String) -> Unit,
    aoImportarArquivo: () -> Unit,
    aoRevogar: () -> Unit,
) {
    var conteudoLicenca by remember { mutableStateOf("") }
    CartaoControle("Status da licença") {
        if (licenca != null) {
            Text("Licença ativa — edição ${licenca.edition}", fontWeight = FontWeight.Bold, color = AzulNeon)
            Text("Cliente: ${licenca.customerId}" + if (licenca.organizationId.isNotBlank()) " · Organização: ${licenca.organizationId}" else "")
            Text("Validade: " + (licenca.expiresAt ?: "sem expiração definida"))
            Text("Módulos: " + licenca.modules.joinToString(", ") { it.name })
        } else {
            Text("Modo DEMO — nenhuma licença local ativada neste aparelho.", fontWeight = FontWeight.Bold, color = DouradoDiscreto)
        }
    }
    if (ehProprietario) {
        CartaoControle("Ativar licença local") {
            Text(
                "Importe o arquivo .beta-license emitido pelo proprietário, ou cole o conteúdo abaixo.",
                style = MaterialTheme.typography.bodySmall,
            )
            OutlinedButton(onClick = aoImportarArquivo) { Text("IMPORTAR ARQUIVO .beta-license") }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = conteudoLicenca,
                onValueChange = { conteudoLicenca = it },
                modifier = Modifier.fillMaxWidth().height(120.dp),
                label = { Text("Ou cole o conteúdo da licença aqui") },
            )
            Button(onClick = { aoAtivar(conteudoLicenca) }, enabled = conteudoLicenca.isNotBlank()) { Text("ATIVAR") }
            when (resultadoAtivacao) {
                is ResultadoAtivacao.Sucesso -> Text("Licença ativada com sucesso.", color = AzulNeon)
                ResultadoAtivacao.AssinaturaInvalida -> Text("Assinatura inválida — arquivo não emitido pelo proprietário real ou alterado.", color = Color(0xFFEF4444))
                ResultadoAtivacao.DispositivoNaoCorresponde -> Text("Licença emitida para outro aparelho (device_id não confere).", color = Color(0xFFEF4444))
                ResultadoAtivacao.Expirada -> Text("Esta licença já está expirada.", color = Color(0xFFEF4444))
                ResultadoAtivacao.ArquivoInvalido -> Text("Arquivo de licença inválido ou incompleto.", color = Color(0xFFEF4444))
                null -> {}
            }
        }
        CartaoControle("Ações destrutivas") {
            Text("REVOGAR remove a licença local e volta ao modo DEMO — não apaga nenhum outro dado.", style = MaterialTheme.typography.bodySmall)
            var pedindoConfirmacao by remember { mutableStateOf(false) }
            if (pedindoConfirmacao) {
                Text("Tem certeza? Toque de novo para confirmar.", color = Color(0xFFF59E0B))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { aoRevogar(); pedindoConfirmacao = false }, enabled = licenca != null) { Text("CONFIRMAR REVOGAÇÃO") }
                    OutlinedButton(onClick = { pedindoConfirmacao = false }) { Text("CANCELAR") }
                }
            } else {
                OutlinedButton(onClick = { pedindoConfirmacao = true }, enabled = licenca != null) { Text("REVOGAR LICENÇA LOCAL") }
            }
        }
    } else {
        CartaoControle("Alteração de licença") {
            Text("Somente o proprietário pode ativar, importar ou revogar a licença deste aparelho.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun SecaoModulos(modulosAtivos: Set<Modulo>, estadoModulo: (Modulo) -> EstadoModulo) {
    CartaoControle("Módulos deste aparelho") {
        Text("Ativos hoje: ${modulosAtivos.size} de ${Modulo.values().size}.", style = MaterialTheme.typography.bodySmall)
    }
    Modulo.values().toList().chunked(2).forEach { par ->
        FlowLinhas {
            par.forEach { modulo ->
                val estado = estadoModulo(modulo)
                val cor = when (estado) {
                    EstadoModulo.ATIVO -> AzulNeon
                    EstadoModulo.TRIAL -> Color(0xFF60A5FA)
                    EstadoModulo.BONUS -> DouradoDiscreto
                    EstadoModulo.EXPIRADO -> Color(0xFFF59E0B)
                    EstadoModulo.BLOQUEADO -> Color(0xFFEF4444)
                    EstadoModulo.INATIVO -> Color(0xFF6B7A94)
                }
                CartaoIndicador(modulo.name, estado.name, destaque = cor, modifier = Modifier.weight(1f))
            }
            if (par.size == 1) Spacer(Modifier.weight(1f))
        }
    }
}

@Composable
private fun SecaoSolicitacao(deviceId: String, plataforma: String, ehProprietario: Boolean) {
    if (!ehProprietario) {
        CartaoControle("Solicitação de ativação") { Text("Somente o proprietário gera pedidos de ativação.", style = MaterialTheme.typography.bodySmall) }
        return
    }
    var modulosMarcados by remember { mutableStateOf(setOf<Modulo>()) }
    var pedidoGerado by remember { mutableStateOf<SolicitacaoAtivacao?>(null) }
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current

    CartaoControle("Selecionar módulos") {
        Text(
            "Marque os módulos que este aparelho deve ter — sem código manual de ativação.",
            style = MaterialTheme.typography.bodySmall,
        )
        Modulo.values().forEach { modulo ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = modulo in modulosMarcados, onCheckedChange = { marcado ->
                    modulosMarcados = if (marcado) modulosMarcados + modulo else modulosMarcados - modulo
                })
                Text(modulo.name)
            }
        }
        Button(
            onClick = { pedidoGerado = SolicitacaoAtivacao(deviceId, plataforma, modulosMarcados) },
            enabled = modulosMarcados.isNotEmpty(),
        ) { Text("GERAR PEDIDO DE ATIVAÇÃO") }
        pedidoGerado?.let { pedido ->
            Spacer(Modifier.height(8.dp))
            Text("Comando para a máquina segura do proprietário:", style = MaterialTheme.typography.bodySmall)
            Text(
                pedido.paraComandoCli("PREENCHER_CLIENTE", "PREENCHER_ORGANIZACAO"),
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
            )
            OutlinedButton(onClick = {
                clipboard.setText(androidx.compose.ui.text.AnnotatedString(pedido.paraComandoCli("PREENCHER_CLIENTE", "PREENCHER_ORGANIZACAO")))
            }) { Text("COPIAR COMANDO") }
        }
    }
}

@Composable
private fun SecaoSeguranca(auditoria: List<RegistroAuditoria>) {
    CartaoControle("Modelo de autenticação") {
        Text("PIN de manutenção (operador) e PIN de desenvolvedor: comparados em memória, nunca gravados em log.")
        Text("Senha do proprietário: PBKDF2-HMAC-SHA256 (120 mil iterações) + sal aleatório — nunca texto puro, nunca hardcoded.")
        Text("Licença local: assinatura RSA-2048/SHA-256 — a chave privada nunca existe neste aparelho.")
    }
    CartaoControle("Tentativas recentes") {
        val incorretas = auditoria.takeLast(30).count { "incorreta" in it.resultado }
        Text(
            if (incorretas == 0) "SEGURO — nenhuma tentativa incorreta recente." else "ATENÇÃO — $incorretas tentativa(s) incorreta(s) recentes.",
            color = if (incorretas == 0) AzulNeon else Color(0xFFF59E0B),
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun SecaoAuditoria(auditoria: List<RegistroAuditoria>) {
    CartaoControle("Auditoria local (últimos eventos)") {
        Text("Nunca mostra senha, PIN, token ou conteúdo de licença — só a ação e o resultado.", style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(8.dp))
        if (auditoria.isEmpty()) {
            Text("Nenhum evento registrado ainda nesta sessão do app.")
        } else {
            auditoria.takeLast(50).reversed().forEach { registro ->
                Text("${registro.quando} · ${registro.acao} · ${registro.resultado}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun SecaoIntegracoes() {
    CartaoControle("Integrações de sistema comercial") {
        Text("Nenhuma integração (API/UI Automation/OCR) conectada nesta instalação.")
    }
    CartaoControle("Escopo permitido para qualquer integração futura") {
        Text("✓ Produtos   ✓ Estoque   ✓ Preço   ✓ Venda", color = AzulNeon)
        Text("🔒 Financeiro   🔒 Banco   🔒 RH   🔒 Credenciais", color = Color(0xFFEF4444))
        Text(
            "Este escopo já é reforçado em tempo real pelo bloqueio de assuntos sensíveis do catálogo conversacional (EscopoPermissoes) — nunca é só documentação.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun SecaoBetaCloud() {
    CartaoControle("BETA-CLOUD") {
        Text("Status: NÃO CONFIGURADO", color = DouradoDiscreto, fontWeight = FontWeight.Bold)
        Text("Projeto: não configurado nesta instalação.")
        Text("Última sincronização: nunca.")
        Text("Fila pendente: 0.")
        Text(
            "Ativação/revogação remota dependem de tabelas novas no BETA-CLOUD real, fora do escopo autorizado desta sessão.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun SecaoAtualizacoes(versaoApp: String) {
    CartaoControle("Atualizações") {
        Text("Versão atual: $versaoApp")
        Text("Versão disponível: desconhecida — nenhum mecanismo de verificação remota implementado.")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {}, enabled = false) { Text("VERIFICAR") }
            OutlinedButton(onClick = {}, enabled = false) { Text("ATUALIZAR") }
        }
        Text("Desabilitado de propósito — nunca finge checar atualização sem um mecanismo real por trás.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun SecaoSobre(modelo: String, versaoAndroid: String, versaoApp: String, aoAbrirConfiguracoes: () -> Unit) {
    CartaoControle("Identidade") {
        Text("BETA (programa) · SISTEMA ALPHA (projeto) · RMD (empresa).")
    }
    CartaoControle("Diagnóstico") {
        Text("Modelo: $modelo")
        Text("Android: $versaoAndroid")
        Text("Versão do app: $versaoApp")
    }
    CartaoControle("Configurações de voz, avatar e acessibilidade") {
        Text("Continuam num painel próprio — ver Configurações.", style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = aoAbrirConfiguracoes) { Text("ABRIR CONFIGURAÇÕES") }
    }
}
