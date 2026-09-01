"""
Núcleo principal do ALFA.

Junta todos os módulos (voz, normalização, NLU, roteamento, execução,
visão, personalidade) em um único orquestrador com um ciclo contínuo:

    ouvir -> interpretar -> executar -> responder -> ouvir de novo

A resposta falada passa sempre por duas camadas independentes:

    resultado (executor) -> Personality (texto + estilo) -> VoiceOutput (áudio)

Isso mantém PERSONALIDADE, TEXTO e TTS separados: trocar a voz
(config/alfa.json -> voz_saida.motor) não muda como a ALFA fala, e
trocar a personalidade não muda qual motor de voz é usado.

Erros em qualquer etapa são contidos aqui: o ALFA registra o problema,
avisa por voz e continua ouvindo, nunca encerra sozinho por causa de
uma falha isolada (ex.: reconhecimento de voz falhou, IA de fallback
fora do ar, motor de TTS em nuvem indisponível, comando inesperado).
"""

import json
import os
import re
import sys
import threading
import time

from computer.executor import (
    ENCERRAR_ATENDIMENTO_SINAL,
    Executor,
    INICIAR_ATENDIMENTO_SINAL,
    SAIR,
)
from agente.contexto import ContextoSessao
from agente.orquestrador import AgenteExecutor
from agente.registro_padrao import construir_registro_padrao
from agente.skill_registry import SkillRegistry
from devices.registry import DeviceRegistry
from integrations.registry import IntegrationRegistry
from core.atendimento import AtendimentoBeta
from core.intent_engine import IntentEngine
from core.normalizer import strip_accents
from core.personality import Personality, eh_falha_retentavel
from core.roteiro_pesquisa import roteiro_nova_entrevista
from core.router import Router
from memory import memory
from security.permissions import CONFIRMACAO_NEGATIVA, CONFIRMACAO_POSITIVA
from ui.estado_beta import EstadoBeta, estado_beta
from voice.barge_in import BargeInListener
from voice.voice_engine import VoiceEngine
from voice.voice_output import VoiceOutput

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE, "config", "alfa.json")

# RMS observado numa fala em volume normal fica por volta de
# 0.004-0.008 (ver correção em voice/voice_engine.py); usa isso como
# referência de "barra cheia" no indicador visual de nível de
# microfone — é só uma escala de exibição, não afeta a detecção real
# de fala.
NIVEL_REFERENCIA_MIC = 0.02

# Intervalo mínimo entre checagens de presença pela câmera (MODO
# ATENDIMENTO) — evita ligar/desligar a câmera a cada ciclo de escuta
# (que pode ser bem mais frequente que isso quando não há fala).
INTERVALO_CHECAGEM_PRESENCA_SEGUNDOS = 4.0

MODOS_BETA_VALIDOS = ("pessoal", "atendimento", "privacidade")

# Frases que, logo depois de uma falha retentável (ver
# core/personality.py -> eh_falha_retentavel), a Beta entende como
# "sim, tenta de novo" — ver _processar_comando.
PALAVRAS_TENTAR_DE_NOVO = (
    "sim", "tenta de novo", "tente de novo", "tente novamente",
    "de novo", "repete", "pode tentar", "manda de novo",
)

# Cancelamento de uma tarefa do agente pausada esperando confirmação
# (ver EstadoEtapa.WAITING_CONFIRMATION) — tratadas como equivalentes
# a "não" nesse contexto específico.
PALAVRAS_CANCELAR_TAREFA = (
    "pare", "para", "cancela", "cancele", "cancelar",
    "pode parar", "esquece", "esqueca", "nao faca mais", "para com isso",
)


def _construir_padrao_wake_word(nome_assistente):
    """
    Monta o regex da palavra de ativação a partir do nome configurado
    da assistente (core/personality.py -> nome_assistente), em vez de
    fixar "Beta" no código — trocar o nome no config/alfa.json já
    ajusta a palavra de ativação sem tocar aqui. Usado sobre o texto
    já normalizado por _detectar_wake_word (minúsculo, sem acento —
    por isso "á"/"ô"/etc. não aparecem mais aqui, diferente de antes).

    Quando o nome é o padrão "Beta", também aceita "Alfa" (nome interno
    do projeto, mesma tolerância de core/normalizer.py) e "Berta"/
    "Beto" — distorções de "Beta" citadas explicitamente no pedido de
    correção da ativação, medidas de verdade em testes com áudio
    sintetizado (ver relatório).

    Duas tolerâncias adicionais, também medidas com áudio real:
      - um saudação curta antes ("oi beta", "ei beta", "olá beta");
      - uma vogal GRUDADA sem espaço antes da palavra ("obeta" — o
        Whisper às vezes funde "ô" ou "e" direto na palavra seguinte).
    Ambas exigem que a palavra de ativação em si ainda apareça
    completa logo depois — não abre brecha para qualquer frase que
    comece com essas letras.
    """
    nome = strip_accents((nome_assistente or "").strip().lower())
    nome_escapado = re.escape(nome)

    if nome == "beta":
        alternativas = "beta|alfa|berta|beto"
    elif nome:
        alternativas = f"{nome_escapado}|beta|alfa"
    else:
        alternativas = "beta|alfa"

    return re.compile(
        rf"^\s*(?:(?:oi|ola|ei)[,!]?\s+)?[oe]?(?:{alternativas})\b[,!.]?\s*",
        re.IGNORECASE,
    )


CONFIG_PADRAO = {
    "voz": {
        "usar_windows_speech": True,
        "modelo_whisper_fallback": "small",
        "timeout_escuta_segundos": 8,
    },
    "voz_saida": {
        "motor": "edge_tts",
        "motor_fallback": "pyttsx3",
        "opcoes_motor": {
            "edge_tts": {
                "voz": "pt-BR-FranciscaNeural",
                "taxa_base": "+0%",
                "volume_base": "+0%",
            },
            "azure": {"voz": "pt-BR-ThalitaMultilingualNeural"},
            "elevenlabs": {"modelo": "eleven_flash_v2_5"},
            "pyttsx3": {"taxa_fala": 190},
        },
    },
    "personalidade": {"nome_usuario": "Rinaldo", "nome_assistente": "Beta"},
    "mouse": {"passo_pixels": 120, "duracao_movimento": 0.05},
    "ia_fallback": {
        "ativo": True,
        "url": "http://127.0.0.1:11434/api/chat",
        "modelo": "qwen2.5-coder:7b",
        # Modelo do planejador do agente (agente/planejador_llm.py) —
        # deliberadamente menor/mais rápido que o de conversa livre
        # acima; ver comentário em AlfaCore.__init__.
        "modelo_planejador": "qwen2.5:0.5b",
    },
    # BETA-CLOUD (ver memory/sync.py) — desligada por padrão. Nunca
    # tem segredo aqui: project_url/publishable_key só valem se
    # vierem do config OU de variáveis de ambiente (ver .env.example);
    # a chave real de servidor (service_role) NUNCA deve rodar no
    # cliente, só a pública/anônima.
    "cloud": {
        "enabled": False,
        "project_url": None,
        "publishable_key": None,
    },
    "sync": {
        "enabled": False,
    },
    # Barge-in (ver voice/barge_in.py): interromper a fala da Beta
    # falando por cima. Ativado por padrão; existe um interruptor
    # aqui para desligar sem mexer em código caso o microfone/
    # alto-falante de um computador específico cause interrupções
    # falsas por eco (ver limitação documentada em voice/barge_in.py).
    "barge_in": {"enabled": True},
    # Reconhecimento facial local (ver vision/face_identity.py) — só
    # ajusta saudação/contexto, nunca autoriza uma ação sozinho (ver
    # security/permissions.py, que continua intacto). Desligado por
    # padrão no perfil portátil (ver launcher/iniciar_portatil.py);
    # ligado por padrão no ALFA pessoal, mas sem ninguém cadastrado
    # automaticamente — só reconhece depois de um cadastro explícito
    # ("Beta, quero cadastrar meu rosto").
    "reconhecimento_facial": {"enabled": True, "indice_camera": 0},
    "inicializacao_automatica_windows": False,
    # pessoal: só reage depois de ouvir a palavra de ativação.
    # atendimento: câmera pode detectar presença e iniciar saudação;
    #   sem visitante, comporta-se como o modo pessoal.
    # privacidade: microfone não ativa comandos nem atendimento — só
    #   escuta a frase de troca de modo (ver AlfaCore._ciclo_privacidade).
    "modo_beta": "pessoal",
}


def carregar_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read().strip()
            if not conteudo:
                return dict(CONFIG_PADRAO)
            dados = json.loads(conteudo)
            # Mescla com os padrões para tolerar config parcial.
            mesclado = dict(CONFIG_PADRAO)
            mesclado.update(dados)
            for chave in (
                "voz", "voz_saida", "personalidade", "mouse", "ia_fallback", "cloud", "sync",
                "barge_in", "reconhecimento_facial",
            ):
                if chave in dados:
                    mesclado[chave] = {**CONFIG_PADRAO[chave], **dados[chave]}
            return mesclado
    except Exception as erro:
        print(f"[ALFA] Config inválida ({erro}). Usando padrões.")
        return dict(CONFIG_PADRAO)


def criar_brain_fallback(config_ia, nome_usuario="Rinaldo", nome_assistente="Beta"):
    if not config_ia.get("ativo", True):
        return None

    import urllib.request

    url = config_ia.get("url", "http://127.0.0.1:11434/api/chat")
    modelo = config_ia.get("modelo", "qwen2.5-coder:7b")

    def brain_fallback(texto):
        payload = {
            "model": modelo,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"Você é a {nome_assistente}, secretária/assistente digital "
                        f"pessoal de {nome_usuario}, que é o usuário principal e "
                        "comandante. Responda em português do Brasil. Seja "
                        "profissional quando o assunto exigir seriedade, e "
                        "descontraída, com humor leve e contextual, quando o "
                        "momento permitir — sem exagerar e sem deixar a "
                        f"personalidade atrapalhar a informação. Trate {nome_usuario} "
                        "pelo nome de vez em quando, sem repetir a cada frase. "
                        "Respostas curtas e naturais, como numa conversa falada, "
                        "nunca como uma lista ou texto formal. Você NÃO controla "
                        "mouse, teclado ou programas: isso é feito localmente pela "
                        f"{nome_assistente}, fora do seu alcance."
                    ),
                },
                {"role": "user", "content": texto},
            ],
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 160},
            # Mantém o modelo carregado na memória do Ollama entre uma
            # fala e outra: sem isso, o servidor descarrega o modelo
            # após um tempo ocioso e cada nova pergunta paga de novo o
            # custo de recarregá-lo — a principal fonte de demora numa
            # conversa (ver correção de latência desta etapa).
            "keep_alive": "30m",
        }

        requisicao = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))

        return dados["message"]["content"].strip()

    return brain_fallback


class AlfaCore:
    """Orquestrador central: liga voz, NLU, roteamento, execução e personalidade."""

    def __init__(self, config=None):
        self.config = config or carregar_config()

        voz_cfg = self.config.get("voz", CONFIG_PADRAO["voz"])
        voz_saida_cfg = self.config.get("voz_saida", CONFIG_PADRAO["voz_saida"])
        personalidade_cfg = self.config.get("personalidade", CONFIG_PADRAO["personalidade"])
        mouse_cfg = self.config.get("mouse", CONFIG_PADRAO["mouse"])
        ia_cfg = self.config.get("ia_fallback", CONFIG_PADRAO["ia_fallback"])

        self.personality = Personality(
            nome_usuario=personalidade_cfg.get("nome_usuario", "Rinaldo"),
            nome_assistente=personalidade_cfg.get("nome_assistente", "Beta"),
        )

        self.voice_output = VoiceOutput(
            motor=voz_saida_cfg.get("motor", "edge_tts"),
            motor_fallback=voz_saida_cfg.get("motor_fallback", "pyttsx3"),
            opcoes_motor=voz_saida_cfg.get("opcoes_motor", {}),
        )

        self.voice_engine = VoiceEngine(
            usar_windows_speech=voz_cfg.get("usar_windows_speech", True),
            modelo_whisper=voz_cfg.get("modelo_whisper_fallback", "base"),
            timeout_segundos=voz_cfg.get("timeout_escuta_segundos", 8),
        )

        self.intent_engine = IntentEngine()

        # Automação orientada a elementos (UI Automation + OCR local).
        # Opcional: se pywinauto/winsdk não estiverem disponíveis
        # neste ambiente, os intents que dependem dela (PREENCHER_CAMPO,
        # CLICAR_ELEMENTO, MARCAR_CAIXA, SELECIONAR_OPCAO, LOCALIZAR)
        # respondem com uma mensagem clara em vez de travar o ALFA.
        form_filler = None
        try:
            from computer.form_filler import FormFiller
            form_filler = FormFiller()
        except Exception as erro:
            print(f"[ALFA] Automação orientada a elementos indisponível: {erro}")

        self.executor = Executor(
            passo_pixels=mouse_cfg.get("passo_pixels", 120),
            duracao=mouse_cfg.get("duracao_movimento", 0.05),
            form_filler=form_filler,
        )

        vision_module = None
        try:
            from vision import vision as vision_module_import
            vision_module = vision_module_import
        except Exception as erro:
            print(f"[ALFA] Módulo de visão indisponível: {erro}")

        # Fundação do agente de computador (FASE 1 — ver agente/).
        # O registro reaproveita a MESMA instância de self.executor
        # (nunca duplica lógica de mouse/teclado/janela/arquivo); o
        # contexto de sessão é leve e só em memória nesta fase.
        self.contexto = ContextoSessao()
        self.contexto.usuario_atual = self.personality.nome_usuario

        # UNIFICAÇÃO DE CONTEXTO: o form_filler (caminho antigo de
        # busca de elementos, usado por pesquisa/atendimento) passa a
        # alimentar o MESMO contexto do agente, em vez de nenhum —
        # nunca cria um segundo mecanismo (ver
        # computer/form_filler.py:_registrar_no_contexto). Não muda
        # nada do comportamento de atendimento em si.
        if form_filler is not None:
            form_filler.contexto = self.contexto

        registro_ferramentas = construir_registro_padrao(self.executor)

        # Skill Registry (ver agente/skill_registry.py) — descoberta de
        # habilidades instaladas (skills/<nome>/manifest.json), FASE A
        # da expansão de plataforma. Só metadado: a execução real das
        # ferramentas continua 100% em registro_ferramentas acima, sem
        # duplicação nem caminho novo de execução.
        # Isolamento por perfil (ver launcher/iniciar_portatil.py):
        # quando rodando um perfil portátil, o estado de ativação de
        # skills fica isolado na pasta daquele perfil — nunca vaza
        # para outro perfil na mesma distribuição nem para o ALFA
        # pessoal (que nunca define "_caminho_estado_skills").
        caminho_estado_skills = self.config.get("_caminho_estado_skills")
        self.skill_registry = SkillRegistry(caminho_estado=caminho_estado_skills)
        self.skill_registry.descobrir()

        # Identidade do dispositivo (ver core/dispositivo.py, item 5 da
        # conexão ao BETA-CLOUD): device_id próprio, nunca o nome do
        # usuário. Isolado por perfil quando portátil (mesmo princípio
        # de _caminho_estado_skills acima).
        from core import dispositivo as dispositivo_mod
        perfil_atual = self.config.get("perfil", {}).get("nome") if self.config.get("perfil") else None
        caminho_dispositivo = self.config.get("_caminho_dispositivo")
        self.dispositivo = dispositivo_mod.obter_ou_criar(caminho=caminho_dispositivo, perfil=perfil_atual)

        if self.dispositivo.get("status") == "novo":
            try:
                from memory import sync as sync_mod
                sync_mod.enfileirar("DEVICE_REGISTERED", dict(self.dispositivo), origem="alfa_core")
                self.dispositivo["status"] = "registrado_localmente"
                dispositivo_mod._salvar(self.dispositivo, caminho_dispositivo)
            except Exception as erro:
                print(f"[ALFA] Não consegui enfileirar registro do dispositivo: {erro}")

        # Integration/Device Registry (ver integrations/registry.py e
        # devices/registry.py — FASES C/E da expansão de plataforma):
        # vazios por padrão, nunca inventam um sistema comercial ou um
        # equipamento conectado que não existe (item 29). Uma skill
        # futura registra um adaptador real chamando
        # core.integration_registry.registrar(...)/device_registry.registrar(...).
        self.integration_registry = IntegrationRegistry()
        self.device_registry = DeviceRegistry()

        agente_executor = AgenteExecutor(
            registro_ferramentas,
            contexto=self.contexto,
            ollama_url=ia_cfg.get("url") if ia_cfg.get("ativo", True) else None,
            # Planejamento usa um modelo bem menor que o de conversa
            # livre (ia_cfg["modelo"]) de propósito: um plano é só
            # "escolher ferramenta + parâmetros", não exige um modelo
            # grande, e nesta máquina (sem GPU) um modelo de 7B chega a
            # levar 30s+ para responder — inviável para algo que devia
            # ser rápido. Ajustável em config/alfa.json ->
            # ia_fallback.modelo_planejador.
            ollama_modelo=ia_cfg.get("modelo_planejador", "qwen2.5:0.5b"),
        )

        # Descoberta de ambiente (ver agente/ambiente.py) — roda UMA
        # vez, numa thread própria: câmera/import de ctranslate2/rede
        # podem levar alguns segundos, e isso nunca deve atrasar a
        # saudação nem o início da escuta. Best-effort: se falhar, a
        # Beta segue normalmente, só sem esses dados em contexto.
        def _detectar_ambiente_em_thread():
            try:
                from agente.ambiente import classificar_hardware, detectar_ambiente, salvar_ambiente
                ambiente_detectado = detectar_ambiente()
                perfil = classificar_hardware(ambiente_detectado)
                ambiente_detectado["perfil_hardware"] = perfil
                self.contexto.temporarios["ambiente"] = ambiente_detectado
                salvar_ambiente(ambiente_detectado)
                print(
                    f"[ALFA] Ambiente detectado em "
                    f"{ambiente_detectado.get('_tempo_deteccao_segundos')}s. "
                    f"Perfil de hardware: {perfil}."
                )
            except Exception as erro:
                print(f"[ALFA] Detecção de ambiente indisponível: {erro}")

        threading.Thread(
            target=_detectar_ambiente_em_thread, name="DetectarAmbiente", daemon=True
        ).start()

        # BETA-CLOUD (ver memory/sync.py) — integração mínima. Chave e
        # URL só vêm de variável de ambiente ou config, NUNCA
        # hardcoded (ver .env.example); só a chave publishable/anônima
        # é aceita aqui, nunca service_role. Desligada por padrão
        # (cloud.enabled=False): a Beta funciona 100% offline sem
        # nada disto. Quando ligada, roda em thread própria e nunca
        # bloqueia a resposta esperando a nuvem.
        cloud_cfg = self.config.get("cloud", CONFIG_PADRAO["cloud"])
        sync_cfg = self.config.get("sync", CONFIG_PADRAO["sync"])
        self._cloud_url = os.environ.get("BETA_CLOUD_PROJECT_URL") or cloud_cfg.get("project_url")
        self._cloud_key = os.environ.get("BETA_CLOUD_PUBLISHABLE_KEY") or cloud_cfg.get("publishable_key")
        self._cloud_habilitada = bool(cloud_cfg.get("enabled")) and bool(self._cloud_url) and bool(self._cloud_key)
        self._sync_habilitada = bool(sync_cfg.get("enabled"))

        # Cliente real do BETA-CLOUD (ver memory/beta_cloud_client.py)
        # — só publishable key aqui, nunca service_role. `configurado()`
        # é False sem as duas variáveis de ambiente/config, e nesse
        # caso a sincronização abaixo nem tenta rodar.
        from memory.beta_cloud_client import BetaCloudClient
        self.beta_cloud_cliente = BetaCloudClient(url=self._cloud_url, publishable_key=self._cloud_key)

        if self._cloud_habilitada and self._sync_habilitada and self.beta_cloud_cliente.configurado():
            def _sincronizar_em_thread():
                try:
                    from memory import sync as sync_mod
                    sucesso, mensagem = sync_mod.sincronizar(enviar_evento=self.beta_cloud_cliente.enviar_evento)
                    print(f"[ALFA] Sincronização BETA-CLOUD: {mensagem}")
                except Exception as erro:
                    print(f"[ALFA] Sincronização BETA-CLOUD indisponível: {erro}")

            threading.Thread(
                target=_sincronizar_em_thread, name="SyncBetaCloud", daemon=True
            ).start()

        self.router = Router(
            intent_engine=self.intent_engine,
            executor=self.executor,
            brain_fallback=criar_brain_fallback(
                ia_cfg, self.personality.nome_usuario, self.personality.nome_assistente
            ),
            vision=vision_module,
            aviso_previo=self._aviso_espera,
            agente=agente_executor,
        )

        # GERENCIADOR DE PROGRESSO CONVERSACIONAL: guarda o texto do
        # último comando que falhou por motivo de rede/IA (ver
        # core/personality.py -> eh_falha_retentavel), para poder
        # repeti-lo se a próxima fala for uma confirmação tipo "sim,
        # tenta de novo" (ver _processar_comando).
        self._retry_pendente = None

        # Modo BETA_ATENDIMENTO (core/atendimento.py): protocolo completo
        # de identificação -> roteiro -> conclusão -> encadeamento
        # automático para o próximo atendimento. O CONTEÚDO do roteiro
        # (as perguntas da pesquisa em si) continua vindo de fora — um
        # módulo de pesquisa futuro chama self.atendimento pelo mesmo
        # mecanismo.
        self.atendimento = AtendimentoBeta(form_filler=form_filler, vision_module=vision_module)
        self._ultimo_roteiro_atendimento = None

        # Ativação por palavra-chave ("Beta"): fora de um atendimento,
        # a Beta só processa comando depois de ouvir a palavra de
        # ativação — evita responder a TV, conversa alheia ou ruído
        # (ver _ciclo_wake_word). "standby" = vigiando só a palavra de
        # ativação; "active" = já confirmou e está ouvindo o comando.
        self._modo_escuta = "standby"
        self._padrao_wake_word = _construir_padrao_wake_word(self.personality.nome_assistente)

        self._modo_beta = self.config.get("modo_beta", "pessoal")
        if self._modo_beta not in MODOS_BETA_VALIDOS:
            print(f"[ALFA] modo_beta inválido ({self._modo_beta!r}); usando 'pessoal'.")
            self._modo_beta = "pessoal"

        # MODO ATENDIMENTO: detecção de presença por câmera (ver
        # vision/presenca.py). _presenca_aguardando_resposta indica
        # que já cumprimentou alguém e está esperando a resposta dela
        # antes de decidir se inicia o atendimento.
        self._presenca_aguardando_resposta = False
        self._ultima_checagem_presenca = 0.0

        # Barge-in (ver voice/barge_in.py) — interruptor simples por
        # config, sem precisar mexer em código se causar problema num
        # computador específico (ver limitação de eco documentada lá).
        barge_in_cfg = self.config.get("barge_in", CONFIG_PADRAO["barge_in"])
        self._barge_in_ativo = bool(barge_in_cfg.get("enabled", True))

        # Reconhecimento facial local (ver vision/face_identity.py) —
        # só ajusta saudação/contexto, NUNCA autoriza uma ação sozinho
        # (security/permissions.py continua intacto). Roda em thread
        # própria e nunca atrasa a inicialização além de um limite
        # curto (ver run(), que espera no máximo alguns segundos antes
        # de seguir com a saudação padrão de qualquer forma).
        reconhecimento_cfg = self.config.get("reconhecimento_facial", CONFIG_PADRAO["reconhecimento_facial"])
        self._reconhecimento_facial_ativo = bool(reconhecimento_cfg.get("enabled", True))
        self._indice_camera_facial = reconhecimento_cfg.get("indice_camera", 0)
        self._identidade_reconhecida = None
        self._evento_reconhecimento_facial = threading.Event()

        if self._reconhecimento_facial_ativo:
            def _reconhecer_rosto_em_thread():
                try:
                    from vision import face_identity
                    if face_identity.reconhecimento_disponivel() and face_identity.camera_disponivel(
                        self._indice_camera_facial
                    ):
                        resultado = face_identity.identificar(self._indice_camera_facial)
                        if resultado["estado"] in (face_identity.MATCH_FORTE, face_identity.MATCH_FRACO):
                            self._identidade_reconhecida = resultado
                        elif resultado["estado"] == face_identity.UNKNOWN:
                            self._identidade_reconhecida = resultado
                        self.contexto.temporarios["identidade_facial"] = resultado
                except Exception as erro:
                    print(f"[ALFA] Reconhecimento facial indisponível: {erro}")
                finally:
                    self._evento_reconhecimento_facial.set()
        else:
            self._evento_reconhecimento_facial.set()

        if self._reconhecimento_facial_ativo:
            threading.Thread(
                target=_reconhecer_rosto_em_thread, name="ReconhecimentoFacial", daemon=True
            ).start()

        # Indicador visual permanente do estado (ui/status_widget.py).
        # Roda numa thread própria — nunca bloqueia o laço de voz, e se
        # não conseguir abrir (ambiente sem interface gráfica), a BETA
        # segue funcionando normalmente, só sem o indicador.
        try:
            from ui import status_widget
            status_widget.iniciar_em_thread()
        except Exception as erro:
            print(f"[ALFA] Indicador visual indisponível: {erro}")

        estado_beta.definir_estado(EstadoBeta.IDLE)

    def _falar(self, texto, estilo=None):
        estado_beta.definir_estado(EstadoBeta.SPEAKING)

        ouvinte = None
        if texto and self._barge_in_ativo:
            ouvinte = BargeInListener(self.voice_engine, self.voice_output)
            ouvinte.iniciar()

        try:
            self.voice_output.falar(texto, estilo)
        finally:
            interrompido = False
            texto_interrupcao = ""
            if ouvinte is not None:
                interrompido = ouvinte.foi_interrompida()
                if interrompido:
                    texto_interrupcao = ouvinte.texto_da_interrupcao()
                ouvinte.parar()

        estado_beta.definir_estado(EstadoBeta.IDLE)
        if texto:
            self.contexto.ultima_resposta_falada = texto

        if interrompido:
            print(f"[BARGE-IN] Fala interrompida. Capturado: '{texto_interrupcao}'")
            if texto_interrupcao:
                self._processar_comando(texto_interrupcao, "barge_in")

    def _saudacao_de_abertura(self):
        """
        Fluxo de integração do reconhecimento facial (item 19 do
        pedido): espera no máximo um tempo curto pelo resultado da
        thread de reconhecimento (nunca trava a inicialização por
        muito tempo — ver __init__) e personaliza a saudação conforme
        o estado (item 11); sem reconhecimento ativo/disponível, cai
        na saudação padrão de sempre, sem mudança nenhuma.
        """
        if self._reconhecimento_facial_ativo:
            self._evento_reconhecimento_facial.wait(timeout=3.0)
            resultado = self._identidade_reconhecida
            if resultado and resultado["estado"] == "MATCH_FORTE":
                # MATCH_FRACO cai para a saudação padrão (item 10: não
                # assumir identidade com confiança fraca).
                eh_principal = resultado["nome"] == self.personality.nome_usuario
                return self.personality.saudacao_reconhecimento_facial(resultado["nome"], eh_principal)
            if resultado and resultado["estado"] == "UNKNOWN":
                return self.personality.saudacao_facial_desconhecida()

        return self.personality.saudacao_inicial()

    def _cadastrar_rosto(self):
        """
        Fluxo de cadastro facial explícito (item 9 do pedido de
        reconhecimento facial) — nunca automático. Fala a confirmação
        ANTES de capturar (a câmera leva alguns segundos), igual ao
        aviso prévio de tarefas demoradas (ver core/router.py).
        """
        from vision import face_identity

        self._falar("Claro. Vou usar a câmera para cadastrar sua identificação facial.", "confirmacao")
        sucesso, mensagem = face_identity.cadastrar_rosto(
            self.personality.nome_usuario, self._indice_camera_facial
        )
        self._falar(mensagem, "confirmacao" if sucesso else "neutra")
        return True

    def _ativar_modo_totem(self):
        """
        Abre a interface de totem (ver ui/totem/totem_app.py) como um
        PROCESSO/JANELA separada — nunca dentro desta sessão (a Beta
        atual continua rodando normalmente). O totem constrói sua
        própria AlfaCore (mesmo núcleo, perfil isolado); esta sessão
        não perde nem compartilha contexto com ela.
        """
        import subprocess

        caminho_totem = os.path.join(BASE, "ui", "totem", "totem_app.py")
        if not os.path.exists(caminho_totem):
            self._falar("Não encontrei o módulo do totem instalado.", "neutra")
            return

        try:
            subprocess.Popen([sys.executable, caminho_totem])
            self._falar("Abrindo o modo totem em tela cheia.", "confirmacao")
        except Exception as erro:
            self._falar(f"Não consegui abrir o modo totem: {erro}", "neutra")

    def _aviso_espera(self, categoria):
        """
        Chamado pelo router (ver core/router.py -> aviso_previo) um
        instante ANTES de uma operação classificada como demorada —
        nunca para tarefas imediatas/rápidas. Depois de avisar, volta
        o estado visual para WORKING (que _falar zera para IDLE ao
        terminar de falar), já que a operação de verdade ainda vai
        rodar em seguida.
        """
        texto, estilo = self.personality.aviso_espera(categoria)
        self._falar(texto, estilo)
        estado_beta.definir_estado(EstadoBeta.WORKING)

    def _eh_confirmacao_retry(self, texto):
        normalizado = self.intent_engine.normalizar(texto)
        return any(
            re.search(rf"\b{re.escape(palavra)}\b", normalizado)
            for palavra in PALAVRAS_TENTAR_DE_NOVO
        )

    def _interpretar_sim_nao(self, texto):
        """True (sim), False (não/cancelar), ou None (resposta ambígua
        — quem chama deve tratar como 'não confirmou', nunca assumir).

        Checa cancelamento/negação ANTES da confirmação positiva de
        propósito: "pode parar" contém a palavra solta "pode" (uma das
        CONFIRMACAO_POSITIVA), então checar a positiva primeiro
        interpretaria erradamente um pedido de cancelamento como um
        "sim" — frases de cancelamento são mais específicas (múltiplas
        palavras), então vencem o empate.
        """
        normalizado = self.intent_engine.normalizar(texto)
        if any(
            re.search(rf"\b{re.escape(palavra)}\b", normalizado)
            for palavra in PALAVRAS_CANCELAR_TAREFA
        ):
            return False
        if any(p in normalizado for p in CONFIRMACAO_NEGATIVA):
            return False
        if any(p in normalizado for p in CONFIRMACAO_POSITIVA):
            return True
        return None

    def _falar_atendimento(self, texto):
        if not texto:
            return
        texto_final, estilo = self.personality.compor({"intent": "ATENDIMENTO"}, texto)
        self._falar(texto_final[:700], estilo)

    def _iniciar_atendimento(self, roteiro=None, proximo=False):
        if roteiro is None:
            # Roteiro real da tela "Nova entrevista" (Central de
            # Pesquisas Online) — ver core/roteiro_pesquisa.py. Não é
            # conteúdo inventado: reflete os campos de verdade da tela.
            roteiro = self._ultimo_roteiro_atendimento or roteiro_nova_entrevista()
        self._ultimo_roteiro_atendimento = roteiro

        saudacao = (
            self.atendimento.iniciar_proximo(roteiro)
            if proximo
            else self.atendimento.iniciar(roteiro)
        )
        self._falar_atendimento(saudacao)
        return True

    def _encerrar_atendimento(self, auto_prox=False):
        """
        Encerramento explícito (pedido do operador). Por padrão NÃO
        encadeia o próximo atendimento — isso é reservado à conclusão
        natural do roteiro em _processar_turno_atendimento, que sempre
        prepara a fila seguinte automaticamente (itens 15-17 do fluxo).
        """
        if self.atendimento.esta_ativo():
            # Captura o id ANTES de finalizar(): finalizar() chama
            # limpar_estado(), que zera atendimento_id — se
            # capturássemos depois, o registro salvo teria um id
            # DIFERENTE do usado para nomear uma eventual foto já
            # associada a este atendimento (ver vision/camera.py).
            atendimento_id_atual = self.atendimento.atendimento_id
            dados = self.atendimento.finalizar()
            self._salvar_dados_atendimento(dados, atendimento_id_atual)
        self._falar_atendimento("Atendimento encerrado.")

        if auto_prox and self._ultimo_roteiro_atendimento is not None:
            return self._iniciar_atendimento(proximo=True)

        return True

    def _salvar_dados_atendimento(self, dados, atendimento_id=None):
        if not dados:
            return
        try:
            atendimento_id = atendimento_id or self.atendimento.atendimento_id or memory.novo_id_atendimento()
            memory.salvar_atendimento(atendimento_id, dados)
        except Exception as erro:
            print(f"[ALFA] Não consegui salvar os dados do atendimento: {erro}")

    def _processar_turno_atendimento(self, texto_ouvido):
        # Mesmo motivo do comentário em _encerrar_atendimento: captura
        # o id ANTES de processar_resposta() poder finalizar (e limpar)
        # o atendimento internamente.
        atendimento_id_atual = self.atendimento.atendimento_id
        resultado = self.atendimento.processar_resposta(texto_ouvido)

        if resultado.get("acao") == "finalizado":
            self._salvar_dados_atendimento(resultado.get("dados"), atendimento_id_atual)
            self._falar_atendimento(resultado.get("mensagem"))
            # Preparar automaticamente o próximo atendimento — fila
            # contínua, sem precisar do operador dizer "iniciar
            # atendimento" de novo a cada pessoa (itens 15-17).
            return self._iniciar_atendimento(proximo=True)

        mensagem = resultado.get("mensagem")
        proxima_pergunta = resultado.get("proxima_pergunta")

        fala = " ".join(parte for parte in (mensagem, proxima_pergunta) if parte)
        self._falar_atendimento(fala)

        return True

    def _detectar_wake_word(self, texto):
        """
        Retorna (True, resto) se `texto` começa com a palavra de
        ativação (ver _construir_padrao_wake_word), onde `resto` é o
        que sobrou depois dela (pode ser "", se a pessoa só disse
        "Beta" e esperou). Retorna (False, texto) se a fala não foi
        endereçada à Beta.

        Normaliza (minúsculo + sem acento) ANTES de comparar — item 4
        da correção de ativação. strip_accents preserva o comprimento
        da string (só troca cada caractere acentuado pelo equivalente
        sem acento), então a posição onde o regex casou é a MESMA no
        texto original, e dá pra cortar `resto` dele sem perder
        maiúsculas/acentos do comando em si.
        """
        texto_normalizado = strip_accents(texto.lower())
        match = self._padrao_wake_word.match(texto_normalizado)
        encontrada = match is not None
        print(f"[WAKE] transcrição raw: {texto!r}")
        print(f"[WAKE] texto normalizado: {texto_normalizado!r}")
        print(f"[WAKE] palavra encontrada: {'SIM' if encontrada else 'NÃO'}")
        if not encontrada:
            return False, texto
        return True, texto[match.end():].strip()

    def _processar_comando(self, texto, motor, t_captura_inicio=None):
        """
        Interpreta e executa um comando/conversa já confirmado como
        endereçado à Beta (palavra de ativação já reconhecida antes de
        chegar aqui, ver _ciclo_wake_word). Mesma lógica de
        roteamento/execução/resposta de sempre.

        GERENCIADOR DE PROGRESSO CONVERSACIONAL: se o comando anterior
        tiver falhado por motivo de rede/IA (ver
        core/personality.py -> eh_falha_retentavel) e esta fala for
        uma confirmação ("sim", "tenta de novo"...), repete o comando
        que falhou em vez de tratar a confirmação como uma fala nova
        sem sentido.

        `t_captura_inicio`, se fornecido pelo chamador (ver
        _ciclo_wake_word), é o instante logo ANTES de
        voice_engine.listen() — só usado para imprimir o log
        [LATÊNCIA] (captura/interpretação/resposta/tts/total) no final;
        nunca influencia o comportamento. Sem ele (chamadas internas,
        como REPETIR/retentativa), o log de latência simplesmente não
        é impresso.
        """
        agente = self.router.agente
        if agente is not None and agente.tem_confirmacao_pendente():
            confirmou = self._interpretar_sim_nao(texto)
            if confirmou is not None:
                print(f"VOCÊ ({motor}): {texto}")
                estado_beta.definir_estado(EstadoBeta.WORKING)
                mensagem = agente.resolver_confirmacao(confirmou)
                texto_final, estilo = self.personality.compor(
                    {"intent": "TAREFA_CONFIRMACAO"}, mensagem
                )
                self._falar(texto_final, estilo)
                return True
            # Resposta ambígua: NÃO assume nem sim nem não — deixa a
            # pendência viva e trata esta fala como uma pergunta nova
            # de esclarecimento por parte do usuário, não como recusa
            # silenciosa da ação pendente.

        if self._retry_pendente is not None:
            texto_retry = self._retry_pendente
            self._retry_pendente = None
            if self._eh_confirmacao_retry(texto):
                return self._processar_comando(texto_retry, motor)

        # "Repita"/"pode repetir" (ver core/intent_engine.py -> REPETIR):
        # fala de novo a ÚLTIMA resposta real, sem passar pelo roteador
        # normal — não existe "resultado" novo para compor, só o texto
        # que já foi dito.
        if self.intent_engine.interpretar(texto, texto).get("intent") == "REPETIR":
            print(f"VOCÊ ({motor}): {texto}")
            if self.contexto.ultima_resposta_falada:
                estado_beta.definir_estado(EstadoBeta.WORKING)
                self._falar(self.contexto.ultima_resposta_falada, "neutra")
            else:
                self._falar("Ainda não tenho uma resposta anterior para repetir.", "neutra")
            return True

        # RECONHECIMENTO FACIAL (ver vision/face_identity.py) — cadastro
        # e remoção são explícitos, nunca automáticos (item 9 do
        # pedido); tratados aqui, antes do roteador, pelo mesmo motivo
        # do REPETIR acima: não é uma ferramenta do agente nem uma
        # ação do executor comum.
        intent_facial = self.intent_engine.interpretar(texto, texto).get("intent")
        if intent_facial == "CADASTRAR_ROSTO":
            print(f"VOCÊ ({motor}): {texto}")
            return self._cadastrar_rosto()
        if intent_facial == "REMOVER_ROSTO":
            print(f"VOCÊ ({motor}): {texto}")
            from vision import face_identity
            sucesso, mensagem = face_identity.remover_identidade(self.personality.nome_usuario)
            self._falar(mensagem, "confirmacao" if sucesso else "neutra")
            return True
        if intent_facial == "LISTAR_HABILIDADES":
            print(f"VOCÊ ({motor}): {texto}")
            habilidades = self.skill_registry.listar()
            if not habilidades:
                self._falar("Não encontrei nenhuma habilidade instalada.", "neutra")
            else:
                nomes = ", ".join(h.nome for h in habilidades if self.skill_registry.esta_ativa(h.nome))
                self._falar(f"Tenho estas habilidades instaladas: {nomes}.", "confirmacao")
            return True
        if intent_facial == "ATIVAR_MODO_TOTEM":
            print(f"VOCÊ ({motor}): {texto}")
            self._ativar_modo_totem()
            return True

        print(f"VOCÊ ({motor}): {texto}")
        estado_beta.definir_estado(EstadoBeta.PROCESSING)
        estado_beta.definir_estado(EstadoBeta.WORKING)

        t_apos_captura = time.monotonic()
        resultado, intent = self.router.handle(texto)
        t_apos_interpretacao = time.monotonic()
        print("INTENÇÃO:", intent)

        self.contexto.atualizar_fala(texto, intent.get("intent"))
        self._retry_pendente = texto if eh_falha_retentavel(str(resultado)) else None

        kind = intent.get("intent")
        if kind == "ATIVAR_MODO_PESSOAL":
            self._modo_beta = "pessoal"
        elif kind == "ATIVAR_MODO_ATENDIMENTO":
            self._modo_beta = "atendimento"
        elif kind == "ATIVAR_MODO_PRIVACIDADE":
            self._modo_beta = "privacidade"

        if resultado == SAIR:
            texto_final, estilo = self.personality.despedida()
            self._falar(texto_final, estilo)
            return False

        if resultado == INICIAR_ATENDIMENTO_SINAL:
            return self._iniciar_atendimento()

        if resultado == ENCERRAR_ATENDIMENTO_SINAL:
            return self._encerrar_atendimento()

        if resultado:
            texto_final, estilo = self.personality.compor(intent, resultado)
            t_apos_resposta = time.monotonic()
            self._falar(texto_final[:700], estilo)
            t_apos_tts = time.monotonic()
            self._logar_latencia(t_captura_inicio, t_apos_captura, t_apos_interpretacao, t_apos_resposta, t_apos_tts)

        return True

    def _logar_latencia(self, t_captura_inicio, t_apos_captura, t_apos_interpretacao, t_apos_resposta, t_apos_tts):
        """
        Só imprime tempos (item 4 do pedido de redução de latência) —
        nunca muda o que é dito nem o que é executado. Sem
        t_captura_inicio (chamada sem medição, ver _processar_comando)
        não imprime nada.
        """
        if t_captura_inicio is None:
            return
        print(
            "[LATÊNCIA]\n"
            f"captura={t_apos_captura - t_captura_inicio:.2f}s\n"
            f"interpretacao={t_apos_interpretacao - t_apos_captura:.2f}s\n"
            f"resposta={t_apos_resposta - t_apos_interpretacao:.2f}s\n"
            f"tts={t_apos_tts - t_apos_resposta:.2f}s\n"
            f"total={t_apos_tts - t_captura_inicio:.2f}s"
        )

    def _ciclo_atendimento(self):
        """Ciclo usado enquanto um atendimento (core/atendimento.py)
        está em andamento — sem palavra de ativação: toda fala vai
        direto para a pessoa sendo atendida, como sempre."""

        print("\nALFA: Estou ouvindo...")
        estado_beta.definir_estado(EstadoBeta.LISTENING, nivel_mic=0.0)
        texto, motor = self.voice_engine.listen(
            on_nivel=lambda rms: estado_beta.definir_nivel_mic(rms / NIVEL_REFERENCIA_MIC)
        )

        if not texto:
            estado_beta.definir_estado(EstadoBeta.IDLE)
            self._falar_atendimento(self.atendimento.mensagem_nao_entendi())
            return True

        print(f"VOCÊ ({motor}): {texto}")
        estado_beta.definir_estado(EstadoBeta.PROCESSING)

        # Válvula de segurança do operador: mesmo com um atendimento em
        # andamento, ele ainda pode encerrar a fila dizendo isso
        # explicitamente — ver INTENCOES_LOCAIS/ENCERRAR_ATENDIMENTO.
        if self.intent_engine.interpretar(texto).get("intent") == "ENCERRAR_ATENDIMENTO":
            return self._encerrar_atendimento(auto_prox=False)

        estado_beta.definir_estado(EstadoBeta.WORKING)
        return self._processar_turno_atendimento(texto)

    def _ciclo_privacidade(self):
        """
        MODO PRIVACIDADE: microfone não ativa comando nenhum. Única
        exceção: a própria frase de troca de modo (com palavra de
        ativação), senão não haveria como sair do modo por voz.
        """
        estado_beta.definir_estado(EstadoBeta.STANDBY)
        texto, _motor = self.voice_engine.listen()

        if not texto:
            return True

        tem_wake_word, resto = self._detectar_wake_word(texto)
        if not tem_wake_word or not resto:
            return True

        intent = self.intent_engine.interpretar(resto, resto)
        kind = intent.get("intent")
        if kind in ("ATIVAR_MODO_PESSOAL", "ATIVAR_MODO_ATENDIMENTO"):
            self._modo_beta = "pessoal" if kind == "ATIVAR_MODO_PESSOAL" else "atendimento"
            resultado = self.executor.executar(intent)
            texto_final, estilo = self.personality.compor(intent, resultado)
            self._falar(texto_final, estilo)

        # Qualquer outra coisa dita em modo privacidade é descartada
        # silenciosamente: sem comando, sem resposta, sem log de "não
        # entendi" — é assim que "microfone não ativa comandos" deve
        # se comportar de verdade.
        return True

    def _ciclo_deteccao_presenca(self):
        """
        MODO ATENDIMENTO: vigia a câmera por presença humana (ver
        vision/presenca.py — NÃO é reconhecimento facial, só confirma
        que há alguém, sem identificar quem). Retorna None quando não
        há nada a fazer agora (chamador deve seguir para o ciclo
        normal de palavra de ativação); True/False quando este método
        já tratou o ciclo inteiro.
        """
        if self._presenca_aguardando_resposta:
            estado_beta.definir_estado(EstadoBeta.LISTENING, nivel_mic=0.0)
            texto, motor = self.voice_engine.listen(
                on_nivel=lambda rms: estado_beta.definir_nivel_mic(rms / NIVEL_REFERENCIA_MIC)
            )
            self._presenca_aguardando_resposta = False

            if not texto:
                # Não respondeu nada compreensível: não força
                # atendimento, só volta a vigiar a câmera depois.
                estado_beta.definir_estado(EstadoBeta.STANDBY)
                return True

            print(f"VOCÊ ({motor}): {texto}")
            # Qualquer resposta falada à saudação já conta como
            # consentimento para começar — não exige uma palavra
            # mágica específica, só que a pessoa tenha respondido.
            return self._iniciar_atendimento()

        agora = time.monotonic()
        if agora - self._ultima_checagem_presenca < INTERVALO_CHECAGEM_PRESENCA_SEGUNDOS:
            return None
        self._ultima_checagem_presenca = agora

        try:
            from vision.presenca import alguem_presente
            presente = alguem_presente()
        except Exception as erro:
            print(f"[ALFA] Detecção de presença indisponível: {erro}")
            return None

        if not presente:
            return None

        texto_saudacao, estilo = self.personality.saudacao_presenca()
        estado_beta.definir_estado(EstadoBeta.ATIVANDO)
        self._falar(texto_saudacao, estilo)
        self._presenca_aguardando_resposta = True
        return True

    def _ciclo_wake_word(self):
        """
        MODO PESSOAL (e MODO ATENDIMENTO sem visitante): só processa
        comando depois de ouvir a palavra de ativação — ver
        _detectar_wake_word. Sem ela, qualquer fala captada (TV,
        conversa alheia, ruído) é ignorada por completo: sem resposta,
        sem log de "não entendi", sem virar comando.

        ESCUTA CONTÍNUA: usa o MESMO stream de microfone sempre aberto
        (ver voice/continuous_mic.py e VoiceEngine.escutar_continuo)
        em vez de abrir/gravar/fechar uma janela fixa a cada tentativa
        — standby e active só mudam COMO o próximo trecho de fala é
        interpretado (procurar "Beta" ou tratar como comando
        completo), nunca abrem um segundo microfone.
        """
        # Descarta qualquer áudio que tenha se acumulado no stream
        # compartilhado enquanto ninguém estava consumindo (ex.: during
        # o processamento do comando anterior) — nunca processa fala
        # velha (item 3: privacidade; evita reagir a algo já passado).
        self.voice_engine.mic_continuo.limpar_fila()

        if self._modo_escuta == "standby":
            print("\n[BETA] (standby) monitorando continuamente a palavra de ativação...")
            estado_beta.definir_estado(EstadoBeta.STANDBY)
            # initial_prompt="Beta": corrige um erro de transcrição
            # real e medido (ver relatório) — a palavra "Beta" dita
            # SOZINHA, sem mais nada na frase, saía como "Bet." sem
            # essa dica. Só usado aqui (detecção da palavra de
            # ativação); a escuta do comando em si (modo ACTIVE, logo
            # abaixo) continua sem viés nenhum. Mesmo Whisper já
            # carregado — nenhum modelo novo.
            texto, motor, t_inicio_fala, t_fim_fala = self.voice_engine.escutar_continuo(
                initial_prompt=self.personality.nome_assistente
            )

            if not texto:
                if t_inicio_fala is not None:
                    print(f"[WAKE] tempo_desde_inicio_da_fala={t_fim_fala - t_inicio_fala:.2f}s (sem transcrição válida)")
                return True

            print(f"[WAKE] transcrição: {texto!r}")
            print(f"[WAKE] tempo_desde_inicio_da_fala={t_fim_fala - t_inicio_fala:.2f}s")
            t_deteccao_inicio = time.monotonic()
            tem_wake_word, resto = self._detectar_wake_word(texto)
            print(f"[WAKE] tempo_detectar_beta={time.monotonic() - t_deteccao_inicio:.3f}s")
            if not tem_wake_word:
                print(f"[BETA] Ignorado (sem palavra de ativação): '{texto}'")
                return True

            t_captura_inicio = t_inicio_fala
            print(f"[BETA] Palavra de ativação detectada em: '{texto}'")
            estado_beta.definir_estado(EstadoBeta.ATIVANDO)

            if not resto:
                # Só disse "Beta" e esperou.
                t_ativacao_inicio = time.monotonic()
                self._falar("Estou ouvindo.", "confirmacao")
                print(f"[WAKE] tempo_ativacao={time.monotonic() - t_ativacao_inicio:.2f}s")
                self._modo_escuta = "active"
                return True

            # Disse a palavra de ativação e o comando na mesma frase
            # ("Beta, abra o navegador.") — processa direto, sem
            # round-trip extra.
            return self._processar_comando(resto, motor, t_captura_inicio=t_captura_inicio)

        # ACTIVE: a palavra de ativação já foi confirmada; esta fala é
        # o comando. Sempre volta para "standby" depois desta rodada,
        # aconteça o que acontecer, para não ficar em ACTIVE preso.
        self._modo_escuta = "standby"
        print("\nALFA: Estou ouvindo...")
        estado_beta.definir_estado(EstadoBeta.LISTENING, nivel_mic=0.0)
        texto, motor, t_inicio_fala, t_fim_fala = self.voice_engine.escutar_continuo(
            on_nivel=lambda rms: estado_beta.definir_nivel_mic(rms / NIVEL_REFERENCIA_MIC)
        )
        t_captura_inicio = t_inicio_fala or time.monotonic()

        if not texto:
            estado_beta.definir_estado(EstadoBeta.STANDBY)
            return True

        return self._processar_comando(texto, motor, t_captura_inicio=t_captura_inicio)

    def ciclo_unico(self):
        """
        Executa um ciclo completo. Retorna False quando o usuário
        pediu para encerrar a Beta, True em qualquer outro caso
        (inclusive silêncio/fala ignorada).

        Prioridade de despacho:
          1. Atendimento em andamento -> sem palavra de ativação
             (ver _ciclo_atendimento, BETA_ATENDIMENTO).
          2. MODO PRIVACIDADE -> microfone não ativa comando nenhum.
          3. MODO ATENDIMENTO sem atendimento ativo -> câmera pode
             detectar presença e iniciar saudação; sem visitante, cai
             no mesmo fluxo de palavra de ativação do modo pessoal.
          4. MODO PESSOAL (padrão) -> só reage à palavra de ativação.
        """
        if self.atendimento.esta_ativo():
            return self._ciclo_atendimento()

        if self._modo_beta == "privacidade":
            return self._ciclo_privacidade()

        if self._modo_beta == "atendimento":
            resultado_presenca = self._ciclo_deteccao_presenca()
            if resultado_presenca is not None:
                return resultado_presenca

        return self._ciclo_wake_word()

    def run(self):
        print(f"[ALFA] Motor de voz (entrada): {self.voice_engine.motor_ativo}")
        print(f"[ALFA] Motor de voz (saída): {self.voice_output.motor_ativo}")

        # Escuta contínua (ver voice/continuous_mic.py): o microfone é
        # aberto UMA VEZ aqui e fica sempre pronto — inclusive durante
        # a própria saudação de abertura (o barge-in já funciona desde
        # a primeira fala). Sem microfone disponível, a Beta segue
        # normalmente só por voz de saída (item 15 do pedido anterior).
        self.voice_engine.iniciar_escuta_continua()

        texto_saudacao, estilo_saudacao = self._saudacao_de_abertura()
        self._falar(texto_saudacao, estilo_saudacao)

        while True:
            try:
                if not self.ciclo_unico():
                    break

            except KeyboardInterrupt:
                print("\nALFA encerrado pelo usuário.")
                break

            except Exception as erro:
                # Nunca deixa uma falha isolada derrubar o assistente:
                # registra o erro e volta a escutar.
                print(f"[ALFA] ERRO CONTROLADO: {erro}")
                estado_beta.definir_estado(EstadoBeta.ERROR)
                try:
                    texto_erro, estilo_erro = self.personality.erro_inesperado()
                    self._falar(texto_erro, estilo_erro)
                except Exception:
                    pass

        # Fecha o stream contínuo de propósito ao sair — o callback do
        # PortAudio roda numa thread nativa que não é necessariamente
        # encerrada só por o processo Python "acabar", então sem isto
        # o processo pode ficar pendurado depois do laço principal
        # terminar (medido durante os testes desta correção).
        self.voice_engine.parar_escuta_continua()

        print("ALFA: Sistema encerrado.")
