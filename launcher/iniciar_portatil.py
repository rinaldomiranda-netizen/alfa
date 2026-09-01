"""
Launcher da BETA PORTÁTIL.

Mesmo núcleo do projeto ALFA/BETA (core/, agente/, voice/, vision/,
skills/, security/, ui/) — NADA aqui é duplicado. Este arquivo só
resolve QUAL configuração e QUAL armazenamento usar antes de chamar
core.alfa_core.AlfaCore exatamente como main.py já faz para o ALFA
pessoal.

ISOLAMENTO POR PERFIL: cada pessoa/organização que usa o portátil tem
sua PRÓPRIA pasta (config, memória e workspace) — nunca compartilha
com outro perfil nem com o ALFA pessoal de Rinaldo (main.py nunca
chama nada deste arquivo, e este arquivo nunca lê config/alfa.json).

    config/local/<slug>/perfil.json   configuração daquele perfil
    memory/portatil/<slug>/           atendimentos daquele perfil
    workspace/<slug>/                 arquivos de trabalho daquele perfil

`<slug>` vem do nome falado (nunca do hostname nem de hardware — ver
_slug()), então é portátil de verdade: o mesmo pendrive num
computador diferente cria a mesma pasta pelo mesmo nome.

Uso:
    python launcher/iniciar_portatil.py
"""

import copy
import json
import os
import re
import sys
import unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

PASTA_LOCAL = os.path.join(BASE, "config", "local")
PASTA_MEMORIA_PORTATIL = os.path.join(BASE, "memory", "portatil")
PASTA_WORKSPACE = os.path.join(BASE, "workspace")


def _slug(texto):
    """Nome de pasta seguro a partir de um nome falado — sem acento,
    minúsculo, só letras/números/underscore. Nunca usa hostname nem
    caminho de outra pessoa/máquina."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "usuario"


def _detectar_ambiente_portatil():
    """Reaproveita agente/ambiente.py — a MESMA descoberta usada pelo
    ALFA pessoal (ver core/alfa_core.py), sem lógica nova."""
    from agente.ambiente import classificar_hardware, detectar_ambiente

    ambiente = detectar_ambiente()
    ambiente["perfil_hardware"] = classificar_hardware(ambiente)
    return ambiente


def _perguntar_identidade():
    """
    Pergunta por voz se é uso pessoal ou de uma empresa/organização, e
    o nome correspondente — reaproveita os MESMOS motores de voz do
    núcleo (nenhum TTS/STT novo). Retorna (tipo, nome), tipo em
    ("pessoa", "organizacao").
    """
    from voice.voice_engine import VoiceEngine
    from voice.voice_output import VoiceOutput

    voice_output = VoiceOutput(motor="edge_tts", motor_fallback="pyttsx3")
    voice_engine = VoiceEngine()

    voice_output.falar("Olá! Você está usando a Beta para uso pessoal ou para uma empresa?", "saudacao")
    resposta_tipo, _motor = voice_engine.listen()
    resposta_tipo = (resposta_tipo or "").strip().lower()
    eh_organizacao = any(
        palavra in resposta_tipo
        for palavra in ("empresa", "organizacao", "organização", "trabalho", "profissional", "companhia")
    )

    if eh_organizacao:
        voice_output.falar("Qual é o nome da empresa ou organização?", "confirmacao")
        nome, _motor = voice_engine.listen()
        nome = (nome or "").strip().title() or "Organização"
        voice_output.falar(f"Certo, configurando para {nome}.", "confirmacao")
        return "organizacao", nome

    voice_output.falar("Com quem estou falando?", "confirmacao")
    nome, _motor = voice_engine.listen()
    nome = (nome or "").strip().title() or "Usuário"
    voice_output.falar(f"Prazer, {nome}. Vou me preparar para você.", "confirmacao")
    return "pessoa", nome


def _perguntar_ativar_reconhecimento_facial():
    """
    Reconhecimento facial (ver vision/face_identity.py) começa
    DESATIVADO no portátil — só no primeiro uso deste perfil se
    pergunta se a pessoa quer ativar (item 13 do pedido de
    reconhecimento facial). Reaproveita os mesmos motores de voz.
    """
    from voice.voice_engine import VoiceEngine
    from voice.voice_output import VoiceOutput

    voice_output = VoiceOutput(motor="edge_tts", motor_fallback="pyttsx3")
    voice_engine = VoiceEngine()

    voice_output.falar(
        "Você quer ativar o reconhecimento facial neste computador? "
        "Isso é opcional e fica só neste perfil.",
        "confirmacao",
    )
    resposta, _motor = voice_engine.listen()
    resposta = (resposta or "").strip().lower()
    return any(palavra in resposta for palavra in ("sim", "quero", "ativar", "pode", "claro"))


def _construir_config_portatil(tipo, nome, ambiente, ativar_reconhecimento_facial):
    """Monta um config equivalente ao config/alfa.json, mas GENÉRICO —
    nunca herda nada do perfil pessoal de Rinaldo."""
    from core.alfa_core import CONFIG_PADRAO

    from core.perfil import construir_perfil

    config = copy.deepcopy(CONFIG_PADRAO)
    config["personalidade"]["nome_usuario"] = nome
    config["personalidade"]["nome_assistente"] = "Beta"
    # Estrutura organizacional (ver core/perfil.py) — filial/
    # departamento/cargo/terminal ficam None até serem configurados
    # manualmente no perfil.json deste computador (nunca perguntados
    # por voz nesta fase; "tudo deve ser configurável", não que TUDO
    # precise ser perguntado na primeira conversa).
    config["perfil"] = construir_perfil(tipo, nome)

    # Reconhecimento facial (ver vision/face_identity.py): desativado
    # por padrão no portátil, só liga se a pessoa pedir explicitamente
    # no primeiro uso (ver _perguntar_ativar_reconhecimento_facial).
    config["reconhecimento_facial"] = {"enabled": bool(ativar_reconhecimento_facial), "indice_camera": 0}

    # Perfil de hardware (agente/ambiente.py) decide só o modelo do
    # Whisper — nunca exige GPU nem modelo pesado.
    perfil_hw = ambiente.get("perfil_hardware", "eco")
    config["voz"]["modelo_whisper_fallback"] = "medium" if perfil_hw in ("avancado", "gpu") else "small"

    # IA de conversa livre só liga se Ollama já existir NESTA máquina.
    config["ia_fallback"]["ativo"] = bool(ambiente.get("ollama_disponivel"))

    # BETA-CLOUD (memory/sync.py) começa sempre desligada — nenhum
    # secret aqui; ligar exige configuração explícita por variável de
    # ambiente depois (ver .env.example). Nunca é o Supabase/
    # central-pesquisas do ALFA pessoal.
    config["cloud"] = {"enabled": False, "project_url": None, "publishable_key": None}
    config["sync"] = {"enabled": False}

    return config


def preparar_config_portatil():
    """
    Pergunta quem está usando, isola COMPLETAMENTE o armazenamento
    daquele perfil (config, memória de atendimentos, workspace) e
    devolve o config pronto para AlfaCore(config=...). Nunca toca em
    config/alfa.json nem em memory/atendimentos/ (só do ALFA pessoal).
    """
    tipo, nome = _perguntar_identidade()
    slug = _slug(nome)

    pasta_perfil = os.path.join(PASTA_LOCAL, slug)
    pasta_memoria_perfil = os.path.join(PASTA_MEMORIA_PORTATIL, slug)
    pasta_workspace_perfil = os.path.join(PASTA_WORKSPACE, slug)
    caminho_perfil = os.path.join(pasta_perfil, "perfil.json")

    perfil_salvo = None
    if os.path.exists(caminho_perfil):
        try:
            with open(caminho_perfil, "r", encoding="utf-8") as arquivo:
                perfil_salvo = json.load(arquivo)
        except Exception:
            perfil_salvo = None

    if perfil_salvo is not None:
        print(f"[BETA PORTÁTIL] Perfil '{nome}' ({tipo}) já existia — reaproveitando configuração.")
        config = perfil_salvo["config"]
    else:
        ambiente = _detectar_ambiente_portatil()
        print(f"[BETA PORTÁTIL] Novo perfil '{nome}' ({tipo}). Hardware: {ambiente.get('perfil_hardware')}.")
        ativar_facial = _perguntar_ativar_reconhecimento_facial()
        config = _construir_config_portatil(tipo, nome, ambiente, ativar_facial)
        os.makedirs(pasta_perfil, exist_ok=True)
        with open(caminho_perfil, "w", encoding="utf-8") as arquivo:
            json.dump({"config": config, "ambiente": ambiente, "tipo": tipo}, arquivo, ensure_ascii=False, indent=2)

    os.makedirs(pasta_memoria_perfil, exist_ok=True)
    os.makedirs(pasta_workspace_perfil, exist_ok=True)

    # ISOLAMENTO DE MEMÓRIA (ver memory/memory.py -> definir_pasta_atendimentos):
    # este perfil grava só na SUA pasta — nunca em memory/atendimentos/
    # (essa continua sendo só do ALFA pessoal, via main.py) e nunca na
    # pasta de outro perfil portátil.
    from memory import memory as memory_mod
    memory_mod.definir_pasta_atendimentos(pasta_memoria_perfil)

    # ISOLAMENTO DO CADASTRO FACIAL (ver vision/face_identity.py):
    # mesmo princípio da memória acima — nunca carrega nem mistura o
    # rosto cadastrado de outro perfil ou do ALFA pessoal (item 13).
    from vision import face_identity
    face_identity.definir_pasta_rostos(os.path.join(pasta_memoria_perfil, "rostos"))

    # ISOLAMENTO DA FILA DE SINCRONIZAÇÃO (ver memory/sync.py) e do
    # ESTADO DE HABILIDADES (ver agente/skill_registry.py) — mesmo
    # princípio: cada perfil só vê os próprios eventos/skills
    # ativadas, nunca os de outro perfil na mesma distribuição
    # portátil (teste de isolamento explícito pedido).
    from memory import sync as sync_mod
    sync_mod.definir_caminho_fila(os.path.join(pasta_memoria_perfil, "fila_sync.json"))

    config["_slug_perfil"] = slug
    config["_workspace_perfil"] = pasta_workspace_perfil
    config["_caminho_estado_skills"] = os.path.join(pasta_memoria_perfil, "skills_estado.json")
    config["_caminho_dispositivo"] = os.path.join(pasta_memoria_perfil, "device.json")
    return config


def main():
    print("=" * 60)
    print("                    BETA PORTÁTIL")
    print("      Mesmo núcleo do projeto ALFA — perfil independente")
    print("=" * 60)

    config = preparar_config_portatil()

    from core.alfa_core import AlfaCore
    AlfaCore(config=config).run()


if __name__ == "__main__":
    main()
