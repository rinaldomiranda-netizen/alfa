package com.beta.mobile.avatar

import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/**
 * Ponto de entrada público do avatar da BETA — o resto do app (Splash,
 * Aplicativo, Totem, Discreto) só conhece esta função, nunca desenha
 * nada diretamente. Isso é o que permite trocar o desenho vetorial
 * por artes reais depois (ver AvatarAssets) sem tocar nas telas.
 *
 * `estado` é o evento do avatar (LISTENING/THINKING/SPEAKING/
 * CONFIRMING/ERROR/IDLE) — desacoplado do estado geral do app (ver
 * com.beta.mobile.ui.avatarStateDe). `visema` vem do texto REAL sendo
 * falado pelo TTS no momento (ver VoiceController.falar/onRangeStart)
 * e só importa quando `estado == SPEAKING`. `perfil` controla a
 * intensidade da animação (item de performance).
 */
@Composable
fun BetaAvatar(
    estado: AvatarState,
    visema: Visema = Visema.REST,
    perfil: PerfilDesempenho = PerfilDesempenho.BALANCEADO,
    tamanho: Int = 160,
    modifier: Modifier = Modifier,
) {
    val anim = rememberAvatarAnimacao(estado, visema, perfil)

    // A engine é escolhida em engineAtiva() (ver AvatarEngine.kt) —
    // hoje sempre Avatar2DEngine, porque não existe modelo 3D real da
    // BETA (ver Avatar3DEngine). Quando existir, só a lógica de
    // engineAtiva() muda, nunca esta função nem as telas que a chamam.
    engineAtiva().Render(
        estado = estado,
        anim = anim,
        modifier = modifier.size(tamanho.dp).semantics { contentDescription = "BETA, assistente virtual." },
    )
}
