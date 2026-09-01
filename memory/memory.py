"""
Armazenamento local dos dados de atendimento da BETA.

Princípios de privacidade:
  - Tudo fica em disco local (memory/atendimentos/), nunca é enviado
    a um serviço externo automaticamente.
  - Uma foto só chega a este armazenamento depois que
    vision/camera.py já garantiu consentimento + confirmação da
    prévia (ver SessaoCamera.associar_ao_atendimento) — este módulo
    não sabe capturar fotos, só guardar o que já foi aprovado.
  - Um atendimento pode ser apagado explicitamente (limpar_atendimento)
    a qualquer momento — nada fica retido "por padrão".
"""

import json
import os
import uuid
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_ATENDIMENTOS = os.path.join(BASE, "atendimentos")


def definir_pasta_atendimentos(caminho):
    """
    Redireciona o armazenamento para `caminho` — usado pelo launcher
    portátil (ver launcher/iniciar_portatil.py) para isolar a memória
    de cada perfil por computador/usuário. Ninguém chama isto no
    caminho do ALFA pessoal (main.py), então PASTA_ATENDIMENTOS
    continua sendo memory/atendimentos/ exatamente como sempre foi —
    zero mudança de comportamento para quem não usa o portátil.
    """
    global PASTA_ATENDIMENTOS
    PASTA_ATENDIMENTOS = caminho
    os.makedirs(caminho, exist_ok=True)


def novo_id_atendimento():
    return datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]


def salvar_atendimento(atendimento_id, dados):
    """
    Salva as respostas de um atendimento em um JSON local.

    `dados` é um dict simples {campo: valor}; não deve conter caminho
    de foto a menos que vision/camera.py já tenha confirmado
    consentimento — essa verificação é responsabilidade de quem monta
    `dados` (tipicamente core/atendimento.py).
    """
    os.makedirs(PASTA_ATENDIMENTOS, exist_ok=True)
    caminho = os.path.join(PASTA_ATENDIMENTOS, f"{atendimento_id}.json")

    registro = {
        "id": atendimento_id,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "dados": dados,
    }

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(registro, arquivo, ensure_ascii=False, indent=2)

    return caminho


def carregar_atendimento(atendimento_id):
    caminho = os.path.join(PASTA_ATENDIMENTOS, f"{atendimento_id}.json")
    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def limpar_atendimento(atendimento_id):
    """Remove os dados (e a foto, se existir) de um atendimento."""
    removido = False

    caminho_json = os.path.join(PASTA_ATENDIMENTOS, f"{atendimento_id}.json")
    if os.path.exists(caminho_json):
        os.remove(caminho_json)
        removido = True

    caminho_foto = os.path.join(PASTA_ATENDIMENTOS, f"{atendimento_id}_foto.jpg")
    if os.path.exists(caminho_foto):
        os.remove(caminho_foto)
        removido = True

    return removido


def listar_atendimentos():
    if not os.path.isdir(PASTA_ATENDIMENTOS):
        return []
    return sorted(
        nome[:-5] for nome in os.listdir(PASTA_ATENDIMENTOS) if nome.endswith(".json")
    )
