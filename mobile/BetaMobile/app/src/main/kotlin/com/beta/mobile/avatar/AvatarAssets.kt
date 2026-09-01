package com.beta.mobile.avatar

import android.content.Context

/**
 * Assets reais da atendente BETA.
 *
 * `beta_avatar_base.png` (res/drawable) é a imagem oficial fornecida
 * nesta sessão — rosto/cabelo/headset/roupa reais, fundo transparente
 * (RGBA). Ela é usada tal como veio, sem distorcer nem esticar (ver
 * AvatarRenderer.AvatarRendererImagem).
 *
 * `possuiImagemBase()` é `true` de forma garantida em tempo de
 * COMPILAÇÃO: o código referencia `R.drawable.beta_avatar_base`
 * diretamente — se o arquivo não existisse, o build já teria falhado
 * antes de chegar a rodar. Não é uma suposição em runtime.
 *
 * `possuiCamadasIndependentes` continua preparado para o dia em que
 * existirem PNGs separados de olhos/boca (maior fidelidade de
 * animação do que recortar a própria imagem base) — hoje sempre
 * false, porque só a imagem base foi fornecida.
 */
object AvatarAssets {
    fun possuiImagemBase(): Boolean = true

    private val CAMADAS_INDEPENDENTES_ESPERADAS = listOf(
        "avatar/olhos_abertos.png",
        "avatar/olhos_fechados.png",
        "avatar/boca_fechada.png",
        "avatar/boca_aberta.png",
    )

    fun possuiCamadasIndependentes(context: Context): Boolean =
        CAMADAS_INDEPENDENTES_ESPERADAS.all { existeAsset(context, it) }

    private fun existeAsset(context: Context, caminho: String): Boolean = try {
        context.assets.open(caminho).close()
        true
    } catch (e: Exception) {
        false
    }
}
