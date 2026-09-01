package com.beta.mobile.ui

import com.beta.mobile.avatar.AvatarState

/**
 * Traduz o estado de interação do app (EstadoBeta — usado também para
 * habilitar botões e rótulos de texto) para o evento do avatar
 * (AvatarState — só interessa à renderização visual). Mantém o avatar
 * desacoplado do resto do app, conforme arquitetura escalável pedida.
 *
 * `confirmando` é um pulso curto e à parte (não faz parte de
 * EstadoBeta porque não deve desabilitar nenhum botão) disparado logo
 * depois de uma resposta falada com sucesso.
 */
fun avatarStateDe(estado: EstadoBeta, confirmando: Boolean): AvatarState = when {
    confirmando -> AvatarState.CONFIRMING
    estado == EstadoBeta.OUVINDO -> AvatarState.LISTENING
    estado == EstadoBeta.PROCESSANDO -> AvatarState.THINKING
    estado == EstadoBeta.FALANDO -> AvatarState.SPEAKING
    estado == EstadoBeta.ERRO -> AvatarState.ERROR
    else -> AvatarState.IDLE
}
