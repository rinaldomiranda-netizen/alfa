package com.beta.mobile.licensing

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant

/**
 * Um PEDIDO de ativação (item do pedido: "cria activation_request...
 * status PENDING_APPROVAL"). Esta instalação não tem um endpoint real
 * no BETA-CLOUD para RECEBER isto (ver limitações do relatório) —
 * então esta classe hoje serve só para a ATIVAÇÃO PRESENCIAL (item 8
 * do pedido): descreve exatamente o que o dispositivo está pedindo,
 * em um formato que o BETA_OWNER cola direto no `emitir_licenca.py`
 * (a ferramenta que tem a chave privada), sem precisar copiar o
 * device_id ou digitar nome de módulo à mão — isso é o "sem código
 * manual de ativação" aplicado ao caminho presencial.
 *
 * Se um dia existir um POST /activation_requests real no BETA-CLOUD
 * (fora do escopo autorizado nesta sessão), `paraJson()` já é
 * exatamente o corpo que esse endpoint receberia.
 */
data class SolicitacaoAtivacao(
    val deviceId: String,
    val plataforma: String,
    val modulosSolicitados: Set<Modulo>,
    val criadoEm: Instant = Instant.now(),
) {
    fun paraJson(): String {
        val json = JSONObject()
        json.put("device_id", deviceId)
        json.put("platform", plataforma)
        json.put("requested_modules", JSONArray(modulosSolicitados.map { it.name }))
        json.put("created_at", criadoEm.toString())
        json.put("status", "PENDING_APPROVAL")
        return json.toString()
    }

    /** Comando pronto pra rodar em `licensing_tools/` (máquina segura
     * do proprietário, nunca no dispositivo — ver item 10 do pedido:
     * chave privada nunca no aparelho final). */
    fun paraComandoCli(customerId: String, organizationId: String, diasValidade: Int = 365): String {
        val modulosCsv = modulosSolicitados.joinToString(",") { it.name }
        return "python emitir_licenca.py --device-id $deviceId --customer-id \"$customerId\" " +
            "--organization-id \"$organizationId\" --modulos $modulosCsv --dias-validade $diasValidade " +
            "--saida $deviceId.beta-license"
    }
}
