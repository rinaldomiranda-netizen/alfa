package com.beta.mobile.avatar

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Abstração pedida explicitamente ("Criar abstração: AvatarEngine") —
 * separa QUEM RENDERIZA do resto do avatar. Animação
 * (AvatarAnimationController), estado (AvatarState), lip-sync
 * (Visema/FormasVisema) e TTS (VoiceController) não sabem nada sobre
 * qual engine está desenhando. Trocar de engine (ex.: quando existir
 * um modelo 3D real da BETA) nunca deve exigir mudar as telas que
 * chamam `BetaAvatar` — só a lógica de `engineAtiva()` abaixo.
 *
 * Isso também é o que permite, no futuro, portar o avatar pra fora do
 * Compose (Windows, Raspberry Pi) — cada plataforma implementaria sua
 * própria `AvatarEngine` reaproveitando o mesmo `AvatarAnimacao`.
 */
interface AvatarEngine {
    val nome: String

    /** Compile-time/runtime: esta engine tem o que precisa pra
     * desenhar algo de verdade agora? */
    fun disponivel(): Boolean

    @Composable
    fun Render(estado: AvatarState, anim: AvatarAnimacao, modifier: Modifier)
}

/**
 * Engine principal HOJE — desenha a foto real da atendente
 * (`beta_avatar_base.png`) com warp de malha nos olhos/boca (ver
 * AvatarRenderer.AvatarRendererImagem). É a única engine que
 * realmente mostra a BETA (as outras duas, quando/se existirem
 * assets, ainda precisam ser alimentadas com um modelo de verdade
 * dela — ver Avatar3DEngine).
 */
object Avatar2DEngine : AvatarEngine {
    override val nome = "Avatar2DEngine (foto + malha)"
    override fun disponivel(): Boolean = AvatarAssets.possuiImagemBase()

    @Composable
    override fun Render(estado: AvatarState, anim: AvatarAnimacao, modifier: Modifier) {
        AvatarRendererImagem(estado = estado, anim = anim, modifier = modifier)
    }
}

/**
 * Engine 3D (VRM/three-vrm via WebView, ou equivalente) — pesquisada
 * (ver relatório) mas NÃO implementada com conteúdo real: não existe
 * hoje um caminho gratuito/offline pra gerar um modelo 3D com a
 * aparência da BETA a partir de uma única foto — isso exige um
 * artista modelando manualmente. `disponivel()` fica false até existir
 * um arquivo de modelo real (ver AvatarAssets) — quando existir, só
 * esta classe precisa ganhar a implementação de verdade (carregar o
 * WebView/three-vrm), sem tocar em mais nada do app.
 */
object Avatar3DEngine : AvatarEngine {
    override val nome = "Avatar3DEngine (reservado — sem modelo 3D real ainda)"
    override fun disponivel(): Boolean = false

    @Composable
    override fun Render(estado: AvatarState, anim: AvatarAnimacao, modifier: Modifier) {
        // Nunca deveria ser chamado (disponivel() == false), mas se um
        // dia for chamado por engano, cai no 2D em vez de quebrar.
        Avatar2DEngine.Render(estado, anim, modifier)
    }
}

/** Rede de segurança final — vetor simples, só se `Avatar2DEngine`
 * relatar indisponibilidade (não deveria acontecer: a imagem é
 * compilada junto do app). */
object FallbackAvatarEngine : AvatarEngine {
    override val nome = "FallbackAvatarEngine (vetor)"
    override fun disponivel(): Boolean = true

    @Composable
    override fun Render(estado: AvatarState, anim: AvatarAnimacao, modifier: Modifier) {
        AvatarRendererVetorial(estado = estado, anim = anim, modifier = modifier)
    }
}

fun engineAtiva(): AvatarEngine = when {
    Avatar3DEngine.disponivel() -> Avatar3DEngine
    Avatar2DEngine.disponivel() -> Avatar2DEngine
    else -> FallbackAvatarEngine
}
