"""Segurança — COPIADO de ALFA/modules/atendimento/plataforma/seguranca.py (RMD Atendimento, testado em produção).
Adaptado para o Sobrou+: prefixo das chaves "sob_". Nada foi alterado no original."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

ITERACOES = 600_000
DURACAO_SESSAO_HORAS = 8
LIMITE_TENTATIVAS = 5
BLOQUEIO_BASE = 30
BLOQUEIO_MAXIMO = 15 * 60
TAMANHO_MINIMO_SENHA = 8


class SenhaFraca(ValueError):
    pass


def gerar_salt() -> str:
    return secrets.token_hex(16)


def hash_senha(senha: str, salt_hex: str, iteracoes: int = ITERACOES) -> str:
    return hashlib.pbkdf2_hmac("sha256", (senha or "").encode("utf-8"), bytes.fromhex(salt_hex), int(iteracoes)).hex()


def conferir_senha(senha: str, salt_hex: str, hash_esperado: str, iteracoes: int = ITERACOES) -> bool:
    return hmac.compare_digest(hash_senha(senha, salt_hex, iteracoes), hash_esperado)


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
            if len(self._janelas) > 2000:
                # limpeza: não deixa a lista crescer sem parar (memória do servidor)
                self._janelas = {k: v for k, v in self._janelas.items() if v and agora - v[-1] < 60}
            janela = [t for t in self._janelas.get(chave, []) if agora - t < 60]
            if len(janela) >= self.por_minuto:
                self._janelas[chave] = janela
                return False
            janela.append(agora)
            self._janelas[chave] = janela
            return True


class BloqueioFalhas:
    """Conta erros por chave (ex.: e-mail + IP, ou uma corrida) e bloqueia por um tempo crescente.

    Fica na memória: um atacante consegue bloquear só a própria tentativa (o próprio IP),
    nunca o acesso do dono vindo de outro lugar."""

    def __init__(self, limite: int = LIMITE_TENTATIVAS, base: int = BLOQUEIO_BASE, maximo: int = BLOQUEIO_MAXIMO,
                 esquecer_apos: int = 3600):
        self.limite, self.base, self.maximo, self.esquecer_apos = limite, base, maximo, esquecer_apos
        self._dados: dict[str, list[float]] = {}  # chave -> [falhas, bloqueado_ate, ultima_falha]
        self._lock = threading.Lock()

    def _limpar(self, agora: float) -> None:
        if len(self._dados) > 5000:
            self._dados = {k: v for k, v in self._dados.items() if agora - v[2] < self.esquecer_apos}

    def bloqueado(self, chave: str) -> bool:
        agora = time.time()
        with self._lock:
            d = self._dados.get(chave)
            if d and agora - d[2] >= self.esquecer_apos:
                self._dados.pop(chave, None)
                return False
            return bool(d) and d[1] > agora

    def falhou(self, chave: str) -> None:
        agora = time.time()
        with self._lock:
            self._limpar(agora)
            d = self._dados.get(chave)
            if not d or agora - d[2] >= self.esquecer_apos:
                d = [0, 0.0, agora]
            d[0] += 1
            d[2] = agora
            if d[0] >= self.limite:
                d[1] = agora + min(self.base * (2 ** (d[0] - self.limite)), self.maximo)
            self._dados[chave] = d

    def sucesso(self, chave: str) -> None:
        with self._lock:
            self._dados.pop(chave, None)


FALHAS_LOGIN = BloqueioFalhas()
FALHAS_CODIGO = BloqueioFalhas(limite=5, base=15 * 60, maximo=60 * 60)    # código de 4 dígitos da entrega
FALHAS_RETIRADA = BloqueioFalhas(limite=15, base=60, maximo=15 * 60)      # balcão: erros de digitação são normais
SAL_FALSO = gerar_salt()


def gastar_tempo_de_senha(senha: str) -> None:
    """Mesmo custo de conferir uma senha real, para não revelar se o e-mail existe."""
    hash_senha(senha or "", SAL_FALSO)


# --- Guardar segredos (tokens de WhatsApp/e-mail) protegidos -----------------
# No Windows usa a proteção do próprio Windows (DPAPI): só esta conta deste
# computador consegue abrir. Assim, um backup copiado não revela os tokens.

import base64 as _b64
import ipaddress as _ipaddress
import os as _os
import socket as _socket
from urllib.parse import urlparse as _urlparse

PREFIXO_PROTEGIDO = "dpapi:"


def _dpapi(dados: bytes, proteger: bool) -> bytes | None:
    if _os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        funcao = crypt32.CryptProtectData if proteger else crypt32.CryptUnprotectData
        funcao.argtypes = [ctypes.POINTER(BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(BLOB)]
        funcao.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        buf = ctypes.create_string_buffer(dados, len(dados))
        entrada = BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        saida = BLOB()
        if not funcao(ctypes.byref(entrada), None, None, None, None, 0x1, ctypes.byref(saida)):  # 0x1 = sem janela
            return None
        try:
            return ctypes.string_at(saida.pbData, saida.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(saida.pbData, ctypes.c_void_p))
    except Exception:  # qualquer falha do Windows: guarda como antes, sem derrubar o sistema
        return None


def proteger_segredo(valor: str) -> str:
    if not valor or valor.startswith(PREFIXO_PROTEGIDO):
        return valor
    cifrado = _dpapi(valor.encode("utf-8"), True)
    return PREFIXO_PROTEGIDO + _b64.b64encode(cifrado).decode("ascii") if cifrado else valor


def revelar_segredo(valor: str | None) -> str | None:
    if not valor or not str(valor).startswith(PREFIXO_PROTEGIDO):
        return valor
    try:
        claro = _dpapi(_b64.b64decode(str(valor)[len(PREFIXO_PROTEGIDO):]), False)
    except ValueError:
        claro = None
    return claro.decode("utf-8") if claro else None  # outro computador: precisa colar o token de novo


def segredo_protegido_disponivel() -> bool:
    return _os.name == "nt" and _dpapi(b"teste", True) is not None


# --- Endereços de serviços externos (mapas, e-mail) --------------------------
# Impede apontar o servidor para a rede interna (roteador, notebook, nuvem).

def host_externo_seguro(host: str) -> bool:
    host = (host or "").strip().strip("[]").lower()
    if not host or host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        return False
    try:
        enderecos = {i[4][0] for i in _socket.getaddrinfo(host, None)}
    except (OSError, UnicodeError):
        return True  # nome que não existe: não leva a lugar nenhum (nem à rede interna)
    for e in enderecos:
        ip = _ipaddress.ip_address(e.split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    return bool(enderecos)


def url_externa_segura(url: str) -> bool:
    try:
        u = _urlparse((url or "").strip())
    except ValueError:
        return False
    return u.scheme == "https" and not u.username and not u.password and host_externo_seguro(u.hostname or "")


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
