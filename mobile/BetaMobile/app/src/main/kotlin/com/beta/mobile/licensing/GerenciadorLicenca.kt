package com.beta.mobile.licensing

import com.beta.mobile.Preferencias
import java.time.Instant

/** Resultado de uma tentativa de ativação local (item do pedido) —
 * nunca esconde o motivo real da recusa (sem código técnico pro
 * visitante, mas o motivo aqui é pra quem está ativando). */
sealed class ResultadoAtivacao {
    data class Sucesso(val licenca: Licenca) : ResultadoAtivacao()
    object AssinaturaInvalida : ResultadoAtivacao()
    object DispositivoNaoCorresponde : ResultadoAtivacao()
    object Expirada : ResultadoAtivacao()
    object ArquivoInvalido : ResultadoAtivacao()
}

/** Estado de um módulo (item do pedido "6. TODOS OS MÓDULOS") — usado
 * só para EXIBIÇÃO (Dashboard/Módulos do BETA CONTROL); a decisão
 * real de liberar o recurso continua sendo `moduloAutorizado`
 * (ATIVO, TRIAL e BONUS todos autorizam; os demais não). */
enum class EstadoModulo { ATIVO, INATIVO, TRIAL, BONUS, EXPIRADO, BLOQUEADO }

/**
 * Único ponto do app que decide "este módulo está autorizado?" (item
 * do pedido: "a BETA deve verificar a licença antes de disponibilizar
 * o recurso"). Sem licença ativada, opera em modo DEMO — um conjunto
 * FIXO e limitado de módulos (nunca os sensíveis: integração de
 * empresa, automação, câmera/reconhecimento facial, BETA-CLOUD,
 * marketplace, atualização) — isso é o "default deny" aplicado aos
 * recursos que importam de verdade, sem quebrar o app de teste que já
 * existe.
 */
class GerenciadorLicenca(private val preferencias: Preferencias) {

    private val modulosDemo = setOf(Modulo.TOTEM, Modulo.APLICATIVO, Modulo.ASSISTENTE, Modulo.CATALOGO, Modulo.ACESSIBILIDADE)

    /** Licença ativada e com assinatura/validade OK agora mesmo, ou
     * null se não houver nenhuma (cai no modo DEMO). Reverifica a
     * assinatura toda vez — nunca confia em cache não assinado. */
    fun licencaAtual(): Licenca? {
        val bruto = preferencias.licencaAtivada ?: return null
        val licenca = LicenseVerifier.verificarEExtrair(bruto) ?: return null
        if (licenca.deviceId != preferencias.deviceId) return null
        if (licenca.status != "active") return null
        if (licenca.expirada(Instant.now(), toleranciaDias = 7)) return null
        return licenca
    }

    fun moduloAutorizado(modulo: Modulo): Boolean {
        val licenca = licencaAtual()
        return if (licenca != null) {
            modulo in licenca.modules || modulo in licenca.modulosBonusAtivos()
        } else {
            modulo in modulosDemo
        }
    }

    /** Estado de exibição de um módulo (item do pedido) — nunca usado
     * para autorizar, só para o BETA CONTROL mostrar algo mais preciso
     * que ATIVO/INATIVO quando fizer sentido. */
    fun estadoDoModulo(modulo: Modulo): EstadoModulo {
        val licenca = licencaAtual() ?: return if (modulo in modulosDemo) EstadoModulo.ATIVO else EstadoModulo.INATIVO
        return when {
            modulo in licenca.modules && licenca.edition.equals("trial", ignoreCase = true) -> EstadoModulo.TRIAL
            modulo in licenca.modules -> EstadoModulo.ATIVO
            modulo in licenca.modulosBonusAtivos() -> EstadoModulo.BONUS
            modulo in licenca.bonusModules.keys -> EstadoModulo.EXPIRADO
            else -> EstadoModulo.INATIVO
        }
    }

    fun emModoDemo(): Boolean = licencaAtual() == null

    /** Ativação local presencial (item do pedido) — verifica
     * assinatura, device_id e validade ANTES de salvar. Nunca salva
     * uma licença que não bateu com este aparelho. */
    fun ativarLocal(conteudoArquivo: String): ResultadoAtivacao {
        val licenca = LicenseVerifier.verificarEExtrair(conteudoArquivo) ?: return ResultadoAtivacao.AssinaturaInvalida
        if (licenca.deviceId != preferencias.deviceId) return ResultadoAtivacao.DispositivoNaoCorresponde
        if (licenca.expirada(Instant.now(), toleranciaDias = 0)) return ResultadoAtivacao.Expirada
        preferencias.licencaAtivada = conteudoArquivo
        return ResultadoAtivacao.Sucesso(licenca)
    }

    /** Revogação LOCAL (a revogação remota de verdade — item 13 —
     * exige o BETA-CLOUD consultável, que ainda não tem essas tabelas
     * — ver limitações do relatório). Isto só limpa a licença deste
     * aparelho, sem apagar nenhum outro dado (item do pedido: "não
     * apagar dados locais"). */
    fun revogarLocal() {
        preferencias.licencaAtivada = null
    }
}
