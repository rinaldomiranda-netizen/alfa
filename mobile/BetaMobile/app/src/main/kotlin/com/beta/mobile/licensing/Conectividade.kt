package com.beta.mobile.licensing

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities

/**
 * Verifica internet real (item do pedido: "quando o dispositivo não
 * possuir internet, mostrar ATIVAÇÃO PRESENCIAL NECESSÁRIA"). Isto é
 * só conectividade de rede — nunca confundir com "ativação remota
 * configurada". Mesmo com internet, esta instalação não tem um
 * endpoint real de ativação no BETA-CLOUD (ver limitações do
 * relatório) — os dois fatos são checados e mostrados separadamente,
 * nunca fingindo que um implica o outro.
 */
object Conectividade {
    fun possuiInternet(contexto: Context): Boolean {
        val gerenciador = contexto.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val rede = gerenciador.activeNetwork ?: return false
        val capacidades = gerenciador.getNetworkCapabilities(rede) ?: return false
        return capacidades.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capacidades.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
}
