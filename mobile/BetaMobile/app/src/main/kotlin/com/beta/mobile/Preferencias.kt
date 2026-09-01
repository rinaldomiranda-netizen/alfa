package com.beta.mobile

import android.content.Context
import com.beta.mobile.avatar.PerfilDesempenho
import java.util.UUID

enum class ModoBeta { DISCRETO, APLICATIVO, TOTEM }
enum class TamanhoFonte { PEQUENA, MEDIA, GRANDE }

/** Preferências locais simples (SharedPreferences) — modo de uso e
 * ajustes de acessibilidade escolhidos pela pessoa, nunca dado de
 * conversa nem biometria. */
class Preferencias(context: Context) {
    private val prefs = context.getSharedPreferences("beta_prefs", Context.MODE_PRIVATE)

    var modo: ModoBeta?
        get() = prefs.getString("modo", null)?.let { runCatching { ModoBeta.valueOf(it) }.getOrNull() }
        set(valor) = prefs.edit().putString("modo", valor?.name).apply()

    var tamanhoFonte: TamanhoFonte
        get() = prefs.getString("tamanho_fonte", null)?.let { runCatching { TamanhoFonte.valueOf(it) }.getOrNull() }
            ?: TamanhoFonte.MEDIA
        set(valor) = prefs.edit().putString("tamanho_fonte", valor.name).apply()

    var altoContraste: Boolean
        get() = prefs.getBoolean("alto_contraste", false)
        set(valor) = prefs.edit().putBoolean("alto_contraste", valor).apply()

    /** Duração da tela de apresentação (Splash), em milissegundos —
     * configurável (item 1 do pedido de identidade de abertura), não
     * fixa no código em três lugares diferentes. */
    var duracaoSplashMs: Long
        get() = prefs.getLong("duracao_splash_ms", DURACAO_SPLASH_PADRAO_MS)
        set(valor) = prefs.edit().putLong("duracao_splash_ms", valor).apply()

    /** Nome da voz do TTS escolhida (null = voz padrão do motor). */
    var vozSelecionada: String?
        get() = prefs.getString("voz_selecionada", null)
        set(valor) = prefs.edit().putString("voz_selecionada", valor).apply()

    /** Perfil de desempenho da animação do avatar (item de
     * performance) — padrão BALANCEADO. */
    var perfilDesempenho: PerfilDesempenho
        get() = prefs.getString("perfil_desempenho", null)
            ?.let { runCatching { PerfilDesempenho.valueOf(it) }.getOrNull() }
            ?: PerfilDesempenho.BALANCEADO
        set(valor) = prefs.edit().putString("perfil_desempenho", valor.name).apply()

    /** Velocidade e tom da voz do TTS (1.0 = padrão do motor). */
    var velocidadeVoz: Float
        get() = prefs.getFloat("velocidade_voz", 1.0f)
        set(valor) = prefs.edit().putFloat("velocidade_voz", valor).apply()

    var tomVoz: Float
        get() = prefs.getFloat("tom_voz", 1.0f)
        set(valor) = prefs.edit().putFloat("tom_voz", valor).apply()

    /** PIN administrativo do Totem público (item do pedido: "painel
     * acessível somente ao responsável... PIN/autenticação"). Padrão
     * "1234" — SEMPRE mude antes de usar em produção real; muda-se em
     * Configurações. Nunca é enviado a lugar nenhum, fica só neste
     * aparelho. */
    var pinAdministrativo: String
        get() = prefs.getString("pin_administrativo", null) ?: "1234"
        set(valor) = prefs.edit().putString("pin_administrativo", valor).apply()

    /** PIN do segundo nível (DEVELOPER) — SEPARADO do PIN de
     * manutenção do operador (item do pedido: "OPERATOR nunca vira
     * DEVELOPER somente com o PIN operacional"). Padrão "9999",
     * diferente do padrão do operador de propósito. */
    var pinDesenvolvedor: String
        get() = prefs.getString("pin_desenvolvedor", null) ?: "9999"
        set(valor) = prefs.edit().putString("pin_desenvolvedor", valor).apply()

    /** Tempo de inatividade dentro do Modo de Manutenção antes de
     * voltar sozinho pro Totem público (item do pedido: "timeout
     * configurável"). Padrão 60s. */
    var timeoutManutencaoMs: Long
        get() = prefs.getLong("timeout_manutencao_ms", TIMEOUT_MANUTENCAO_PADRAO_MS)
        set(valor) = prefs.edit().putLong("timeout_manutencao_ms", valor).apply()

    /** Identidade deste APARELHO para o sistema de licenciamento (item
     * do pedido: "usar device_id já existente" — para mobile, esse
     * device_id ainda não existia antes desta entrega, então é gerado
     * UMA VEZ aqui e nunca muda depois, mesmo reinstalando o app com
     * `adb install -r` — só muda se os dados do app forem apagados ou
     * o app copiado "do zero" para outro aparelho, que é exatamente o
     * comportamento pedido). */
    var deviceId: String
        get() {
            val existente = prefs.getString("device_id", null)
            if (existente != null) return existente
            val novo = UUID.randomUUID().toString()
            prefs.edit().putString("device_id", novo).apply()
            return novo
        }
        private set(valor) = prefs.edit().putString("device_id", valor).apply()

    /** Licença local ativada (o arquivo .beta-license de 2 linhas
     * inteiro, ver licensing/LicenseVerifier.kt) — null = nenhuma
     * licença ativada (modo DEMO, ver GerenciadorLicenca). */
    var licencaAtivada: String?
        get() = prefs.getString("licenca_ativada", null)
        set(valor) = prefs.edit().putString("licenca_ativada", valor).apply()

    /** Credencial do BETA_OWNER — NUNCA em texto puro (item do pedido).
     * Guardada como hash PBKDF2 + salt (ver
     * licensing/CredencialProprietario.kt). Padrão vazio = usa a senha
     * de fábrica só na primeira vez (ver GerenciadorLicenca). */
    var senhaProprietarioHash: String?
        get() = prefs.getString("senha_proprietario_hash", null)
        set(valor) = prefs.edit().putString("senha_proprietario_hash", valor).apply()

    var senhaProprietarioSal: String?
        get() = prefs.getString("senha_proprietario_sal", null)
        set(valor) = prefs.edit().putString("senha_proprietario_sal", valor).apply()

    companion object {
        const val DURACAO_SPLASH_PADRAO_MS = 3000L
        const val TIMEOUT_MANUTENCAO_PADRAO_MS = 60_000L
    }
}
