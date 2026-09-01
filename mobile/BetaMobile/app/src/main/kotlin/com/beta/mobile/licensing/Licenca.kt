package com.beta.mobile.licensing

import org.json.JSONObject
import java.time.Instant
import java.time.format.DateTimeParseException

/**
 * Licença local (item do pedido) — campos mínimos pedidos. Só é
 * construída a partir de um corpo JÁ VERIFICADO (assinatura conferida
 * em LicenseVerifier) — este arquivo nunca confia em dado não
 * assinado.
 */
data class Licenca(
    val licenseId: String,
    val customerId: String,
    val organizationId: String,
    val deviceId: String,
    val status: String,
    val issuedAt: String,
    val expiresAt: String?,
    val modules: Set<Modulo>,
    val edition: String,
    val maxDevices: Int,
    // BONUS_MODULE (item do pedido "5. BÔNUS") — módulo -> instante de
    // expiração (ISO-8601). Nunca confundir com `modules`: um módulo
    // bônus expirado simplesmente não conta mais em
    // GerenciadorLicenca.moduloAutorizado, sem invalidar o resto da
    // licença nem exigir reemissão.
    val bonusModules: Map<Modulo, String> = emptyMap(),
) {
    fun expirada(agora: Instant = Instant.now(), toleranciaDias: Long = 7): Boolean {
        val expiraTexto = expiresAt ?: return false
        val instanteExpiracao = try {
            Instant.parse(expiraTexto)
        } catch (e: DateTimeParseException) {
            return true // data ilegível — trata como expirada, nunca como válida por engano
        }
        // Tolerância (item do pedido: "nunca bloquear imediatamente por
        // uma queda temporária da internet/revalidação") — só some de
        // verdade depois da tolerância.
        return agora.isAfter(instanteExpiracao.plusSeconds(toleranciaDias * 86_400))
    }

    /** Módulos bônus ainda válidos agora (item do pedido: "30/60/90
     * dias conforme configuração") — data ilegível conta como já
     * expirada, nunca como bônus válido por engano. */
    fun modulosBonusAtivos(agora: Instant = Instant.now()): Set<Modulo> =
        bonusModules.filterValues { expiraTexto ->
            try { agora.isBefore(Instant.parse(expiraTexto)) } catch (e: DateTimeParseException) { false }
        }.keys

    companion object {
        /** Nunca lança em corpo malformado — retorna null, pra quem
         * chama decidir tratar como "sem licença válida" (nunca
         * inventa um valor padrão pra um campo ausente). */
        fun deJson(corpo: String): Licenca? = try {
            val json = JSONObject(corpo)
            val modulosJson = json.getJSONArray("modules")
            val modulos = (0 until modulosJson.length()).mapNotNull { i ->
                runCatching { Modulo.valueOf(modulosJson.getString(i)) }.getOrNull()
            }.toSet()
            val bonusJson = json.optJSONObject("bonus_modules")
            val bonus = bonusJson?.keys()?.asSequence()?.mapNotNull { chave ->
                runCatching { Modulo.valueOf(chave) }.getOrNull()?.let { it to bonusJson.getString(chave) }
            }?.toMap() ?: emptyMap()
            Licenca(
                licenseId = json.getString("license_id"),
                customerId = json.getString("customer_id"),
                organizationId = json.optString("organization_id", ""),
                deviceId = json.getString("device_id"),
                status = json.getString("status"),
                issuedAt = json.getString("issued_at"),
                expiresAt = if (json.isNull("expires_at")) null else json.optString("expires_at", null),
                modules = modulos,
                edition = json.optString("edition", "standard"),
                maxDevices = json.optInt("max_devices", 1),
                bonusModules = bonus,
            )
        } catch (e: Exception) {
            null
        }
    }
}
