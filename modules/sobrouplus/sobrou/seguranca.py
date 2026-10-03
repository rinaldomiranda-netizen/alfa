"""Segurança — COPIADO de ALFA/modules/atendimento/plataforma/seguranca.py (RMD Atendimento, testado em produção).
Adaptado para o Sobrou+: prefixo das chaves "sob_". Nada foi alterado no original."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

ITERACOES = 200_000
DURACAO_SESSAO_HORAS = 12
LIMITE_TENTATIVAS = 5
BLOQUEIO_BASE = 30
BLOQUEIO_MAXIMO = 15 * 60
TAMANHO_MINIMO_SENHA = 8


class SenhaFraca(ValueError):
    pass


def gerar_salt() -> str:
    return secrets.token_hex(16)


def hash_senha(senha: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", (senha or "").encode("utf-8"), bytes.fromhex(salt_hex), ITERACOES).hex()


def conferir_senha(senha: str, salt_hex: str, hash_esperado: str) -> bool:
    return hmac.compare_digest(hash_senha(senha, salt_hex), hash_esperado)


def validar_senha_nova(senha: str) -> None:
    if not senha or len(senha) < TAMANHO_MINIMO_SENHA:
        raise SenhaFraca(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")
    if senha.isdigit() or senha.isalpha():
        raise SenhaFraca("Use letras e números na senha.")


def gerar_senha_temporaria() -> str:
    alfabeto = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(10)) + str(secrets.randbelow(10))


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def novo_token() -> str:
    return secrets.token_urlsafe(32)


def expiracao_sessao() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=DURACAO_SESSAO_HORAS)).isoformat(timespec="seconds")


def duracao_bloqueio(falhas: int) -> int:
    if falhas < LIMITE_TENTATIVAS:
        return 0
    return min(BLOQUEIO_BASE * (2 ** (falhas - LIMITE_TENTATIVAS)), BLOQUEIO_MAXIMO)


# --- Chaves da API pública --------------------------------------------------

def nova_chave_api() -> tuple[str, str, str]:
    """Devolve (chave_completa, prefixo, hash). A chave completa só é
    mostrada uma vez, na criação."""
    prefixo = "sob_" + secrets.token_hex(4)
    segredo = secrets.token_urlsafe(24)
    chave = f"{prefixo}.{segredo}"
    return chave, prefixo, hash_token(chave)


def separar_prefixo(chave: str) -> str | None:
    if not chave or "." not in chave or not chave.startswith("sob_"):
        return None
    return chave.split(".", 1)[0]


# --- Tokens de uso único (abrir o Atendimento a partir do ALFA) --------------

_TOKENS_UNICOS: dict[str, tuple[str, str | None, float]] = {}
_LOCK_TOKENS = threading.Lock()
VALIDADE_TOKEN_UNICO = 90


def criar_token_unico(usuario_id: str, empresa_id: str | None) -> str:
    token = secrets.token_urlsafe(24)
    with _LOCK_TOKENS:
        agora = time.time()
        for chave, (_u, _e, expira) in list(_TOKENS_UNICOS.items()):
            if expira < agora:
                _TOKENS_UNICOS.pop(chave, None)
        _TOKENS_UNICOS[hash_token(token)] = (usuario_id, empresa_id, agora + VALIDADE_TOKEN_UNICO)
    return token


def consumir_token_unico(token: str) -> tuple[str, str | None] | None:
    with _LOCK_TOKENS:
        registro = _TOKENS_UNICOS.pop(hash_token(token), None)
    if not registro or registro[2] < time.time():
        return None
    return registro[0], registro[1]


# --- Limite de chamadas (API pública) ---------------------------------------

class LimiteChamadas:
    def __init__(self, por_minuto: int = 60):
        self.por_minuto = por_minuto
        self._janelas: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def permitir(self, chave: str) -> bool:
        agora = time.time()
        with self._lock:
            janela = [t for t in self._janelas.get(chave, []) if agora - t < 60]
            if len(janela) >= self.por_minuto:
                self._janelas[chave] = janela
                return False
            janela.append(agora)
            self._janelas[chave] = janela
            return True


# --- Verificação em duas etapas (código de 6 números do celular) -------------
# Padrão TOTP (RFC 6238), o mesmo do Google Authenticator, Microsoft
# Authenticator e similares. Só biblioteca padrão do Python.

import base64 as _base64
import struct as _struct

TOTP_PASSO = 30
TOTP_DIGITOS = 6


def gerar_segredo_totp() -> str:
    return _base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _chave_totp(segredo: str) -> bytes:
    limpo = (segredo or "").replace(" ", "").upper()
    return _base64.b32decode(limpo + "=" * (-len(limpo) % 8))


def codigo_totp(segredo: str, contador: int) -> str:
    resumo = hmac.new(_chave_totp(segredo), _struct.pack(">Q", contador), hashlib.sha1).digest()
    deslocamento = resumo[-1] & 0x0F
    numero = _struct.unpack(">I", resumo[deslocamento:deslocamento + 4])[0] & 0x7FFFFFFF
    return str(numero % (10 ** TOTP_DIGITOS)).zfill(TOTP_DIGITOS)


def conferir_totp(segredo: str, codigo: str, ultimo_usado: int | None = None, agora_s: float | None = None) -> int | None:
    """Devolve o contador aceito (para impedir reuso do mesmo código) ou None.
    Aceita o código do intervalo atual e de um intervalo antes/depois (relógio do celular um pouco diferente)."""
    codigo = "".join(ch for ch in str(codigo or "") if ch.isdigit())
    if len(codigo) != TOTP_DIGITOS or not segredo:
        return None
    atual = int((agora_s if agora_s is not None else time.time()) // TOTP_PASSO)
    for contador in (atual, atual - 1, atual + 1):
        if ultimo_usado is not None and contador <= ultimo_usado:
            continue
        if hmac.compare_digest(codigo_totp(segredo, contador), codigo):
            return contador
    return None


def endereco_totp(segredo: str, email: str, emissor: str) -> str:
    from urllib.parse import quote
    return (f"otpauth://totp/{quote(emissor)}:{quote(email)}?secret={segredo}&issuer={quote(emissor)}"
            f"&algorithm=SHA1&digits={TOTP_DIGITOS}&period={TOTP_PASSO}")
