package com.beta.mobile.licensing

import android.util.Base64
import java.security.KeyFactory
import java.security.PublicKey
import java.security.Signature
import java.security.spec.X509EncodedKeySpec

/**
 * Verifica a assinatura digital de uma licença local (item do pedido:
 * "a licença deve possuir assinatura digital... BETA instalada:
 * somente chave pública"). A chave PRIVADA correspondente nunca
 * existiu neste projeto de app — ela foi gerada e fica só em
 * `licensing_tools/beta_owner_private_key.pem`, fora de
 * mobile/BetaMobile, nunca compilada no APK (ver LEIAME dessa pasta).
 *
 * Formato do arquivo .beta-license (2 linhas, UTF-8):
 *   linha 1 — corpo da licença em JSON (uma linha só, é isto que foi
 *             assinado, byte a byte, sem re-serializar)
 *   linha 2 — assinatura RSA-SHA256 (PKCS#1 v1.5) do corpo, em base64
 */
object LicenseVerifier {
    // Chave PÚBLICA real (RSA 2048), gerada nesta sessão — corresponde
    // à privada em licensing_tools/beta_owner_private_key.pem. Não é
    // segredo: só serve para VERIFICAR, nunca para assinar.
    private const val CHAVE_PUBLICA_PEM = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA43qM/DipBSoLR3zzb3UR
8UxvbmpfbteYjzHciVlb470DS4zqRkaoILkXdJNXWL0Tn02RVr/3WXuLHxhrZbTe
G7QkslH2tyVTZM+0GPzF95Lmm0jDLEYu/Vu+8+ZFdLKu3EelAJsV87fPeiA0YZyY
XfLutAMX3pc2J9CjrRqBtGi3k+ySP4+013Xx40cxQR+WIxAswHAR7uZzydXPBttl
X2/A7U7Oa/7Ub/Aozm7rxYNckizNYnKsWxSHrk/7vhwksV/7/caLFGSTpXOrxbTE
504iosKT6eKSbuvCgVffr+ptQ01Nb+MKrTFhr+hNqs/GTuoSrLn/Fu/CtmRYlmob
kwIDAQAB
-----END PUBLIC KEY-----
"""

    private val chavePublica: PublicKey by lazy {
        val limpo = CHAVE_PUBLICA_PEM
            .replace("-----BEGIN PUBLIC KEY-----", "")
            .replace("-----END PUBLIC KEY-----", "")
            .replace("\\s".toRegex(), "")
        val bytes = Base64.decode(limpo, Base64.DEFAULT)
        KeyFactory.getInstance("RSA").generatePublic(X509EncodedKeySpec(bytes))
    }

    /** Verifica o arquivo .beta-license inteiro (2 linhas). Retorna a
     * Licenca só se a assinatura bater — nunca confia no corpo antes
     * de verificar. */
    fun verificarEExtrair(conteudoArquivo: String): Licenca? {
        val linhas = conteudoArquivo.trim().lines()
        if (linhas.size < 2) return null
        val corpo = linhas[0]
        val assinaturaBase64 = linhas[1]

        val assinaturaValida = try {
            val assinatura = Signature.getInstance("SHA256withRSA")
            assinatura.initVerify(chavePublica)
            assinatura.update(corpo.toByteArray(Charsets.UTF_8))
            assinatura.verify(Base64.decode(assinaturaBase64, Base64.DEFAULT))
        } catch (e: Exception) {
            false
        }
        if (!assinaturaValida) return null
        return Licenca.deJson(corpo)
    }
}
