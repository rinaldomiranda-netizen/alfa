"""
Contexto de sessão do agente — leve, só em memória (RAM), sem
persistência em disco nesta fase. Memória de longo prazo (sessão
retomável, habilidades aprendidas, preferências) fica para uma fase
futura (ver relatório de auditoria arquitetural).
"""


class ContextoSessao:
    def __init__(self):
        self.usuario_atual = None
        self.ultima_fala = None
        self.ultima_intencao = None
        # Última coisa que a BETA falou de verdade (ver
        # core/alfa_core.py -> _falar) — usado só para "repita"/"pode
        # repetir" (ver core/intent_engine.py -> REPETIR).
        self.ultima_resposta_falada = None
        self.tarefa_atual = None
        self.ferramenta_atual = None
        self.etapa_atual = None
        # Último programa que o agente abriu com sucesso (ver
        # agente/orquestrador.py) — permanece mesmo depois da tarefa
        # terminar (ao contrário de tarefa_atual/etapa_atual), para um
        # pedido seguinte sem o nome do programa poder ser entendido
        # como continuação ("abra o Excel" -> "procure o valor X").
        self.ultimo_programa = None
        # Espaço livre para qualquer dado temporário que uma etapa
        # precise passar adiante para a próxima, sem precisar inventar
        # um campo novo na classe a cada necessidade.
        self.temporarios = {}

        # CONTEXTO DE MÚLTIPLOS RESULTADOS ("procure João" -> 3
        # resultados -> "o segundo"). Cada item é um dict livre (pelo
        # menos "texto"; opcionalmente "posicao"/"endereco"/
        # "ferramenta"/"contexto") — quem produz os resultados decide
        # o formato, quem resolve a referência só usa o índice.
        self.ultimos_resultados = []
        self.ultimo_elemento_selecionado = None

    def definir_resultados(self, resultados, ferramenta=None):
        """Guarda uma nova lista de resultados enumerados (substitui a
        anterior — uma nova busca sempre zera a última)."""
        self.ultimos_resultados = []
        for indice, item in enumerate(resultados or [], start=1):
            entrada = dict(item)
            entrada["indice"] = indice
            entrada.setdefault("ferramenta", ferramenta)
            self.ultimos_resultados.append(entrada)

    def resolver_referencia(self, ordinal):
        """`ordinal`: 1-based (1=primeiro, 2=segundo...) ou -1 para "o
        último". Retorna o dict do resultado, ou None se não houver
        resultados guardados ou o índice não existir — nunca inventa."""
        if not self.ultimos_resultados or ordinal is None:
            return None
        if ordinal == -1:
            return self.ultimos_resultados[-1]
        if 1 <= ordinal <= len(self.ultimos_resultados):
            return self.ultimos_resultados[ordinal - 1]
        return None

    def limpar_resultados(self):
        self.ultimos_resultados = []

    def atualizar_fala(self, texto, intencao=None):
        self.ultima_fala = texto
        if intencao is not None:
            self.ultima_intencao = intencao

    def iniciar_tarefa(self, tarefa):
        self.tarefa_atual = tarefa
        self.ferramenta_atual = None
        self.etapa_atual = None

    def atualizar_progresso(self, etapa):
        self.etapa_atual = etapa
        self.ferramenta_atual = etapa.ferramenta if etapa else None

    def encerrar_tarefa(self):
        self.tarefa_atual = None
        self.ferramenta_atual = None
        self.etapa_atual = None

    def resetar_sessao(self):
        """
        Limpa tudo que é específico de UMA sessão/visitante — usado
        pelo modo totem (ver ui/totem/totem_app.py) ao encerrar o
        atendimento de uma pessoa, para a próxima nunca herdar
        resultado de busca, tarefa em andamento ou referência da
        pessoa anterior. Zera os campos NO MESMO objeto (não troca a
        instância) porque outras partes já guardam referência a este
        ContextoSessao (agente/orquestrador.py, computer/form_filler.py)
        — substituir o objeto as deixaria apontando para um contexto
        velho.

        NUNCA zera `usuario_atual`: isso é identidade/configuração do
        perfil (ex.: nome da organização dona do totem), não do
        visitante de cada sessão.
        """
        self.ultima_fala = None
        self.ultima_intencao = None
        self.ultima_resposta_falada = None
        self.tarefa_atual = None
        self.ferramenta_atual = None
        self.etapa_atual = None
        self.ultimo_programa = None
        self.temporarios = {}
        self.ultimos_resultados = []
        self.ultimo_elemento_selecionado = None
