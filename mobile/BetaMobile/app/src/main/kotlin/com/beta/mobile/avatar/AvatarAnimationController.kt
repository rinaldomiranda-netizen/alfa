package com.beta.mobile.avatar

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Offset
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.random.Random

/** Fases de animação num instante — separadas do desenho
 * (AvatarRenderer) e da interpretação do estado da conversa
 * (AvatarState), conforme arquitetura escalável pedida. */
data class AvatarAnimacao(
    val fechamentoOlho: Float,
    val olharDeslocamento: Offset,
    val formaBoca: List<Offset>,
    val elevacaoSobrancelha: Float,
    val inclinacaoGraus: Float,
    val respiracao: Float,
    val balancoLateral: Float,
    val anguloDestaque: Float,
    val brilho: Float,
)

/**
 * Controlador de animação do avatar. Não sabe desenhar nada (isso é
 * do AvatarRenderer) e não sabe de TTS/catálogo/Planner — só produz
 * fases de movimento a partir de `estado`, `visemaAlvo` (vindo do
 * texto real sendo falado, ver VoiceController.falar) e `perfil`.
 */
@Composable
fun rememberAvatarAnimacao(estado: AvatarState, visemaAlvo: Visema, perfil: PerfilDesempenho): AvatarAnimacao {
    val animarExtras = perfil != PerfilDesempenho.ECO
    val transicao = rememberInfiniteTransition(label = "avatar_ctrl")

    val brilho by transicao.animateFloat(
        initialValue = 0.6f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1800, easing = LinearEasing), RepeatMode.Reverse),
        label = "brilho",
    )
    val anguloDestaque by transicao.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(6000, easing = LinearEasing)),
        label = "angulo_destaque",
    )

    val amplitudeInclinacao = when (perfil) {
        PerfilDesempenho.ECO -> 0f
        PerfilDesempenho.BALANCEADO -> 2f
        PerfilDesempenho.AVANCADO -> 3.5f
    }
    val inclinacao by transicao.animateFloat(
        initialValue = -amplitudeInclinacao,
        targetValue = amplitudeInclinacao,
        animationSpec = infiniteRepeatable(tween(4200, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "inclinacao",
    )
    val respiracao by transicao.animateFloat(
        initialValue = if (animarExtras) 0.985f else 1f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(2600, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "respiracao",
    )
    // Mudança de peso — balanço horizontal bem sutil do corpo inteiro
    // (item "microanimações: mudança de peso"), período longo pra não
    // parecer um metrônomo.
    val balancoLateral by transicao.animateFloat(
        initialValue = if (animarExtras) -0.01f else 0f,
        targetValue = 0.01f,
        animationSpec = infiniteRepeatable(tween(5200, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "balanco",
    )

    // Piscar NATURAL — fechamento e abertura suaves (não um corte
    // seco), em intervalo irregular, e desligado de propósito da fala
    // (ver pedido: "não sincronizar sempre com fala").
    val fechamentoOlho = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(Random.nextLong(2500, 6000))
            fechamentoOlho.animateTo(1f, tween(90, easing = FastOutSlowInEasing))
            fechamentoOlho.animateTo(0f, tween(140, easing = FastOutSlowInEasing))
        }
    }

    // Olhar — pequenas mudanças de direção, só no perfil AVANÇADO
    // (custo extra de composição/leitura). Suavizado com Animatable.
    val olharX = remember { Animatable(0f) }
    val olharY = remember { Animatable(0f) }
    if (perfil == PerfilDesempenho.AVANCADO) {
        LaunchedEffect(Unit) {
            while (true) {
                delay(Random.nextLong(2000, 4500))
                launch { olharX.animateTo(Random.nextDouble(-1.0, 1.0).toFloat(), tween(500, easing = FastOutSlowInEasing)) }
                launch { olharY.animateTo(Random.nextDouble(-0.5, 0.5).toFloat(), tween(500, easing = FastOutSlowInEasing)) }
            }
        }
    }

    // Sobrancelha — sobe um pouco em OUVINDO/CONFIRMING (atenção/
    // aprovação), desce um pouco em THINKING (concentração leve).
    val elevacaoSobrancelhaAlvo = when (estado) {
        AvatarState.LISTENING -> 0.6f
        AvatarState.CONFIRMING -> 0.3f
        AvatarState.THINKING -> -0.4f
        else -> 0f
    }
    val elevacaoSobrancelha = remember { Animatable(0f) }
    LaunchedEffect(elevacaoSobrancelhaAlvo) {
        elevacaoSobrancelha.animateTo(elevacaoSobrancelhaAlvo, tween(280, easing = FastOutSlowInEasing))
    }

    // Visema — transição suave entre a forma de boca anterior e a
    // nova, disparada só quando o visema-alvo muda de verdade.
    var visemaAnterior by remember { mutableStateOf(Visema.REST) }
    var formaDe by remember { mutableStateOf(FormasVisema.malha(Visema.REST, FormasVisema.LINHAS, FormasVisema.COLUNAS)) }
    var formaPara by remember { mutableStateOf(formaDe) }
    val progressoVisema = remember { Animatable(1f) }
    LaunchedEffect(visemaAlvo, estado) {
        val alvo = if (estado == AvatarState.SPEAKING) visemaAlvo else Visema.REST
        if (alvo != visemaAnterior) {
            formaDe = FormasVisema.interpolar(formaDe, formaPara, progressoVisema.value)
            formaPara = FormasVisema.malha(alvo, FormasVisema.LINHAS, FormasVisema.COLUNAS)
            visemaAnterior = alvo
            progressoVisema.snapTo(0f)
            progressoVisema.animateTo(1f, tween(90, easing = FastOutSlowInEasing))
        }
    }

    return AvatarAnimacao(
        fechamentoOlho = fechamentoOlho.value,
        olharDeslocamento = Offset(olharX.value, olharY.value),
        formaBoca = if (animarExtras) FormasVisema.interpolar(formaDe, formaPara, progressoVisema.value) else FormasVisema.malha(Visema.REST, FormasVisema.LINHAS, FormasVisema.COLUNAS),
        elevacaoSobrancelha = if (animarExtras) elevacaoSobrancelha.value else 0f,
        inclinacaoGraus = if (animarExtras) inclinacao else 0f,
        respiracao = respiracao,
        balancoLateral = balancoLateral,
        anguloDestaque = anguloDestaque,
        brilho = brilho,
    )
}
