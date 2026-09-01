package com.beta.mobile.licensing

import android.util.Base64
import java.security.SecureRandom
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * Guarda a senha do BETA_OWNER como hash PBKDF2 + sal (item do
 * pedido: "não armazenar em texto puro") — nunca a senha em si.
 * PBKDF2WithHmacSHA256 já vem no próprio Android, sem dependência
 * nova, e é adequado para uma senha local de dispositivo (não é o
 * mesmo cenário de uma tabela de senhas de milhões de usuários, onde
 * Argon2/scrypt seriam preferíveis).
 */
object CredencialProprietario {
    private const val ITERACOES = 120_000
    private const val TAMANHO_CHAVE_BITS = 256

    fun gerarSal(): String {
        val bytes = ByteArray(16)
        SecureRandom().nextBytes(bytes)
        return Base64.encodeToString(bytes, Base64.NO_WRAP)
    }

    fun hash(senha: String, salBase64: String): String {
        val sal = Base64.decode(salBase64, Base64.NO_WRAP)
        val spec = PBEKeySpec(senha.toCharArray(), sal, ITERACOES, TAMANHO_CHAVE_BITS)
        val chave = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        return Base64.encodeToString(chave, Base64.NO_WRAP)
    }

    fun confere(senhaDigitada: String, salBase64: String, hashEsperado: String): Boolean =
        hash(senhaDigitada, salBase64) == hashEsperado
}
