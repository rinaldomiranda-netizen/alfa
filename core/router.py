"""
Roteador de comandos do ALFA.

Fluxo: texto -> intenção -> parâmetros -> executor local.

Regras:
  - Só comandos que o interpretador NÃO reconhece (intent
    DESCONHECIDO) seguem para o mecanismo de IA de fallback
    (conversa livre). Comandos locais nunca são enviados para fora.
  - VISUALIZAR/CAMERA são intenções locais reconhecidas, mas cuja
    EXECUÇÃO depende de IA multimodal (vision/vision.py) — é o caso
    de "comando que realmente precisa de IA" citado na especificação.
  - Intenções sensíveis (ver security/permissions.py) nunca executam
    direto: o router pede confirmação falada e só executa na frase
    seguinte, se o usuário confirmar.
"""

from security.permissions import (
    CONFIRMACAO_NEGATIVA,
    CONFIRMACAO_POSITIVA,
    INTENCOES_SENSIVEIS,
)

# Estimativa de duração por intenção — usada só para decidir se avisa
# o usuário ANTES de rodar algo demorado (ver GERENCIADOR DE PROGRESSO
# CONVERSACIONAL em core/personality.py -> aviso_espera). Não afeta a
# execução em si; qualquer intent fora deste mapa é tratada como
# imediata/rápida (nenhum aviso prévio).
DEMORADA = "demorada"
MUITO_DEMORADA = "muito_demorada"

DURACAO_ESTIMADA = {
    # Envolvem chamada a um modelo de IA multimodal via rede
    # (vision/vision.py -> Ollama), com timeout de até 60s.
    "VISUALIZAR": MUITO_DEMORADA,
    "CAMERA": MUITO_DEMORADA,
    # Tarefa composta do agente (agente/orquestrador.py): abrir um
    # programa, esperar a janela e digitar — sempre alguns segundos.
    "TAREFA_ABRIR_E_ESCREVER": MUITO_DEMORADA,
    "TAREFA_EXCEL_PROCURAR": MUITO_DEMORADA,
    "TAREFA_EXCEL_SUBSTITUIR": MUITO_DEMORADA,
    # Chamada de rede a um serviço externo (ver core/clima.py).
    "CONSULTAR_CLIMA": DEMORADA,
}


def _normalizar_resposta_simples(intent_engine, texto):
    return intent_engine.normalizar(texto)


def _descreve_intent(intent):
    kind = intent.get("intent")
    programa = intent.get("programa")

    if kind == "FECHAR" and programa:
        return f"fechar {programa}"
    if kind == "FECHAR_JANELA":
        return "fechar a janela ativa"
    if kind == "DESLIGAR_COMPUTADOR":
        return "desligar o computador"
    if kind == "REINICIAR_COMPUTADOR":
        return "reiniciar o computador"
    return kind.replace("_", " ").lower()


class Router:
    def __init__(
        self, intent_engine, executor, brain_fallback=None, vision=None,
        aviso_previo=None, agente=None,
    ):
        self.intent_engine = intent_engine
        self.executor = executor
        self.brain_fallback = brain_fallback
        self.vision = vision
        # Ponte opcional para o agente de computador (ver
        # agente/orquestrador.py:AgenteExecutor) — None em qualquer
        # lugar que ainda construa um Router sem essa opção (ex.:
        # testes existentes), preservando compatibilidade total.
        self.agente = agente
        # Callback opcional (ver core/alfa_core.py -> _aviso_espera),
        # chamado com "demorada"/"muito_demorada" um instante ANTES de
        # uma operação lenta de verdade (IA de conversa livre, visão).
        # O router não sabe falar nem tem acesso a TTS/personalidade —
        # só avisa QUANDO avisar; o texto em si é decidido lá.
        self.aviso_previo = aviso_previo
        self.pendente = None  # intenção sensível aguardando confirmação

    def _resolver_pendencia(self, texto):
        """Trata a resposta do usuário a uma pergunta de confirmação.

        Retorna (resultado, intent) se a pendência foi tratada
        (confirmada, negada, ou abandonada), ou None se não havia
        nenhuma pendência ativa.
        """

        if self.pendente is None:
            return None

        texto_normalizado = _normalizar_resposta_simples(self.intent_engine, texto)
        pendente = self.pendente
        self.pendente = None

        if any(palavra in texto_normalizado for palavra in CONFIRMACAO_POSITIVA):
            resultado = self.executor.executar(pendente)
            return resultado, pendente

        if any(palavra in texto_normalizado for palavra in CONFIRMACAO_NEGATIVA):
            return "Ação cancelada.", {"intent": "CONFIRMACAO_NEGADA"}

        # O usuário disse outra coisa em vez de confirmar/negar: não
        # trava o ALFA esperando para sempre — cancela silenciosamente
        # e deixa a frase nova seguir o fluxo normal.
        return None

    def handle(self, texto, texto_original=None):
        """Processa um comando bruto (já transcrito) e retorna a resposta falada."""

        if texto_original is None:
            texto_original = texto

        pendencia_tratada = self._resolver_pendencia(texto)
        if pendencia_tratada is not None:
            return pendencia_tratada

        intent = self.intent_engine.interpretar(texto, texto_original)
        kind = intent.get("intent")

        if kind == "DESCONHECIDO":
            # Antes da conversa livre em texto puro, dá ao LLM local
            # uma chance de propor um PLANO usando ferramentas já
            # registradas (ver agente/planejador_llm.py) — só tenta
            # quando a fala parece um pedido de ação (filtro barato,
            # evita pagar uma segunda chamada de IA em toda conversa
            # comum). O LLM nunca executa nada diretamente: só nomeia
            # ferramentas que o agente confere contra o registro real.
            if self.agente is not None:
                plano = self.agente.tentar_planejar_com_llm(texto_original)
                if plano is not None:
                    if self.aviso_previo:
                        self.aviso_previo(DEMORADA)
                    mensagem = self.agente.executar_tarefa(plano)
                    return mensagem, intent

            if self.brain_fallback is not None:
                # Conversa livre depende de rede (Ollama) — não é
                # imediata, mas também não costuma passar de alguns
                # segundos: classificada como "demorada", não "muito
                # demorada" (ver VISUALIZAR/CAMERA abaixo).
                if self.aviso_previo:
                    self.aviso_previo(DEMORADA)
                try:
                    resposta = self.brain_fallback(texto_original)
                    return resposta, intent
                except Exception:
                    return "Não consegui processar esse comando agora.", intent

            return (
                "Comando ainda não configurado. Vamos ensinar isso ao ALFA.",
                intent,
            )

        if kind == "CANCELAR_TAREFA":
            # Na prática, uma confirmação pendente já é resolvida ANTES
            # de chegar aqui (ver core/alfa_core.py -> _processar_comando)
            # — este ramo cobre "cancela"/"pare" ditos sem nada em
            # andamento, para nunca virar DESCONHECIDO sem sentido.
            if self.agente is not None and self.agente.tem_confirmacao_pendente():
                return self.agente.resolver_confirmacao(False), intent
            return "Não havia nenhuma tarefa em andamento para cancelar.", intent

        if kind == "CONSULTAR_CLIMA":
            if self.aviso_previo:
                self.aviso_previo(DURACAO_ESTIMADA["CONSULTAR_CLIMA"])
            from core import clima
            resultado_clima = clima.consultar(intent.get("local", ""))
            if resultado_clima is None:
                return (
                    "Não consegui consultar a previsão do tempo agora — "
                    "sem internet ou o serviço está indisponível.",
                    intent,
                )
            return resultado_clima, intent

        if kind == "TAREFA_ABRIR_E_ESCREVER" and self.agente is not None:
            if self.aviso_previo:
                self.aviso_previo(DURACAO_ESTIMADA["TAREFA_ABRIR_E_ESCREVER"])
            mensagem = self.agente.executar_abrir_e_escrever(
                intent.get("programa"), intent.get("texto")
            )
            return mensagem, intent

        if kind in ("SELECIONAR_REFERENCIA", "REFERENCIA_AMBIGUA") and self.agente is not None:
            # Resolve contra os ÚLTIMOS resultados guardados no
            # contexto (ver agente/contexto.py) — nunca inventa; sem
            # contexto suficiente, devolve a mensagem honesta.
            return self.agente.selecionar_resultado(intent.get("ordinal")), intent

        if kind == "CLICAR_REFERENCIA" and self.agente is not None:
            return self.agente.clicar_referencia(), intent

        if kind == "LER_TELA_AGENTE" and self.agente is not None:
            return self.agente.ler_tela(), intent

        if kind == "ROLAR_ATE_ENCONTRAR" and self.agente is not None:
            return self.agente.rolar_ate_encontrar(intent.get("alvo")), intent

        if kind == "ABRIR" and not intent.get("programa") and self.agente is not None:
            # A whitelist fixa antiga (security/permissions.py:
            # PROGRAMAS_ABRIR) não reconheceu o nome pedido — em vez de
            # desistir ("Não entendi qual programa..."), tenta a
            # descoberta real de aplicativos do agente antes de
            # responder. Só entra aqui quando "programa" veio vazio;
            # qualquer programa já reconhecido pela whitelist segue o
            # caminho de sempre, sem mudança nenhuma.
            if self.aviso_previo:
                self.aviso_previo(DEMORADA)
            return self.agente.abrir_aplicativo_generico(intent.get("programa_bruto")), intent

        if kind == "TAREFA_EXCEL_PROCURAR" and self.agente is not None:
            if self.aviso_previo:
                self.aviso_previo(DURACAO_ESTIMADA["TAREFA_EXCEL_PROCURAR"])
            return self.agente.executar_excel_procurar(intent.get("valor")), intent

        if kind == "TAREFA_EXCEL_SUBSTITUIR" and self.agente is not None:
            if self.aviso_previo:
                self.aviso_previo(DURACAO_ESTIMADA["TAREFA_EXCEL_SUBSTITUIR"])
            return self.agente.executar_excel_substituir(intent.get("de"), intent.get("para")), intent

        if kind == "VISUALIZAR" and self.vision is not None:
            if self.aviso_previo:
                self.aviso_previo(DURACAO_ESTIMADA["VISUALIZAR"])
            return self.vision.analisar_tela(), intent

        if kind == "CAMERA" and self.vision is not None:
            if self.aviso_previo:
                self.aviso_previo(DURACAO_ESTIMADA["CAMERA"])
            return self.vision.analisar_camera(), intent

        if kind in INTENCOES_SENSIVEIS:
            # Sem programa identificado não há o que confirmar: deixa o
            # executor responder que não entendeu, sem travar em uma
            # pergunta de confirmação vazia.
            if kind == "FECHAR" and not intent.get("programa"):
                resultado = self.executor.executar(intent)
                return resultado, intent

            self.pendente = intent
            descricao = _descreve_intent(intent)

            intent_pergunta = dict(intent)
            intent_pergunta["_pedido_confirmacao"] = True

            return (
                f"Tem certeza que deseja {descricao}? Diga 'sim' para confirmar.",
                intent_pergunta,
            )

        resultado = self.executor.executar(intent)
        return resultado, intent
