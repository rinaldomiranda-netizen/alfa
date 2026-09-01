package com.beta.mobile

import java.net.HttpURLConnection
import java.net.URL

/**
 * Cliente do BETA-CLOUD para o mobile — espelha o mesmo contrato do
 * núcleo desktop (ver api/contrato.py e memory/beta_cloud_client.py):
 * /auth, /profile, /devices, /skills, /tasks, /sync, /version.
 *
 * NUNCA usa service_role nem grava senha em texto puro — só a
 * publishable key (BuildConfig, nunca hardcoded aqui) e o JWT da
 * sessão, mantido só em memória do processo (nunca em
 * SharedPreferences nem arquivo).
 *
 * Sem BETA_CLOUD_PROJECT_URL/BETA_CLOUD_PUBLISHABLE_KEY configurados
 * no build (ver app/build.gradle.kts), `configurado()` é false e o
 * app continua funcionando 100% local/offline — a internet nunca é
 * exigida para abrir nem operar o app (catálogo local, voz on-device,
 * acessibilidade).
 */
class BetaCloudApi(
    private val url: String = BuildConfig.BETA_CLOUD_PROJECT_URL,
    private val publishableKey: String = BuildConfig.BETA_CLOUD_PUBLISHABLE_KEY,
) {
    private var jwtSessao: String? = null

    fun configurado(): Boolean = url.isNotBlank() && publishableKey.isNotBlank()

    fun autenticado(): Boolean = jwtSessao != null

    /**
     * POST /auth/v1/token?grant_type=password (Supabase Auth, mesmo
     * contrato do desktop). A senha passada aqui nunca é retida além
     * do escopo desta chamada.
     */
    fun autenticar(email: String, senha: String): Resultado {
        if (!configurado()) return Resultado.erro("BETA-CLOUD não configurado neste aplicativo.")

        return try {
            val conexao = URL("$url/auth/v1/token?grant_type=password").openConnection() as HttpURLConnection
            conexao.requestMethod = "POST"
            conexao.setRequestProperty("apikey", publishableKey)
            conexao.setRequestProperty("Content-Type", "application/json")
            conexao.doOutput = true
            val corpo = """{"email":"${email}","password":"${senha}"}"""
            conexao.outputStream.use { it.write(corpo.toByteArray()) }

            if (conexao.responseCode in 200..299) {
                val resposta = conexao.inputStream.bufferedReader().use { it.readText() }
                jwtSessao = Regex("\"access_token\":\"([^\"]+)\"").find(resposta)?.groupValues?.get(1)
                if (jwtSessao != null) Resultado.ok("Autenticado.") else Resultado.erro("Resposta sem token de sessão.")
            } else {
                val erro = conexao.errorStream?.bufferedReader()?.use { it.readText() } ?: "erro ${conexao.responseCode}"
                Resultado.erro("Falha na autenticação: $erro")
            }
        } catch (e: Exception) {
            Resultado.erro("BETA-CLOUD inacessível: ${e.message}")
        }
    }

    data class Resultado(val sucesso: Boolean, val mensagem: String) {
        companion object {
            fun ok(msg: String) = Resultado(true, msg)
            fun erro(msg: String) = Resultado(false, msg)
        }
    }
}
