package com.beta.mobile.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import com.beta.mobile.TamanhoFonte

/**
 * Identidade visual BETA — moderna/tecnológica/premium: fundo escuro,
 * azul-neon como cor principal, dourado como detalhe discreto (ver
 * pedido de identidade de abertura). Esta é a base do app inteiro,
 * não só da Splash — "alto contraste" (configurações de
 * acessibilidade) intensifica ainda mais o contraste em cima desta
 * mesma base, nunca troca pra um tema claro incoerente com a
 * identidade.
 */
val AzulNeon = Color(0xFF22D3EE)
val DouradoDiscreto = Color(0xFFD4AF37)
val FundoBeta = Color(0xFF0A0E17)
val SuperficieBeta = Color(0xFF0F1B2E)

private val CoresBeta = darkColorScheme(
    primary = AzulNeon,
    secondary = DouradoDiscreto,
    background = FundoBeta,
    surface = SuperficieBeta,
    onBackground = Color(0xFFE5E7EB),
    onSurface = Color(0xFFE5E7EB),
)

private val CoresAltoContraste = darkColorScheme(
    primary = AzulNeon,
    secondary = DouradoDiscreto,
    background = Color.Black,
    surface = Color.Black,
    onBackground = Color.White,
    onSurface = Color.White,
)

fun escalaFonte(tamanho: TamanhoFonte): Float = when (tamanho) {
    TamanhoFonte.PEQUENA -> 0.85f
    TamanhoFonte.MEDIA -> 1.0f
    TamanhoFonte.GRANDE -> 1.4f
}

@Composable
fun BetaTheme(altoContraste: Boolean, escala: Float, conteudo: @Composable () -> Unit) {
    val esquemaCores = if (altoContraste) CoresAltoContraste else CoresBeta

    val base = Typography()
    val tipografiaEscalada = base.copy(
        bodyLarge = base.bodyLarge.comEscala(escala),
        bodyMedium = base.bodyMedium.comEscala(escala),
        titleLarge = base.titleLarge.comEscala(escala),
        headlineMedium = base.headlineMedium.comEscala(escala),
        headlineLarge = base.headlineLarge.comEscala(escala),
    )

    MaterialTheme(colorScheme = esquemaCores, typography = tipografiaEscalada, content = conteudo)
}

private fun TextStyle.comEscala(escala: Float): TextStyle =
    copy(fontSize = fontSize * escala)
