"""Aviso no celular com o app fechado (Web Push: RFC 8291 aes128gcm + VAPID RFC 8292).

Precisa do pacote `cryptography` (vem na versão da internet). Sem ele, o aviso no celular fica desligado e
o resto do sistema funciona normalmente (aviso dentro do app continua).
"""
from __future__ import annotations

import base64
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.hmac import HMAC
    DISPONIVEL = True
except ImportError:  # pragma: no cover
    DISPONIVEL = False


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def de_b64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hmac(chave: bytes, dados: bytes) -> bytes:
    h = HMAC(chave, hashes.SHA256())
    h.update(dados)
    return h.finalize()


def _hkdf(sal: bytes, ikm: bytes, info: bytes, tam: int) -> bytes:
    prk = _hmac(sal, ikm)
    return _hmac(prk, info + b"\x01")[:tam]


def novas_chaves_vapid() -> tuple[str, str]:
    """Devolve (privada PEM, pública base64url sem compressão)."""
    priv = ec.generate_private_key(ec.SECP256R1())
    pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    pub = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return pem, b64u(pub)


def cifrar(mensagem: bytes, p256dh: str, auth: str) -> bytes:
    ua_pub = de_b64u(p256dh)
    segredo_auth = de_b64u(auth)
    as_priv = ec.generate_private_key(ec.SECP256R1())
    as_pub = as_priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ecdh = as_priv.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hkdf(segredo_auth, ecdh, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    sal = os.urandom(16)
    cek = _hkdf(sal, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(sal, ikm, b"Content-Encoding: nonce\x00", 12)
    cifrado = AESGCM(cek).encrypt(nonce, mensagem + b"\x02", None)
    return sal + struct.pack("!I", 4096) + bytes([len(as_pub)]) + as_pub + cifrado


def _jwt_vapid(endpoint: str, pem: str, contato: str) -> str:
    u = urllib.parse.urlparse(endpoint)
    cab = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    corpo = b64u(json.dumps({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": contato}).encode())
    priv = serialization.load_pem_private_key(pem.encode(), None)
    r, s = decode_dss_signature(priv.sign(f"{cab}.{corpo}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{cab}.{corpo}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def enviar(inscricao: dict, dados: dict, pem: str, publica: str, contato: str = "mailto:contato@sobrou.plus", enviador=None) -> int:
    """Envia um aviso. Devolve o status HTTP (201 = entregue ao serviço de push; 404/410 = inscrição vencida)."""
    corpo = cifrar(json.dumps(dados, ensure_ascii=False).encode(), inscricao["p256dh"], inscricao["auth"])
    cab = {"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": "86400", "Urgency": "high",
           "Authorization": f"vapid t={_jwt_vapid(inscricao['endpoint'], pem, contato)}, k={publica}"}
    if enviador:
        return enviador(inscricao["endpoint"], corpo, cab)
    req = urllib.request.Request(inscricao["endpoint"], data=corpo, method="POST", headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return 0
