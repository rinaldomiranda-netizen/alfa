package com.beta.mobile.avatar

/**
 * Conjunto mínimo de visemas pedido (REST + vogais + grupos
 * consonantais). Não é fonética precisa — é uma classificação por
 * GRAFEMA (letra), suficiente para dar formas de boca diferentes
 * durante a fala sem precisar de um modelo de reconhecimento de fala.
 */
enum class Visema { REST, A, E, I, O, U, MBP, FV, L, SZ, CHJ, KG, TH }

/**
 * Mapeia o texto realmente sendo falado (recebido em tempo real do
 * TextToSpeech via `onRangeStart`, ver VoiceController.falar) para um
 * visema — é o que permite a boca reagir ao TEXTO/ÁUDIO real da fala,
 * e não só a um relógio artificial. Baseado em grafema (letra do
 * português), não em fonemas reais — deliberadamente simples (ver
 * pedido: "não precisa ser perfeito foneticamente na primeira
 * versão").
 */
object MapeadorDeVisema {
    fun doTrecho(trecho: String): Visema {
        val c = trecho.firstOrNull { it.isLetter() }?.lowercaseChar() ?: return Visema.REST
        return when (c) {
            'a' -> Visema.A
            'e', 'é', 'ê' -> Visema.E
            'i' -> Visema.I
            'o', 'ó', 'ô', 'õ' -> Visema.O
            'u' -> Visema.U
            'm', 'b', 'p' -> Visema.MBP
            'f', 'v' -> Visema.FV
            'l' -> Visema.L
            's', 'z', 'ç' -> Visema.SZ
            'c', 'g', 'k', 'q' -> Visema.KG
            'x', 'j' -> Visema.CHJ
            ' ', '\n', '\t', ',', '.', '!', '?' -> Visema.REST
            else -> Visema.TH
        }
    }
}
