package com.beta.mobile.avatar

import android.graphics.BitmapFactory
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import com.beta.mobile.R
import kotlin.math.roundToInt

private val AzulNeon = Color(0xFF22D3EE)
private val DouradoDiscreto = Color(0xFFD4AF37)
private val CorErro = Color(0xFFF59E0B)

// Caixas delimitadoras dos olhos/boca em FRAÇÃO da imagem
// beta_avatar_base.png (calibradas visualmente sobre essa imagem
// específica). Se a imagem base for trocada por outra com
// enquadramento diferente, precisam ser recalibradas.
private val OLHO_ESQUERDO = RetanguloFracionario(0.392f, 0.218f, 0.475f, 0.245f)
private val OLHO_DIREITO = RetanguloFracionario(0.542f, 0.218f, 0.625f, 0.245f)
private val SOBRANCELHA_ESQUERDA = RetanguloFracionario(0.385f, 0.185f, 0.480f, 0.208f)
private val SOBRANCELHA_DIREITA = RetanguloFracionario(0.537f, 0.185f, 0.632f, 0.208f)
private val BOCA = RetanguloFracionario(0.425f, 0.329f, 0.575f, 0.382f)

private data class RetanguloFracionario(val x0: Float, val y0: Float, val x1: Float, val y1: Float)

/** Desenho VETORIAL — rede de segurança se a imagem real não puder
 * ser decodificada em tempo de execução. Não é mais o caminho
 * principal desde que `beta_avatar_base.png` foi fornecida. */
@Composable
fun AvatarRendererVetorial(estado: AvatarState, anim: AvatarAnimacao, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val raio = (size.minDimension / 2) * anim.respiracao
        val centro = Offset(size.width / 2, size.height / 2)
        val corPrincipal = if (estado == AvatarState.ERROR) CorErro else AzulNeon

        rotate(degrees = anim.inclinacaoGraus, pivot = centro) {
            drawCircle(
                brush = Brush.radialGradient(listOf(corPrincipal.copy(alpha = anim.brilho * 0.5f), corPrincipal.copy(alpha = 0f))),
                radius = raio,
                center = centro,
            )
            drawCircle(
                color = corPrincipal.copy(alpha = anim.brilho),
                radius = raio * 0.62f,
                center = centro,
                style = Stroke(width = raio * 0.06f),
            )
            drawArc(
                color = DouradoDiscreto,
                startAngle = anim.anguloDestaque,
                sweepAngle = 70f,
                useCenter = false,
                topLeft = Offset(centro.x - raio * 0.62f, centro.y - raio * 0.62f),
                size = Size(raio * 1.24f, raio * 1.24f),
                style = Stroke(width = raio * 0.035f),
            )
            val alturaOlho = (raio * 0.10f * (1f - anim.fechamentoOlho)).coerceAtLeast(raio * 0.015f)
            listOf(-1f, 1f).forEach { lado ->
                drawOval(
                    color = corPrincipal.copy(alpha = anim.brilho),
                    topLeft = Offset(centro.x + lado * raio * 0.24f - raio * 0.07f, centro.y - raio * 0.12f - alturaOlho / 2),
                    size = Size(raio * 0.14f, alturaOlho),
                )
            }
            val aberturaBoca = if (estado == AvatarState.SPEAKING) 0.3f + anim.brilho * 0.4f else 0f
            desenharBocaVetor(centro, raio, estado, aberturaBoca, corPrincipal)
        }
    }
}

/**
 * Desenho a partir da imagem REAL da atendente (`beta_avatar_base.png`).
 * A imagem nunca é distorcida/esticada como um todo (ajuste "contain",
 * leve inclinação/respiração no conjunto inteiro). Como é uma FOTO
 * ÚNICA (sem camadas de olhos/boca separadas), a animação é feita por
 * um warp geométrico 2D (malha 5x5 vértices, gerada por curva suave —
 * ver FormasVisema.malha — via `android.graphics.Canvas.
 * drawBitmapMesh`) sobre os PRÓPRIOS pixels da boca — nunca desenha
 * uma forma inventada por cima do rosto. Cada visema (ver Visema.kt/
 * FormasVisema) tem parâmetros próprios de abertura/largura, então a
 * boca muda de FORMATO (largo/estreito/arredondado/fechado), não só
 * de altura.
 */
@Composable
fun AvatarRendererImagem(estado: AvatarState, anim: AvatarAnimacao, modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    val densidade = LocalDensity.current

    BoxWithConstraints(modifier = modifier) {
        val larguraAlvoPx = with(densidade) { maxWidth.roundToPx() }.coerceAtLeast(1)
        val bitmap = remember(larguraAlvoPx) {
            carregarBitmapOtimizado(contexto, R.drawable.beta_avatar_base, larguraAlvoPx)
        }
        // Recorte da boca feito UMA VEZ por bitmap carregado, não a
        // cada frame (evita alocar um Bitmap novo 60x/s durante a
        // fala — item de performance/hardware moderado).
        val recorteBoca = remember(bitmap) { bitmap?.let { recortarBocaAndroid(it, BOCA) } }

        if (bitmap != null) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                desenharAvatarImagem(bitmap, recorteBoca, estado, anim)
            }
        } else {
            AvatarRendererVetorial(estado = estado, anim = anim, modifier = Modifier.fillMaxSize())
        }
    }
}

/** Decodifica a imagem já reduzida para o tamanho exibido (nunca o
 * bitmap de 1199x1312 inteiro num avatar de 48dp) — otimização real de
 * memória (item de performance), via `inSampleSize` do Android. */
private fun carregarBitmapOtimizado(context: android.content.Context, resId: Int, larguraAlvoPx: Int): ImageBitmap? = try {
    val opcoesMedida = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeResource(context.resources, resId, opcoesMedida)

    var inSampleSize = 1
    var larguraAtual = opcoesMedida.outWidth
    while (larguraAtual / 2 >= larguraAlvoPx) {
        inSampleSize *= 2
        larguraAtual /= 2
    }

    val opcoesFinais = BitmapFactory.Options().apply { this.inSampleSize = inSampleSize }
    BitmapFactory.decodeResource(context.resources, resId, opcoesFinais)?.asImageBitmap()
} catch (e: Exception) {
    null
}

/** Recorta, uma única vez, a região da boca em pixels reais do bitmap
 * Android original (não do ImageBitmap reduzido) — usada como textura
 * fixa do warp de malha (ver desenharBocaComMalha). */
private fun recortarBocaAndroid(bitmap: ImageBitmap, caixa: RetanguloFracionario): android.graphics.Bitmap? {
    val bitmapAndroid = bitmap.asAndroidBitmap()
    val x = (caixa.x0 * bitmapAndroid.width).roundToInt()
    val y = (caixa.y0 * bitmapAndroid.height).roundToInt()
    val w = ((caixa.x1 - caixa.x0) * bitmapAndroid.width).roundToInt().coerceAtLeast(1)
    val h = ((caixa.y1 - caixa.y0) * bitmapAndroid.height).roundToInt().coerceAtLeast(1)
    return try {
        android.graphics.Bitmap.createBitmap(bitmapAndroid, x, y, w, h)
    } catch (e: Exception) {
        null
    }
}

private fun DrawScope.desenharAvatarImagem(bitmap: ImageBitmap, recorteBoca: android.graphics.Bitmap?, estado: AvatarState, anim: AvatarAnimacao) {
    val corDestaque = if (estado == AvatarState.ERROR) CorErro else AzulNeon
    val centro = Offset(size.width / 2, size.height / 2)

    drawCircle(
        brush = Brush.radialGradient(listOf(corDestaque.copy(alpha = anim.brilho * 0.35f), corDestaque.copy(alpha = 0f))),
        radius = size.minDimension * 0.55f,
        center = centro,
    )

    val aspectoImagem = bitmap.width.toFloat() / bitmap.height
    val aspectoCanvas = size.width / size.height
    val (larguraBase, alturaBase) = if (aspectoCanvas > aspectoImagem) {
        (size.height * aspectoImagem) to size.height
    } else {
        size.width to (size.width / aspectoImagem)
    }
    val largura = larguraBase * anim.respiracao
    val altura = alturaBase * anim.respiracao
    val destinoX = (size.width - largura) / 2 + anim.balancoLateral * size.width
    val destinoY = (size.height - altura) / 2

    rotate(degrees = anim.inclinacaoGraus, pivot = centro) {
        val dstOffset = IntOffset(destinoX.roundToInt(), destinoY.roundToInt())
        val dstSize = IntSize(largura.roundToInt(), altura.roundToInt())

        drawImage(image = bitmap, dstOffset = dstOffset, dstSize = dstSize)

        if (anim.fechamentoOlho > 0.02f) {
            desenharOlhoFechando(bitmap, OLHO_ESQUERDO, dstOffset, dstSize, anim.fechamentoOlho)
            desenharOlhoFechando(bitmap, OLHO_DIREITO, dstOffset, dstSize, anim.fechamentoOlho)
        }
        if (anim.olharDeslocamento != Offset.Zero) {
            desenharOlharIris(bitmap, OLHO_ESQUERDO, dstOffset, dstSize, anim.olharDeslocamento)
            desenharOlharIris(bitmap, OLHO_DIREITO, dstOffset, dstSize, anim.olharDeslocamento)
        }
        if (kotlin.math.abs(anim.elevacaoSobrancelha) > 0.02f) {
            desenharSobrancelha(bitmap, SOBRANCELHA_ESQUERDA, dstOffset, dstSize, anim.elevacaoSobrancelha)
            desenharSobrancelha(bitmap, SOBRANCELHA_DIREITA, dstOffset, dstSize, anim.elevacaoSobrancelha)
        }
        if (recorteBoca != null && (estado == AvatarState.SPEAKING || anim.formaBoca.any { it != Offset.Zero })) {
            desenharBocaComMalha(recorteBoca, BOCA, dstOffset, dstSize, anim.formaBoca)
        }
    }
}

/** Levanta/abaixa a sobrancelha deslocando os próprios pixels da
 * região dela verticalmente — mesma técnica dos olhos/boca (recorte
 * real, nunca uma forma desenhada por cima). `elevacao` positivo =
 * sobrancelha sobe (atenção/aprovação), negativo = desce um pouco
 * (concentração leve). */
private fun DrawScope.desenharSobrancelha(bitmap: ImageBitmap, caixa: RetanguloFracionario, dstOffset: IntOffset, dstSize: IntSize, elevacao: Float) {
    val src = caixaParaPixelsFonte(bitmap, caixa)
    val dst = caixaParaPixelsDestino(caixa, dstOffset, dstSize)
    val deslocY = (-elevacao * dst.height * 0.6f).roundToInt()
    drawImage(
        image = bitmap,
        srcOffset = src.offset,
        srcSize = src.size,
        dstOffset = IntOffset(dst.offset.x, dst.offset.y + deslocY),
        dstSize = dst.size,
    )
}

/** Fecha o olho comprimindo os próprios pixels da região do olho numa
 * faixa progressivamente mais fina perto da base da caixa — suave
 * (contínuo, não um corte seco), sem inventar cor/forma. */
private fun DrawScope.desenharOlhoFechando(bitmap: ImageBitmap, caixa: RetanguloFracionario, dstOffset: IntOffset, dstSize: IntSize, fechamento: Float) {
    val src = caixaParaPixelsFonte(bitmap, caixa)
    val dst = caixaParaPixelsDestino(caixa, dstOffset, dstSize)
    val alturaFinal = (dst.height * (1f - fechamento * 0.85f)).roundToInt().coerceAtLeast(1)
    drawImage(
        image = bitmap,
        srcOffset = src.offset,
        srcSize = src.size,
        dstOffset = IntOffset(dst.offset.x, dst.offset.y + dst.height - alturaFinal),
        dstSize = IntSize(dst.width, alturaFinal),
    )
}

/** Pequeno deslocamento do miolo do olho (região central, aproximando
 * a íris) dentro da própria caixa do olho — simula "olhar para os
 * lados" reaproveitando os pixels reais da foto, sem criar uma
 * pupila artificial. Amplitude pequena o bastante para não sair da
 * área do olho. */
private fun DrawScope.desenharOlharIris(bitmap: ImageBitmap, caixa: RetanguloFracionario, dstOffset: IntOffset, dstSize: IntSize, deslocamento: Offset) {
    val largura = caixa.x1 - caixa.x0
    val altura = caixa.y1 - caixa.y0
    val margem = 0.28f
    val irisCaixa = RetanguloFracionario(
        caixa.x0 + largura * margem,
        caixa.y0 + altura * margem,
        caixa.x1 - largura * margem,
        caixa.y1 - altura * margem,
    )
    val src = caixaParaPixelsFonte(bitmap, irisCaixa)
    val dst = caixaParaPixelsDestino(irisCaixa, dstOffset, dstSize)
    val deslocX = (deslocamento.x * dst.width * 0.35f).roundToInt()
    val deslocY = (deslocamento.y * dst.height * 0.35f).roundToInt()
    drawImage(
        image = bitmap,
        srcOffset = src.offset,
        srcSize = src.size,
        dstOffset = IntOffset(dst.offset.x + deslocX, dst.offset.y + deslocY),
        dstSize = dst.size,
    )
}

/** Warp em malha 4x4 (android.graphics.Canvas.drawBitmapMesh) sobre a
 * caixa da boca — cada visema empurra os vértices das linhas do meio
 * para um formato diferente (ver FormasVisema). Continua sendo só um
 * reaproveitamento geométrico dos pixels reais da foto (textura =
 * bitmap original), nunca uma forma desenhada por cima. */
private fun DrawScope.desenharBocaComMalha(recorte: android.graphics.Bitmap, caixa: RetanguloFracionario, dstOffset: IntOffset, dstSize: IntSize, formaBoca: List<Offset>) {
    val dst = caixaParaPixelsDestino(caixa, dstOffset, dstSize)
    if (dst.width <= 0 || dst.height <= 0) return

    val meshW = FormasVisema.COLUNAS
    val meshH = FormasVisema.LINHAS
    val verts = FloatArray((meshW + 1) * (meshH + 1) * 2)
    var i = 0
    for (linha in 0..meshH) {
        for (coluna in 0..meshW) {
            val fx = coluna / meshW.toFloat()
            val fy = linha / meshH.toFloat()
            val deslocamento = formaBoca.getOrElse(linha * (meshW + 1) + coluna) { Offset.Zero }
            val x = dst.offset.x + (fx + deslocamento.x) * dst.width
            val y = dst.offset.y + (fy + deslocamento.y) * dst.height
            verts[i++] = x
            verts[i++] = y
        }
    }

    drawContext.canvas.nativeCanvas.drawBitmapMesh(recorte, meshW, meshH, verts, 0, null, 0, null)
}

private data class CaixaPixels(val offset: IntOffset, val size: IntSize) {
    val width get() = size.width
    val height get() = size.height
}

private fun caixaParaPixelsFonte(bitmap: ImageBitmap, caixa: RetanguloFracionario): CaixaPixels {
    val x0 = (caixa.x0 * bitmap.width).roundToInt()
    val y0 = (caixa.y0 * bitmap.height).roundToInt()
    val x1 = (caixa.x1 * bitmap.width).roundToInt()
    val y1 = (caixa.y1 * bitmap.height).roundToInt()
    return CaixaPixels(IntOffset(x0, y0), IntSize((x1 - x0).coerceAtLeast(1), (y1 - y0).coerceAtLeast(1)))
}

private fun caixaParaPixelsDestino(caixa: RetanguloFracionario, dstOffset: IntOffset, dstSize: IntSize): CaixaPixels {
    val x0 = dstOffset.x + (caixa.x0 * dstSize.width).roundToInt()
    val y0 = dstOffset.y + (caixa.y0 * dstSize.height).roundToInt()
    val x1 = dstOffset.x + (caixa.x1 * dstSize.width).roundToInt()
    val y1 = dstOffset.y + (caixa.y1 * dstSize.height).roundToInt()
    return CaixaPixels(IntOffset(x0, y0), IntSize((x1 - x0).coerceAtLeast(1), (y1 - y0).coerceAtLeast(1)))
}

private fun DrawScope.desenharBocaVetor(centro: Offset, raio: Float, estado: AvatarState, aberturaBoca: Float, cor: Color) {
    val yBoca = centro.y + raio * 0.32f
    when (estado) {
        AvatarState.SPEAKING -> drawOval(
            color = cor.copy(alpha = 0.9f),
            topLeft = Offset(centro.x - raio * 0.16f, yBoca - (raio * 0.16f * aberturaBoca) / 2),
            size = Size(raio * 0.32f, raio * 0.16f * aberturaBoca),
        )
        AvatarState.ERROR -> drawLine(
            color = cor, start = Offset(centro.x - raio * 0.16f, yBoca), end = Offset(centro.x + raio * 0.16f, yBoca),
            strokeWidth = raio * 0.035f, cap = StrokeCap.Round,
        )
        AvatarState.CONFIRMING -> drawArc(
            color = cor, startAngle = 15f, sweepAngle = 150f, useCenter = false,
            topLeft = Offset(centro.x - raio * 0.22f, yBoca - raio * 0.20f), size = Size(raio * 0.44f, raio * 0.28f),
            style = Stroke(width = raio * 0.04f, cap = StrokeCap.Round),
        )
        AvatarState.LISTENING, AvatarState.THINKING -> drawLine(
            color = cor, start = Offset(centro.x - raio * 0.14f, yBoca), end = Offset(centro.x + raio * 0.14f, yBoca),
            strokeWidth = raio * 0.03f, cap = StrokeCap.Round,
        )
        AvatarState.IDLE -> drawArc(
            color = cor, startAngle = 20f, sweepAngle = 140f, useCenter = false,
            topLeft = Offset(centro.x - raio * 0.20f, yBoca - raio * 0.16f), size = Size(raio * 0.40f, raio * 0.22f),
            style = Stroke(width = raio * 0.035f, cap = StrokeCap.Round),
        )
    }
}
