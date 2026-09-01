package com.beta.mobile.avatar

/**
 * Eventos/estado do avatar — desacoplado do BETA Core, do TTS e do
 * Planner (item de arquitetura escalável: "avatar recebe eventos e
 * responde visualmente"). Quem gera esses eventos é a camada de UI
 * (ver `com.beta.mobile.ui.avatarStateDe`), nunca o avatar decide
 * sozinho o que está acontecendo na conversa.
 */
enum class AvatarState { IDLE, LISTENING, THINKING, SPEAKING, CONFIRMING, ERROR }

/**
 * Perfil de desempenho da animação (item de performance) — reduz ou
 * aumenta a quantidade de movimento sem trocar o desenho em si, para
 * caber em aparelhos mais fracos.
 */
enum class PerfilDesempenho { ECO, BALANCEADO, AVANCADO }
