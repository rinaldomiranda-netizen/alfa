package com.beta.mobile.avatar

import androidx.compose.ui.geometry.Offset
import kotlin.math.PI
import kotlin.math.sin

/**
 * Parâmetros de cada visema — bem mais simples que definir célula por
 * célula da malha (técnica anterior): cada visema só diz "quão aberta
 * verticalmente" (negativo = pressionada/fechada) e "quão larga ou
 * arredondada horizontalmente" a boca fica. A malha é então gerada
 * PROCEDURALMENTE (`FormasVisema.gerarMalha`) com uma curva suave
 * (seno) que cresce do canto pro centro — o que dá um contorno curvo
 * de verdade, não um retângulo esticado, e escala pra qualquer
 * resolução de malha sem precisar reescrever nada por visema.
 */
private data class ParametrosVisema(val aberturaVertical: Float, val larguraHorizontal: Float)

object FormasVisema {
    // Resolução da malha da boca — maior que a versão anterior (4x4
    // células = 25 vértices em vez de 16) pra dar um contorno mais
    // curvo/suave por visema.
    const val LINHAS = 4
    const val COLUNAS = 4

    private val parametros: Map<Visema, ParametrosVisema> = mapOf(
        Visema.REST to ParametrosVisema(0f, 0f),
        Visema.MBP to ParametrosVisema(-0.55f, 0.10f),
        Visema.A to ParametrosVisema(1.00f, 0.10f),
        Visema.E to ParametrosVisema(0.40f, 0.90f),
        Visema.I to ParametrosVisema(0.25f, 0.60f),
        Visema.O to ParametrosVisema(0.55f, -0.70f),
        Visema.U to ParametrosVisema(0.35f, -0.90f),
        Visema.FV to ParametrosVisema(-0.20f, 0.20f),
        Visema.L to ParametrosVisema(0.50f, 0.00f),
        Visema.SZ to ParametrosVisema(0.30f, 0.30f),
        Visema.CHJ to ParametrosVisema(0.45f, -0.40f),
        Visema.KG to ParametrosVisema(0.60f, 0.00f),
        Visema.TH to ParametrosVisema(0.35f, 0.00f),
    )

    /** Malha (linhas+1)x(colunas+1) de deslocamentos fracionários,
     * gerada com uma curva suave: zero nas bordas (topo/base/lados —
     * âncora contra o resto do rosto), máxima no centro. */
    fun malha(visema: Visema, linhas: Int, colunas: Int): List<Offset> {
        val p = parametros[visema] ?: parametros.getValue(Visema.REST)
        return (0..linhas).flatMap { linha ->
            val fy = linha.toFloat() / linhas
            val bulge = sin((fy * PI).toFloat())
            val direcaoVertical = if (fy < 0.5f) -1f else 1f
            (0..colunas).map { coluna ->
                val fx = coluna.toFloat() / colunas
                val lateral = (fx - 0.5f) * 2f
                val dy = direcaoVertical * bulge * p.aberturaVertical * 0.16f
                val dx = lateral * bulge * p.larguraHorizontal * 0.10f
                Offset(dx, dy)
            }
        }
    }

    /** Interpolação linear entre duas malhas (transição suave entre
     * visemas, ver pedido "transições suaves"). */
    fun interpolar(de: List<Offset>, para: List<Offset>, progresso: Float): List<Offset> =
        de.indices.map { i ->
            Offset(
                de[i].x + (para[i].x - de[i].x) * progresso,
                de[i].y + (para[i].y - de[i].y) * progresso,
            )
        }
}
