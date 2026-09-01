"""
Identidade do DISPOSITIVO (esta instalação da BETA) — item 5 da
conexão ao BETA-CLOUD: cada instalação precisa de um identificador
próprio, NUNCA o nome do usuário, para um futuro BETA-CLOUD conseguir
distinguir "qual computador/terminal" gerou um evento sem depender de
quem está falando com a Beta no momento.

Gerado uma única vez por instalação/perfil (persistido em disco) —
sobrevive a reinícios; nunca é regenerado se o arquivo já existir
(nunca troca o device_id de uma instalação já em uso, o que quebraria
o histórico de sincronização dela).
"""

import json
import os
import platform
import time
import uuid

from core.version import COMPONENTES

NOME_ARQUIVO_PADRAO = "device.json"


def _caminho_padrao():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", NOME_ARQUIVO_PADRAO)


def obter_ou_criar(caminho=None, perfil=None):
    """
    Retorna o registro do dispositivo: device_id, versão, sistema,
    perfil, última sincronização, status. Cria na primeira vez,
    reaproveita depois. `caminho`, se fornecido, isola por perfil (ver
    launcher/iniciar_portatil.py) — o mesmo princípio de
    memory.definir_pasta_atendimentos.
    """
    caminho = caminho or _caminho_padrao()

    if os.path.isfile(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                registro = json.load(arquivo)
            if perfil is not None and registro.get("perfil") != perfil:
                registro["perfil"] = perfil
                _salvar(registro, caminho)
            return registro
        except Exception:
            pass

    registro = {
        # Formato uuid com hífens (str(uuid4()), não .hex) — compatível
        # com a coluna `device_key`/`id` tipo uuid do BETA-CLOUD real
        # (ver memory/beta_cloud_client.py).
        "device_id": str(uuid.uuid4()),
        "versao": COMPONENTES["core"],
        "sistema": f"{platform.system()} {platform.release()}",
        "perfil": perfil,
        "ultima_sincronizacao": None,
        "status": "novo",
    }
    _salvar(registro, caminho)
    return registro


def _salvar(registro, caminho=None):
    caminho = caminho or _caminho_padrao()
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(registro, arquivo, ensure_ascii=False, indent=2)


def marcar_sincronizado(caminho=None):
    caminho = caminho or _caminho_padrao()
    registro = obter_ou_criar(caminho)
    registro["ultima_sincronizacao"] = time.time()
    registro["status"] = "sincronizado"
    _salvar(registro, caminho)
    return registro
