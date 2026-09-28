"""Integração opcional com o WhatsApp Business Platform (Meta Cloud API).

Sem nenhuma configuração, esta integração fica completamente desligada e
nada muda no funcionamento do módulo — o atendimento por WhatsApp continua
registrado normalmente como sempre foi, só que sem envio/recebimento
automático de verdade pelo número oficial da igreja.

Para ligar de verdade, é preciso ter uma conta própria no Meta for
Developers com um número do WhatsApp Business verificado — isso quem cria
é você mesmo (envolve aceitar os termos e possíveis custos do Meta; este
código nunca cria contas nem lida com pagamentos). Com a conta pronta,
defina no `.env` do ALFA:

    WHATSAPP_TOKEN               token de acesso do app da Meta
    WHATSAPP_PHONE_NUMBER_ID     ID do número de telefone (painel da Meta)
    WHATSAPP_VERIFY_TOKEN        uma palavra qualquer que você escolhe,
                                   usada só para a Meta confirmar o
                                   endereço do webhook (não é segredo de
                                   um serviço externo, é você quem inventa)
    WHATSAPP_APP_SECRET          opcional; camada extra de segurança que
                                   confere se as mensagens recebidas vêm
                                   mesmo da Meta (App Settings > Basic)

No painel da Meta (WhatsApp > Configuration > Webhook), cadastre:
    URL de callback: https://SEU-DOMINIO/api/whatsapp/webhook?igreja=<id>
    Token de verificação: o mesmo valor de WHATSAPP_VERIFY_TOKEN
    Campo (fields) a assinar: messages
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - requests já é usado em outros módulos
    requests = None

_GRAPH_VERSAO = "v21.0"


def configurado() -> bool:
    """True quando há token e ID de número suficientes para ENVIAR mensagens."""
    return bool(
        os.environ.get("WHATSAPP_TOKEN")
        and os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        and requests is not None
    )


def verificar_webhook(parametros: dict[str, str]) -> str | None:
    """Confirma o desafio de verificação da Meta (GET do webhook).

    Retorna o valor de "hub.challenge" quando o modo e o token batem com
    WHATSAPP_VERIFY_TOKEN, ou None quando a chamada não deve ser aceita
    (inclusive quando WHATSAPP_VERIFY_TOKEN não está configurado).
    """
    esperado = os.environ.get("WHATSAPP_VERIFY_TOKEN") or ""
    if not esperado:
        return None
    if parametros.get("hub.mode") != "subscribe":
        return None
    if parametros.get("hub.verify_token") != esperado:
        return None
    return parametros.get("hub.challenge")


def assinatura_valida(corpo_bruto: bytes, assinatura_recebida: str | None) -> bool:
    """Confere a assinatura X-Hub-Signature-256 enviada pela Meta.

    Sem WHATSAPP_APP_SECRET definido, não há como conferir e a função
    aceita a chamada normalmente (mesmo comportamento de antes dessa
    camada extra existir) — configure o app secret para essa proteção.
    """
    segredo = os.environ.get("WHATSAPP_APP_SECRET") or ""
    if not segredo:
        return True
    if not assinatura_recebida or not assinatura_recebida.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode("utf-8"), corpo_bruto, hashlib.sha256).hexdigest()
    recebido = assinatura_recebida.split("=", 1)[1]
    return hmac.compare_digest(esperado, recebido)


def extrair_mensagem_recebida(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai {telefone, nome, texto} de um payload de webhook da Meta.

    Retorna None quando o payload não é uma mensagem de texto recebida
    (por exemplo, é só uma confirmação de entrega/leitura, ou veio
    malformado).
    """
    try:
        entrada = payload["entry"][0]["changes"][0]["value"]
        mensagens = entrada.get("messages")
        if not mensagens:
            return None
        msg = mensagens[0]
        if msg.get("type") != "text":
            return None
        telefone = msg.get("from") or ""
        texto = (msg.get("text") or {}).get("body") or ""
        contatos = entrada.get("contacts") or [{}]
        nome = (contatos[0].get("profile") or {}).get("name") or telefone
        if not telefone or not texto:
            return None
        return {"telefone": telefone, "nome": nome, "texto": texto}
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def enviar_mensagem(telefone: str, texto: str) -> bool:
    """Envia uma mensagem de texto pelo WhatsApp. Nunca levanta exceção.

    Retorna False (sem quebrar o atendimento) quando a integração não
    está configurada ou o envio falha por qualquer motivo — a mensagem
    já foi salva na conversa de qualquer forma, só o envio real que não
    aconteceu.
    """
    if not configurado():
        return False
    token = os.environ["WHATSAPP_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    url = f"https://graph.facebook.com/{_GRAPH_VERSAO}/{phone_id}/messages"
    corpo = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto},
    }
    try:
        resposta = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=corpo,
            timeout=8.0,
        )
        return bool(resposta.ok)
    except Exception:
        return False
