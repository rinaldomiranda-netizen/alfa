"""
Ponte entre core/router.py e o planejador (agente/planejador.py):
constrói a Tarefa certa para um pedido e roda através do
ExecutorDePlano, atualizando o contexto de sessão e o indicador visual
real durante a execução — nunca fingindo sucesso.

Dois caminhos para compor uma tarefa:
  1. `construir_tarefa_abrir_e_escrever` — regra fixa e determinística
     para "abra X e escreva Y" (ver core/intent_engine.py), usando o
     skill de Office (skills/word) quando o programa for Word e ele
     estiver disponível, ou o caminho genérico (abrir + Ctrl+N +
     digitar + OCR) para qualquer outro programa.
  2. `AgenteExecutor.tentar_planejar_com_llm` — para pedidos que o
     Intent Engine não reconhece, mas que parecem uma tarefa (ver
     agente/planejador_llm.py). O LLM só pode escolher ferramentas já
     registradas — nunca executa texto livre.
"""

from agente.planejador import Etapa, ExecutorDePlano, ResultadoDaEtapa, StatusEtapa, Tarefa
from ui.estado_beta import EstadoBeta, estado_beta

# Espera fixa depois que a janela do programa aparece, antes de tentar
# interagir com ele: a janela pode existir (título já visível) antes
# do programa terminar de ficar pronto para receber atalhos/COM. É uma
# folga pragmática, não uma verificação de verdade.
PAUSA_APOS_ABRIR_SEGUNDOS = 1.5

# Ferramentas que ABREM um programa — usadas para atualizar
# contexto.ultimo_programa (ver CONTEXTO DE TAREFA) depois de uma
# tarefa bem-sucedida, para um pedido seguinte sem nome de programa
# ("procure o valor 500") poder ser entendido como continuação.
_FERRAMENTAS_QUE_ABREM_APP = {
    "abrir_aplicativo": "programa",  # nome vem do parâmetro
    "word_abrir": "word",
    "excel_abrir": "excel",
    "powerpoint_abrir": "powerpoint",
    "navegador_abrir": "navegador",
}


def _construir_tarefa_word(texto):
    etapas = [
        Etapa(
            objetivo="Abrir o Word",
            ferramenta="word_abrir",
            resultado_esperado="Word aberto",
            verificacao="chamada COM confirma app ativo",
            tratamento_erro="Não consegui abrir o Word neste computador.",
        ),
        Etapa(
            objetivo="Criar um documento novo",
            ferramenta="word_novo_documento",
            resultado_esperado="Documento em branco",
            tratamento_erro="Abri o Word, mas não consegui criar um documento novo.",
        ),
        Etapa(
            objetivo="Escrever o texto pedido",
            ferramenta="word_escrever",
            parametros={"texto": texto},
            resultado_esperado="Texto no documento",
            verificacao="Word.Selection.Find relê o documento procurando o texto",
            tratamento_erro="Escrevi, mas não consegui confirmar o texto no documento.",
        ),
    ]
    return Tarefa(objetivo_geral="Abrir o Word e escrever o texto pedido", etapas=etapas)


def _construir_tarefa_generica(programa, texto):
    programa_norm = (programa or "").strip().lower()
    etapas = [
        Etapa(
            objetivo=f"Localizar e abrir '{programa_norm}'",
            ferramenta="abrir_aplicativo",
            parametros={"programa": programa_norm},
            resultado_esperado=f"Janela de {programa_norm} aberta",
            verificacao=f"janela contendo '{programa_norm}' aparece em até 8s (poll)",
            tratamento_erro=f"Não encontrei o {programa_norm} neste computador.",
            pausa_apos=PAUSA_APOS_ABRIR_SEGUNDOS,
        ),
        Etapa(
            objetivo="Criar um documento/arquivo novo",
            ferramenta="pressionar_tecla",
            parametros={"teclas": ("ctrl", "n")},
            resultado_esperado="Documento em branco pronto para digitação",
            verificacao="não verificável de forma genérica nesta fase",
            tratamento_erro=f"Abri o {programa_norm}, mas não consegui criar um documento novo.",
        ),
        Etapa(
            objetivo="Escrever o texto pedido",
            ferramenta="digitar",
            parametros={"texto": texto},
            resultado_esperado="Texto visível no documento",
            verificacao="OCR local relê a tela e procura um trecho do texto digitado",
            tratamento_erro="Escrevi, mas não consegui confirmar o texto na tela.",
        ),
    ]
    return Tarefa(
        objetivo_geral=f"Abrir {programa_norm} e escrever o texto pedido",
        etapas=etapas,
    )


def construir_tarefa_abrir_e_escrever(programa, texto):
    if (programa or "").strip().lower() in ("word", "microsoft word"):
        return _construir_tarefa_word(texto)
    return _construir_tarefa_generica(programa, texto)


def construir_tarefa_excel_procurar(valor):
    """
    Três etapas de verdade encadeadas pelo Planner (ver
    agente/planejador.py -> ResultadoDaEtapa): a 3ª usa o ENDEREÇO
    achado pela 2ª como parâmetro — não é uma função monolítica, é o
    Planner passando dado real de uma etapa para a próxima. A releitura
    também serve como Verifier: confirma de verdade o que está na
    célula encontrada, em vez de só informar a posição.
    """
    etapas = [
        Etapa(
            objetivo="Abrir o Excel",
            ferramenta="excel_abrir",
            tratamento_erro="Não consegui abrir o Excel neste computador.",
        ),
        Etapa(
            objetivo=f"Procurar '{valor}' na planilha",
            ferramenta="excel_localizar_valor",
            parametros={"valor": valor},
            verificacao="Cells.Find relê a planilha; a própria célula é selecionada ao achar",
            tratamento_erro=f"Não encontrei '{valor}' na planilha.",
        ),
        Etapa(
            objetivo="Reler o valor da célula encontrada (confirmação)",
            ferramenta="excel_ler_valor",
            parametros={"endereco": ResultadoDaEtapa(2, campo="endereco")},
            verificacao="relê a célula pelo endereço achado na etapa anterior",
            tratamento_erro="Encontrei a célula, mas não consegui confirmar o valor ao reler.",
        ),
    ]
    return Tarefa(objetivo_geral=f"Procurar '{valor}' no Excel", etapas=etapas)


def construir_tarefa_excel_substituir(de, para):
    etapas = [
        Etapa(
            objetivo="Abrir o Excel",
            ferramenta="excel_abrir",
            tratamento_erro="Não consegui abrir o Excel neste computador.",
        ),
        Etapa(
            objetivo=f"Trocar '{de}' por '{para}'",
            ferramenta="excel_localizar_e_substituir",
            parametros={"valor_antigo": de, "valor_novo": para},
            verificacao="relê a célula depois de alterar e confirma o valor novo",
            tratamento_erro=f"Não consegui trocar '{de}' por '{para}'.",
        ),
    ]
    return Tarefa(objetivo_geral=f"Trocar '{de}' por '{para}' no Excel", etapas=etapas)


class AgenteExecutor:
    """Ponte entre core/router.py e o planejador — atualiza o contexto
    de sessão e o indicador visual real durante a execução."""

    def __init__(self, registro, contexto=None, ollama_url=None, ollama_modelo=None):
        self.registro = registro
        self.contexto = contexto
        self.ollama_url = ollama_url
        self.ollama_modelo = ollama_modelo
        # (tarefa, indice_etapa_pendente) enquanto uma etapa
        # SENSITIVE/SYSTEM espera confirmação falada — ver
        # tem_confirmacao_pendente/resolver_confirmacao, chamados por
        # core/alfa_core.py na fala seguinte.
        self._pendente = None

    def _on_progresso(self, indice, total, etapa):
        if self.contexto is not None:
            self.contexto.atualizar_progresso(etapa)
        estado_beta.definir_estado(EstadoBeta.EXECUTING, detalhe=f"etapa {indice}/{total}")

    def executar_tarefa(self, tarefa, mensagem_sucesso=None, indice_inicial=1, confirmado=False):
        """Roda qualquer Tarefa já montada (fixa ou proposta pelo LLM)
        pelo mesmo caminho: ExecutorDePlano, nunca fingindo sucesso."""
        estado_beta.definir_estado(EstadoBeta.PLANNING)

        if self.contexto is not None:
            self.contexto.iniciar_tarefa(tarefa)

        executor_plano = ExecutorDePlano(self.registro)
        relatorio = executor_plano.executar(
            tarefa, on_progresso=self._on_progresso,
            indice_inicial=indice_inicial, confirmado=confirmado,
        )

        if relatorio.aguardando_confirmacao:
            # Guarda a tarefa PARADA na etapa que precisa de "sim" —
            # não encerra o contexto, a tarefa ainda está em andamento.
            self._pendente = (tarefa, relatorio.indice_etapa_pendente, mensagem_sucesso)
            return relatorio.mensagem_final

        if relatorio.sucesso and self.contexto is not None:
            self._atualizar_ultimo_programa(tarefa)

        if self.contexto is not None:
            self.contexto.encerrar_tarefa()

        if relatorio.sucesso:
            return mensagem_sucesso or relatorio.mensagem_final or "Pronto."
        return relatorio.mensagem_final

    def _atualizar_ultimo_programa(self, tarefa):
        for etapa in tarefa.etapas:
            chave_parametro = _FERRAMENTAS_QUE_ABREM_APP.get(etapa.ferramenta)
            if chave_parametro is None:
                continue
            if chave_parametro == "programa":
                self.contexto.ultimo_programa = etapa.parametros.get("programa")
            else:
                self.contexto.ultimo_programa = chave_parametro

    def tem_confirmacao_pendente(self):
        return self._pendente is not None

    def resolver_confirmacao(self, confirmado):
        """
        Chamado por core/alfa_core.py quando a fala seguinte a um
        pedido de confirmação de ferramenta é "sim"/"não". Se
        confirmado, RETOMA a tarefa exatamente da etapa que estava
        esperando (não recomeça do início); se negado, cancela.
        """
        if self._pendente is None:
            return "Não havia nada pendente para confirmar."

        tarefa, indice_pendente, mensagem_sucesso = self._pendente
        self._pendente = None

        if not confirmado:
            tarefa.status = StatusEtapa.CANCELLED
            if self.contexto is not None:
                self.contexto.encerrar_tarefa()
            return "Ação cancelada."

        return self.executar_tarefa(
            tarefa, mensagem_sucesso=mensagem_sucesso,
            indice_inicial=indice_pendente, confirmado=True,
        )

    def executar_abrir_e_escrever(self, programa, texto):
        tarefa = construir_tarefa_abrir_e_escrever(programa, texto)
        programa_norm = (programa or "").strip().lower()
        return self.executar_tarefa(
            tarefa,
            mensagem_sucesso=f"Pronto. Abri o {programa_norm} e escrevi o texto pedido.",
        )

    def abrir_aplicativo_generico(self, nome_bruto):
        """
        Fallback para "abra o X" quando X não está na whitelist fixa
        antiga (security/permissions.py:PROGRAMAS_ABRIR, ~12 programas)
        — usa a descoberta real (PATH, registro do Windows, Menu
        Iniciar, ver agente/descoberta_apps.py). `nome_bruto` vem cru
        do que a pessoa falou (ex.: "o word"), por isso remove artigo
        antes de procurar.

        Se o nome não bater exatamente (ex.: Whisper transcreveu
        "Word" como "urde"), tenta a RESOLUÇÃO CONTEXTUAL: só aceita
        um candidato que já esteja de verdade instalado nesta máquina
        (nunca inventa um programa) — ver
        descoberta_apps.resolve_aplicativo_falado.
        """
        import re as _re
        from agente import descoberta_apps

        nome = _re.sub(r"^(o|a|os|as)\s+", "", (nome_bruto or "").strip(), flags=_re.IGNORECASE).strip()
        if not nome:
            return "Não entendi qual programa você quer abrir."

        estado_beta.definir_estado(EstadoBeta.WORKING)

        # 1) Nome exato (rápido, sem heurística nenhuma).
        if descoberta_apps.localizar_executavel(nome):
            resultado = self.registro.executar("abrir_aplicativo", programa=nome)
            if resultado.sucesso and self.contexto is not None:
                self.contexto.ultimo_programa = nome
            return resultado.mensagem

        # 2) Resolução contextual — só contra o que está REALMENTE
        # instalado aqui, nunca uma lista fixa de nomes possíveis.
        disponiveis = {}
        for candidato in descoberta_apps.NOMES_EXECUTAVEL:
            caminho = descoberta_apps.localizar_executavel(candidato)
            if caminho:
                disponiveis[candidato] = caminho

        resolvido, confianca, candidatos = descoberta_apps.resolve_aplicativo_falado(nome, disponiveis)
        print(f"[APP RESOLVER] '{nome}' -> {resolvido!r} (confianca={confianca}, candidatos={candidatos})")

        if confianca == descoberta_apps.CONFIANCA_BAIXA or resolvido is None:
            return "Não encontrei esse programa neste computador."

        if confianca == descoberta_apps.CONFIANCA_MEDIA:
            if len(candidatos) > 1:
                opcoes = " ou ".join(c.title() for c in candidatos)
                return f"Você quis dizer {opcoes}?"
            return f"Você quis dizer {resolvido.title()}?"

        # confiança ALTA: abre direto, já confirmado que existe de verdade.
        resultado = self.registro.executar("abrir_aplicativo", programa=resolvido)
        if resultado.sucesso and self.contexto is not None:
            self.contexto.ultimo_programa = resolvido
        return resultado.mensagem

    def ler_tela(self):
        """Chamada direta (sem Planner — é uma única ferramenta, não
        uma tarefa composta) para "Beta, leia a tela" (ver
        core/intent_engine.py -> LER_TELA_AGENTE)."""
        from agente.leitura_tela import resumo_legivel

        estado_beta.definir_estado(EstadoBeta.WORKING)
        resultado = self.registro.executar("ler_tela")
        if not resultado.sucesso or not isinstance(resultado.mensagem, dict):
            return "Não consegui ler a tela agora."
        return resumo_legivel(resultado.mensagem["estrutura"])

    def rolar_ate_encontrar(self, alvo, direcao="baixo"):
        estado_beta.definir_estado(EstadoBeta.WORKING)
        resultado = self.registro.executar("rolar_para_elemento", alvo=alvo, direcao=direcao)
        if not resultado.sucesso:
            return resultado.mensagem
        # Guarda o elemento achado como "último" (ver
        # core/intent_engine.py -> CLICAR_REFERENCIA): permite "clique
        # naquele" logo depois, sem repetir o nome do alvo.
        if self.contexto is not None and isinstance(resultado.mensagem, dict):
            self.contexto.ultimo_elemento_selecionado = {
                "texto": alvo,
                "posicao": resultado.mensagem.get("posicao"),
            }
        return f"Encontrei '{alvo}'."

    def clicar_referencia(self):
        """
        Resolve "clique naquele"/"clique nisso" contra o último
        elemento encontrado (ver rolar_ate_encontrar acima e
        agente/contexto.py) — nunca clica numa coordenada inventada.
        """
        item = self.contexto.ultimo_elemento_selecionado if self.contexto is not None else None
        if item is None or not item.get("posicao"):
            return "Não consegui identificar em qual elemento você quer clicar."

        try:
            import pyautogui
            pyautogui.click(*item["posicao"])
            return f"Cliquei em '{item.get('texto', 'esse elemento')}'."
        except Exception as erro:
            return f"Encontrei o elemento, mas não consegui clicar: {erro}"

    def executar_excel_procurar(self, valor):
        """
        Abre o Excel e localiza TODAS as ocorrências de `valor` (não só
        a primeira) — fica numa função própria (em vez de Etapas do
        Planner) porque decidir "responder direto" vs. "enumerar e
        guardar contexto" depende de QUANTOS resultados vieram, uma
        ramificação que o Planner linear ainda não expressa (mesmo
        motivo de skills/excel/localizar_e_substituir).
        """
        estado_beta.definir_estado(EstadoBeta.PLANNING)

        resultado_abrir = self.registro.executar("excel_abrir")
        if not resultado_abrir.sucesso:
            return resultado_abrir.mensagem

        estado_beta.definir_estado(EstadoBeta.EXECUTING, detalhe="etapa 2/2")
        resultado_busca = self.registro.executar("excel_localizar_todos", valor=valor)
        if not resultado_busca.sucesso:
            return resultado_busca.mensagem

        resultados = (resultado_busca.dados or {}).get("resultados", [])
        if self.contexto is not None:
            self.contexto.definir_resultados(resultados, ferramenta="excel_selecionar_celula")
            self.contexto.ultimo_programa = "excel"

        if len(resultados) <= 1:
            return resultado_busca.mensagem

        nomes_ordinais = ["primeiro", "segundo", "terceiro", "quarto", "quinto"]
        partes = []
        for item in resultados[:5]:
            rotulo = nomes_ordinais[item["indice"] - 1] if item["indice"] <= 5 else f"{item['indice']}º"
            partes.append(f"o {rotulo} na célula {item['endereco']}")
        return f"Encontrei {len(resultados)} ocorrências de '{valor}': " + ", ".join(partes) + "."

    def resolver_referencia(self, ordinal):
        """Resolve "o segundo"/"o último" contra os últimos resultados
        do contexto — nunca inventa (ver agente/contexto.py)."""
        if self.contexto is None:
            return None
        return self.contexto.resolver_referencia(ordinal)

    def selecionar_resultado(self, ordinal):
        """
        Usado tanto por "selecione o segundo" quanto por "o segundo"
        sozinho (ver core/router.py) — resolve a referência e, quando
        a ferramenta de origem permitir (ex.: uma célula do Excel),
        seleciona de verdade; sempre verificando, nunca fingindo.
        """
        resolvido = self.resolver_referencia(ordinal)
        if resolvido is None:
            return "Não consegui identificar qual resultado você quis dizer."

        if self.contexto is not None:
            self.contexto.ultimo_elemento_selecionado = resolvido

        ferramenta_origem = resolvido.get("ferramenta")
        endereco = resolvido.get("endereco")
        if ferramenta_origem == "excel_selecionar_celula" and endereco:
            resultado = self.registro.executar("excel_selecionar_celula", endereco=endereco)
            return resultado.mensagem

        texto_item = resolvido.get("texto") or "esse item"
        return f"Certo, é o item: {texto_item}."

    def executar_excel_substituir(self, de, para):
        tarefa = construir_tarefa_excel_substituir(de, para)
        return self.executar_tarefa(tarefa)

    def tentar_planejar_com_llm(self, pedido):
        """
        Pergunta ao Ollama (se configurado) como cumprir `pedido` com
        as ferramentas já registradas. Retorna uma Tarefa (1+ etapas
        já validadas contra o registro) ou None — nunca executa nada
        aqui, só planeja (ver executar_tarefa para rodar de verdade).
        """
        if not self.ollama_url or not self.ollama_modelo:
            return None

        from agente.planejador_llm import parece_tarefa, propor_plano

        if not parece_tarefa(pedido):
            return None

        # CONTEXTO DE TAREFA: se o pedido não nomeia um programa e um
        # já está em uso (ver _atualizar_ultimo_programa), avisa o LLM
        # — "abra o Excel" -> "procure o valor 500" deve ser entendido
        # como continuação no Excel recém-aberto, não uma ação solta.
        contexto_extra = None
        if self.contexto is not None and self.contexto.ultimo_programa:
            contexto_extra = (
                f"Contexto: o último programa que a Beta abriu foi "
                f"'{self.contexto.ultimo_programa}'. Se o pedido do "
                f"usuário não disser outro programa, assuma que é sobre "
                f"esse."
            )

        return propor_plano(
            pedido, self.registro, self.ollama_url, self.ollama_modelo,
            contexto_extra=contexto_extra,
        )
