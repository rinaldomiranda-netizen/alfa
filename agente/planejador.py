"""
Planejador mínimo do agente: representa uma tarefa composta como uma
sequência LINEAR de etapas, cada uma usando uma ferramenta genérica do
Tool Registry (agente/ferramentas.py). Não tem IA nem ramificação
condicional — só o suficiente para provar que ferramentas genéricas
podem ser combinadas num fluxo verificável (ver agente/orquestrador.py
para o primeiro fluxo real). Planejamento com IA/ramificação fica para
uma fase futura.
"""

import enum
import time
import uuid


class StatusEtapa(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    CANCELLED = "cancelled"


class ResultadoDaEtapa:
    """
    Placeholder usado em `Etapa.parametros` para dizer "pegue este
    valor do RESULTADO de uma etapa ANTERIOR já executada" — é o que
    permite ao Planner encadear etapas onde a segunda precisa de um
    dado que só existe depois da primeira rodar (ex.: o endereço de
    uma célula achada por "excel_localizar_valor" virando parâmetro de
    "excel_ler_valor"). Resolvido em ExecutorDePlano antes de chamar a
    ferramenta — nunca chega cru na função da ferramenta.
    """

    def __init__(self, indice_etapa, campo=None):
        # indice_etapa: posição 1-based da etapa cujo resultado se quer.
        self.indice_etapa = indice_etapa
        # campo: se resultado.dados for um dict, qual chave pegar;
        # None = usa resultado.mensagem direto.
        self.campo = campo


class Etapa:
    def __init__(
        self,
        objetivo,
        ferramenta,
        parametros=None,
        resultado_esperado="",
        verificacao="",
        tratamento_erro=None,
        pausa_apos=0.0,
        max_tentativas=1,
        ferramenta_alternativa=None,
        parametros_alternativos=None,
        id=None,
    ):
        self.id = id or uuid.uuid4().hex[:8]
        self.objetivo = objetivo
        self.ferramenta = ferramenta
        self.parametros = parametros or {}
        self.resultado_esperado = resultado_esperado
        # Descrição de COMO esta etapa é verificada — documentação; a
        # verificação de verdade é feita pela própria ferramenta (ver
        # Ferramenta.verificador em agente/ferramentas.py).
        self.verificacao = verificacao
        # Mensagem falada quando esta etapa falha sem recuperação (nem
        # tentativas nem alternativa resolveram).
        self.tratamento_erro = tratamento_erro
        # Espera fixa (segundos) depois de uma verificação bem
        # sucedida, antes da próxima etapa — mitigação pragmática para
        # programas que "existem" (janela apareceu) mas ainda não
        # terminaram de inicializar a UI. Não é uma verificação de
        # verdade, é só uma folga; ver limitações no relatório final.
        self.pausa_apos = pausa_apos
        # RECUPERAÇÃO (ver ExecutorDePlano.executar): quantas vezes
        # tentar a MESMA ferramenta antes de desistir ou tentar a
        # alternativa. Nunca repete indefinidamente.
        self.max_tentativas = max(1, max_tentativas)
        self.tentativas_realizadas = 0
        # Estratégia alternativa SEGURA (ver relatório de auditoria,
        # item 2 do pedido "recuperação visual"): se a ferramenta
        # principal esgotar as tentativas, tenta esta uma vez antes de
        # desistir de verdade. Ex.: clicar_elemento (UI Automation)
        # falhando -> tentar localizar via OCR antes de recorrer a
        # coordenadas fixas.
        self.ferramenta_alternativa = ferramenta_alternativa
        self.parametros_alternativos = parametros_alternativos or {}
        # Preenchido por Tarefa.__init__, de acordo com a ordem da
        # lista — um plano linear não precisa de grafo, só de
        # sequência.
        self.proxima_etapa = None
        self.status = StatusEtapa.PENDING
        self.resultado = None  # ResultadoFerramenta, depois de rodar


class Tarefa:
    def __init__(self, objetivo_geral, etapas):
        self.id = uuid.uuid4().hex[:8]
        self.objetivo_geral = objetivo_geral
        self.etapas = list(etapas)
        for atual, seguinte in zip(self.etapas, self.etapas[1:]):
            atual.proxima_etapa = seguinte.id
        self.status = StatusEtapa.PENDING


class RelatorioExecucao:
    def __init__(self, tarefa):
        self.tarefa = tarefa
        self.sucesso = False
        self.mensagem_final = ""
        # Preenchido só quando uma etapa SENSITIVE/SYSTEM (ver
        # security/permissions.py) pede confirmação antes de rodar —
        # o índice (1-based, mesma contagem de on_progresso) da etapa
        # parada, para o chamador poder retomar dali (ver
        # ExecutorDePlano.executar(..., indice_inicial=...) e
        # agente/orquestrador.py:AgenteExecutor).
        self.aguardando_confirmacao = False
        self.indice_etapa_pendente = None

    def resumo_etapas(self):
        return [
            (etapa.objetivo, etapa.status.value, etapa.resultado.mensagem if etapa.resultado else None)
            for etapa in self.tarefa.etapas
        ]


class ExecutorDePlano:
    """
    Executa uma Tarefa etapa por etapa, sempre em ordem, parando no
    primeiro erro sem tratamento — nunca finge que uma etapa que
    falhou (ou cuja verificação deu False) teve sucesso.
    """

    def __init__(self, registro):
        self.registro = registro

    def _resolver_parametros(self, parametros, tarefa):
        """Troca qualquer ResultadoDaEtapa pelo valor de verdade do
        resultado da etapa referenciada — nunca deixa o placeholder
        vazar para dentro da função da ferramenta."""
        resolvidos = {}
        for chave, valor in parametros.items():
            if not isinstance(valor, ResultadoDaEtapa):
                resolvidos[chave] = valor
                continue

            indice = valor.indice_etapa - 1
            if indice < 0 or indice >= len(tarefa.etapas):
                resolvidos[chave] = None
                continue

            resultado_fonte = tarefa.etapas[indice].resultado
            if resultado_fonte is None:
                resolvidos[chave] = None
            elif valor.campo and isinstance(resultado_fonte.dados, dict):
                resolvidos[chave] = resultado_fonte.dados.get(valor.campo)
            else:
                resolvidos[chave] = resultado_fonte.mensagem
        return resolvidos

    def executar(self, tarefa, on_progresso=None, indice_inicial=1, confirmado=False):
        """
        `indice_inicial` (1-based) permite RETOMAR uma tarefa que
        parou esperando confirmação, em vez de rodar tudo de novo do
        zero — ver agente/orquestrador.py:AgenteExecutor.
        `confirmado` só vale para a PRIMEIRA etapa rodada nesta
        chamada (a que estava esperando confirmação); as demais nunca
        precisam dele porque não são SENSITIVE/SYSTEM (isso é
        garantido pelo próprio registro, ver
        security.permissions.CATEGORIAS_QUE_EXIGEM_CONFIRMACAO).
        """
        tarefa.status = StatusEtapa.RUNNING
        total = len(tarefa.etapas)

        for indice, etapa in enumerate(tarefa.etapas, start=1):
            if indice < indice_inicial:
                continue

            if on_progresso is not None:
                try:
                    on_progresso(indice, total, etapa)
                except Exception:
                    pass

            confirmado_desta_etapa = confirmado if indice == indice_inicial else False
            deu_certo = False
            resultado = None

            # RECUPERAÇÃO: tenta a ferramenta principal até
            # max_tentativas vezes (nunca indefinidamente); entre uma
            # tentativa e outra, dá uma folga curta para o estado da
            # tela/aplicativo se assentar antes de checar de novo.
            for tentativa in range(1, etapa.max_tentativas + 1):
                etapa.tentativas_realizadas = tentativa
                etapa.status = StatusEtapa.RUNNING
                parametros_resolvidos = self._resolver_parametros(etapa.parametros, tarefa)
                resultado = self.registro.executar(
                    etapa.ferramenta,
                    confirmado=(confirmado_desta_etapa and tentativa == 1),
                    **parametros_resolvidos,
                )
                etapa.resultado = resultado

                if resultado.requer_confirmacao:
                    etapa.status = StatusEtapa.WAITING_CONFIRMATION
                    tarefa.status = StatusEtapa.WAITING_CONFIRMATION
                    relatorio = RelatorioExecucao(tarefa)
                    relatorio.sucesso = False
                    relatorio.aguardando_confirmacao = True
                    relatorio.indice_etapa_pendente = indice
                    relatorio.mensagem_final = (
                        f"{resultado.mensagem} Diga 'sim' para confirmar, ou 'não' para cancelar."
                    )
                    return relatorio

                # verificado is False -> a etapa RODOU mas
                # confirmadamente NÃO deu o resultado esperado.
                # verificado is None -> não dava para confirmar; nesse
                # caso, confia no sucesso da própria chamada (não tem
                # como fazer melhor sem inventar).
                deu_certo = resultado.sucesso and resultado.verificado is not False
                if deu_certo:
                    break
                if tentativa < etapa.max_tentativas:
                    time.sleep(0.8)

            etapa.status = StatusEtapa.SUCCESS if deu_certo else StatusEtapa.FAILED

            # Esgotou as tentativas da ferramenta principal: tenta a
            # alternativa SEGURA uma única vez antes de desistir de
            # verdade (ex.: elemento por UI Automation falhou -> tenta
            # de novo depois de reler a tela via OCR).
            if not deu_certo and etapa.ferramenta_alternativa:
                resultado = self.registro.executar(
                    etapa.ferramenta_alternativa, **etapa.parametros_alternativos
                )
                etapa.resultado = resultado
                deu_certo = resultado.sucesso and resultado.verificado is not False
                etapa.status = StatusEtapa.SUCCESS if deu_certo else StatusEtapa.FAILED

            if not deu_certo:
                tarefa.status = StatusEtapa.FAILED
                relatorio = RelatorioExecucao(tarefa)
                relatorio.sucesso = False
                relatorio.mensagem_final = (
                    etapa.tratamento_erro
                    if isinstance(etapa.tratamento_erro, str) and etapa.tratamento_erro
                    else resultado.mensagem
                )
                return relatorio

            if etapa.pausa_apos:
                time.sleep(etapa.pausa_apos)

        tarefa.status = StatusEtapa.SUCCESS
        relatorio = RelatorioExecucao(tarefa)
        relatorio.sucesso = True
        relatorio.mensagem_final = tarefa.etapas[-1].resultado.mensagem if tarefa.etapas else ""
        return relatorio
