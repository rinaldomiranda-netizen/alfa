"""
Personalidade da BETA — assistente/secretária digital pessoal de Rinaldo.

    INTENÇÃO + RESULTADO -> [Personality] -> TEXTO FINAL + ESTILO

Conceito de identidade:
    Rinaldo = usuário principal e comandante.
    Beta    = assistente/secretária digital pessoal dele.

Esta é a única camada que decide COMO a assistente fala (nome que usa
para si mesma, tom, forma de tratar o Rinaldo, humor). Ela nunca fala
com o sistema operacional nem com um motor de TTS — só recebe o
resultado factual já pronto (do executor/roteador) e devolve um texto
pronto para narrar, mais uma tag de estilo emocional que o VoiceOutput
repassa ao motor de voz configurado (ver voice/voice_output.py).

Isso mantém a separação pedida:
    PERSONALIDADE -> TEXTO -> TTS -> ÁUDIO
Trocar a personalidade (outro nome, outro tom) não exige tocar em
core/router.py, computer/executor.py, nos motores de voz, nem em
nenhum nome interno de arquivo/classe/módulo do projeto ALFA — a
identidade apresentada ao usuário é só o que esta camada decide dizer.
"""

from datetime import datetime

NOME_USUARIO_PADRAO = "Rinaldo"
NOME_ASSISTENTE_PADRAO = "Beta"

# Fato histórico fixo — quem criou o projeto ALFA/BETA nunca muda,
# mesmo quando self.nome_usuario é outra pessoa/empresa (ver BETA
# PORTÁTIL em launcher/iniciar_portatil.py). Nunca usar
# self.nome_usuario para responder "quem te criou"/história.
NOME_CRIADOR = "Rinaldo"

ABERTURAS_CONFIRMACAO = ["Claro", "Certo", "Pronto", "Perfeito", "Entendi"]
ABERTURAS_SERIA = ["Certo", "Entendido"]
ABERTURAS_EMPATICA = ["Puxa", "Poxa", "Ih"]

PALAVRAS_ERRO = [
    "não consegui", "nao consegui",
    "não entendi", "nao entendi",
    "não está aberto", "nao esta aberto",
    "não conheço", "nao conheco",
    "não tenho", "nao tenho",
    "encontrei um problema",
    "erro:",
]

# Falhas de operações que dependem de rede/IA (conversa livre, visão)
# — ao contrário de um erro comum (ex.: "programa não está aberto"),
# faz sentido oferecer tentar de novo, já que a causa costuma ser
# passageira (serviço fora do ar, timeout). Ver Personality.compor e
# core/alfa_core.py -> _processar_comando (retentativa por voz).
PREFIXOS_FALHA_RETENTAVEL = (
    "não consegui processar esse comando agora",
    "não consegui analisar",
    "não consegui acessar a câmera",
)

AVISOS_ESPERA_DEMORADA = ["Só um instante", "Um momento", "Espera um pouquinho"]
AVISOS_ESPERA_MUITO_DEMORADA = [
    "Isso pode levar alguns segundos, só um instante",
    "Um momento, isso exige um pouco mais de atenção",
]


def eh_falha_retentavel(texto):
    """Diz se `texto` é uma dessas falhas de rede/IA para as quais faz
    sentido oferecer/aceitar uma nova tentativa (ver
    core/alfa_core.py)."""
    texto_lower = str(texto).lower()
    return any(texto_lower.startswith(p) for p in PREFIXOS_FALHA_RETENTAVEL)

INTENTS_ACAO_SERIA = {
    "DESLIGAR_COMPUTADOR",
    "REINICIAR_COMPUTADOR",
    "FECHAR",
    "FECHAR_JANELA",
    "CANCELAR_DESLIGAMENTO",
}


class Personality:
    """
    Estilo de fala da Beta: secretária digital pessoal de Rinaldo —
    profissional quando o momento pede, descontraída quando o
    contexto permite, com humor leve e contextual, mas nunca a ponto
    de atrapalhar a execução de um comando (a piada, quando cabe,
    sempre vem DEPOIS do fato relatado, nunca no lugar dele).
    """

    def __init__(self, nome_usuario=NOME_USUARIO_PADRAO, nome_assistente=NOME_ASSISTENTE_PADRAO):
        self.nome_usuario = nome_usuario
        self.nome_assistente = nome_assistente
        self._contador_aberturas = 0

    def _proxima_abertura(self, opcoes):
        opcao = opcoes[self._contador_aberturas % len(opcoes)]
        self._contador_aberturas += 1
        return opcao

    def saudacao_inicial(self):
        hora = datetime.now().hour

        if hora < 12:
            texto = (
                f"Bom dia, {self.nome_usuario}. A {self.nome_assistente} está "
                "pronta. Como posso ajudá-lo?"
            )
        elif hora < 18:
            texto = f"Boa tarde, {self.nome_usuario}. A {self.nome_assistente} está pronta."
        else:
            texto = f"Boa noite, {self.nome_usuario}. Estou pronta para ajudá-lo."

        return texto, "saudacao"

    def saudacao_reconhecimento_facial(self, nome, eh_usuario_principal):
        """
        Saudação de abertura quando o reconhecimento facial (ver
        vision/face_identity.py) identifica quem está na câmera com
        confiança suficiente (MATCH_FORTE) — nunca revela informação
        pessoal, só cumprimenta pelo nome (ver item 11 do pedido de
        reconhecimento facial). Reconhecimento facial NUNCA substitui
        permissão (ver security/permissions.py); isto só personaliza
        a saudação.
        """
        hora = datetime.now().hour
        saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
        if eh_usuario_principal:
            return f"{saudacao}, {nome}. Reconheci você. Estou pronta para ajudar.", "saudacao"
        return f"{saudacao}, {nome}.", "saudacao"

    def saudacao_facial_desconhecida(self):
        """Um rosto foi visto pela câmera mas não bate com ninguém
        cadastrado — saudação neutra, sem presumir quem é nem revelar
        de quem é o computador."""
        return "Olá! Como posso ajudar?", "saudacao"

    def despedida(self):
        return f"Até logo, {self.nome_usuario}.", "seria"

    def presenca(self):
        """Resposta a um chamado de verificação, ex.: "Beta, você está aí?"."""
        return f"Estou sim, {self.nome_usuario}. Sempre de prontidão.", "confirmacao"

    def saudacao_presenca(self):
        """
        Saudação do MODO ATENDIMENTO ao detectar presença pela câmera
        (ver vision/presenca.py e core/alfa_core.py). Não usa o nome
        de nenhum usuário específico: quem está diante da câmera pode
        ser qualquer pessoa, não necessariamente Rinaldo.
        """
        return "Olá! Seja bem-vindo. Posso ajudá-lo?", "saudacao"

    def saudacao_resposta(self, saudacao="oi"):
        """Resposta a uma saudação do usuário durante a conversa (não a
        saudação de abertura do programa, ver saudacao_inicial)."""
        respostas = {
            "oi": (f"Oi, {self.nome_usuario}! Estou aqui.", "saudacao"),
            "bom_dia": (
                f"Bom dia, {self.nome_usuario}! Estou pronta. O que vamos fazer?",
                "saudacao",
            ),
            "boa_tarde": (f"Boa tarde, {self.nome_usuario}! Pronta para ajudar.", "saudacao"),
            "boa_noite": (f"Boa noite, {self.nome_usuario}! Em que posso ajudar?", "saudacao"),
        }
        return respostas.get(saudacao, respostas["oi"])

    def estado_atual(self):
        """Resposta a "como você está?"/"tudo bem?"."""
        return f"Tudo certo por aqui, {self.nome_usuario}. E com você?", "descontraida"

    def agradecimento(self):
        return "Disponha, é sempre um prazer ajudar.", "confirmacao"

    def despedida_leve(self):
        """"Até logo" dito em meio à conversa: não encerra o programa
        (isso é o intent SAIR), só encerra o assunto."""
        return f"Até já, {self.nome_usuario}.", "seria"

    def aguardar(self):
        return "Sem pressa, fico por aqui.", "neutra"

    def continuar(self):
        return "Certo, vamos em frente.", "confirmacao"

    # -----------------------------------------------------------
    # IDENTIDADE INSTITUCIONAL DA BETA — pública, offline, mesma para
    # qualquer pessoa que perguntar (diferente da MEMÓRIA PESSOAL do
    # ALFA: nome de usuário, família, dados de atendimento — essa
    # continua só na configuração, nunca exposta aqui). Só os fatos
    # abaixo, verdadeiros e já fornecidos — nada inventado.
    # -----------------------------------------------------------
    def identidade_quem_e_voce(self):
        return (
            f"Eu sou a {self.nome_assistente}, uma assistente de inteligência "
            f"artificial criada dentro do projeto ALFA, por {NOME_CRIADOR}.",
            "confirmacao",
        )

    def identidade_quem_criou(self):
        return (
            f"Fui criada por {NOME_CRIADOR}, um estudante de Cibersegurança "
            "de 47 anos. Ele começou a me desenvolver ainda no primeiro mês da "
            "faculdade.",
            "confirmacao",
        )

    def identidade_historia(self):
        return (
            f"Eu sou a {self.nome_assistente}, uma assistente de inteligência "
            f"artificial criada dentro do projeto ALFA por {NOME_CRIADOR}, um "
            "estudante de Cibersegurança de 47 anos.\n\n"
            f"{NOME_CRIADOR} começou sua graduação em Cibersegurança e, ainda "
            "no primeiro mês de faculdade, iniciou o desenvolvimento do "
            "projeto.\n\n"
            "A ideia começou como uma assistente pessoal capaz de ouvir, "
            "conversar e ajudar no computador. Com o tempo, o projeto evoluiu "
            "para inteligência artificial, automação, controle do computador, "
            "visão de tela, acessibilidade e funcionamento local.\n\n"
            "Meu objetivo é tornar o computador mais simples, acessível e "
            "útil para as pessoas.",
            "confirmacao",
        )

    def identidade_quem_e_rinaldo(self):
        return (
            f"{NOME_CRIADOR} é um estudante de Cibersegurança de 47 anos — "
            "foi ele quem criou o projeto ALFA, e sou eu, a Beta, quem roda "
            "dentro dele.",
            "confirmacao",
        )

    def identidade_o_que_e_alfa(self):
        return (
            "ALFA é o nome interno do projeto que me criou. Começou como a ideia "
            "de uma assistente pessoal capaz de ouvir, conversar e ajudar no "
            "computador, e foi crescendo até virar o que sou hoje.",
            "confirmacao",
        )

    def identidade_por_que_beta(self):
        return (
            f"{self.nome_assistente} é o nome que uso para falar com você — ALFA "
            "é o projeto por trás, e eu sou a parte que conversa e age no seu "
            "lugar.",
            "confirmacao",
        )

    def identidade_para_que_serve(self):
        return (
            "Sirvo para ouvir, conversar e ajudar você a usar o computador — "
            "abrir programas, preencher formulários, ler e explicar o que está "
            "na tela, entre outras coisas.",
            "confirmacao",
        )

    def identidade_o_que_consegue_fazer(self):
        return (
            "Consigo entender comandos de voz, controlar mouse e teclado, abrir "
            "e fechar programas, mexer em arquivos, ler e descrever o que está "
            "na tela, e ajudar em tarefas do dia a dia no computador — tudo isso "
            "rodando localmente sempre que possível.",
            "confirmacao",
        )

    def identidade_funciona_offline(self):
        return (
            "Minha voz, meus comandos e a maior parte do que faço funcionam "
            "totalmente offline. Só preciso de internet para coisas específicas, "
            "como conversas mais complexas ou informações atuais.",
            "confirmacao",
        )

    def identidade_usa_computador(self):
        return (
            "Sim. Consigo mexer no mouse, no teclado, abrir e fechar programas, "
            "e trabalhar com o que está na tela.",
            "confirmacao",
        )

    def identidade_acessibilidade(self):
        return (
            "Esse é um dos meus objetivos: ajudar quem precisa de mais "
            "acessibilidade para usar o computador, seja por voz, sem enxergar "
            "a tela, ou sem usar as mãos.",
            "confirmacao",
        )

    def identidade_sem_teclado(self):
        return (
            "Sim, boa parte do que faço pode ser feito só por voz, sem precisar "
            "tocar no teclado.",
            "confirmacao",
        )

    def identidade_e_humana(self):
        return (
            "Não, sou um programa de computador — uma inteligência artificial. "
            "Mas faço o possível para conversar de um jeito natural.",
            "confirmacao",
        )

    def identidade_sabe_tudo(self):
        return (
            "Não, longe disso. Sei o que foi me ensinado e o que consigo "
            "verificar — quando não sei algo, prefiro dizer isso a inventar uma "
            "resposta.",
            "confirmacao",
        )

    def hora_atual(self):
        agora = datetime.now()
        return f"Agora são {agora.strftime('%H:%M')}, {self.nome_usuario}.", "confirmacao"

    def data_atual(self):
        dias_semana = [
            "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo",
        ]
        agora = datetime.now()
        dia_semana = dias_semana[agora.weekday()]
        return (
            f"Hoje é {dia_semana}, {agora.strftime('%d/%m/%Y')}, {self.nome_usuario}.",
            "confirmacao",
        )

    def aviso_espera(self, categoria):
        """
        Aviso curto falado ANTES de uma operação classificada como
        demorada/muito demorada (ver core/router.py -> DURACAO_ESTIMADA
        e GERENCIADOR DE PROGRESSO CONVERSACIONAL) — para o usuário
        nunca ficar em silêncio sem saber se a Beta está trabalhando.
        Nunca chamado para tarefas imediatas/rápidas.
        """
        opcoes = (
            AVISOS_ESPERA_MUITO_DEMORADA if categoria == "muito_demorada"
            else AVISOS_ESPERA_DEMORADA
        )
        abertura = self._proxima_abertura(opcoes)
        return f"{abertura}, {self.nome_usuario}.", "neutra"

    def erro_inesperado(self):
        return (
            f"{self._proxima_abertura(ABERTURAS_EMPATICA)}, {self.nome_usuario}, "
            "encontrei um problema, mas continuo ouvindo.",
            "empatica",
        )

    def compor(self, intent, resultado):
        """
        Recebe a intenção reconhecida (dict de core/intent_engine.py)
        e o texto factual já produzido pelo router/executor, devolve
        (texto_final, estilo) prontos para VoiceOutput.falar(...).
        """

        intent = intent or {}
        kind = intent.get("intent", "DESCONHECIDO")
        texto = str(resultado)
        texto_lower = texto.lower()

        if kind == "PRESENCA":
            return self.presenca()

        if kind == "CONVERSA_SAUDACAO":
            return self.saudacao_resposta(intent.get("saudacao", "oi"))

        if kind == "CONVERSA_ESTADO":
            return self.estado_atual()

        if kind == "CONVERSA_AGRADECIMENTO":
            return self.agradecimento()

        if kind == "CONVERSA_DESPEDIDA_LEVE":
            return self.despedida_leve()

        if kind == "CONVERSA_AGUARDAR":
            return self.aguardar()

        if kind == "CONVERSA_CONTINUAR":
            return self.continuar()

        if kind == "CONVERSA_HORAS":
            return self.hora_atual()

        if kind == "CONVERSA_DATA":
            return self.data_atual()

        _RESPOSTAS_IDENTIDADE = {
            "IDENTIDADE_QUEM_E_VOCE": self.identidade_quem_e_voce,
            "IDENTIDADE_QUEM_CRIOU": self.identidade_quem_criou,
            "IDENTIDADE_HISTORIA": self.identidade_historia,
            "IDENTIDADE_QUEM_E_RINALDO": self.identidade_quem_e_rinaldo,
            "IDENTIDADE_O_QUE_E_ALFA": self.identidade_o_que_e_alfa,
            "IDENTIDADE_POR_QUE_BETA": self.identidade_por_que_beta,
            "IDENTIDADE_PARA_QUE_SERVE": self.identidade_para_que_serve,
            "IDENTIDADE_O_QUE_CONSEGUE_FAZER": self.identidade_o_que_consegue_fazer,
            "IDENTIDADE_FUNCIONA_OFFLINE": self.identidade_funciona_offline,
            "IDENTIDADE_USA_COMPUTADOR": self.identidade_usa_computador,
            "IDENTIDADE_ACESSIBILIDADE": self.identidade_acessibilidade,
            "IDENTIDADE_SEM_TECLADO": self.identidade_sem_teclado,
            "IDENTIDADE_E_HUMANA": self.identidade_e_humana,
            "IDENTIDADE_SABE_TUDO": self.identidade_sabe_tudo,
        }
        if kind in _RESPOSTAS_IDENTIDADE:
            return _RESPOSTAS_IDENTIDADE[kind]()

        if kind in ("REFERENCIA_AMBIGUA", "SELECIONAR_REFERENCIA"):
            # O texto já vem PRONTO do router/agente (resolvido de
            # verdade contra os últimos resultados, ou a mensagem
            # honesta de "não consegui identificar") — ver
            # agente/orquestrador.py:selecionar_resultado.
            return texto, "neutra"

        # Durante um atendimento presencial (core/atendimento.py), a
        # BETA pode estar falando com QUEM ESTÁ SENDO ATENDIDO, não
        # necessariamente com o Rinaldo — por isso as falas do
        # atendimento nunca recebem o endereçamento "Rinaldo" nem a
        # abertura de confirmação padrão.
        if kind == "ATENDIMENTO":
            return texto, "confirmacao"

        # Pergunta/resultado de confirmação de uma FERRAMENTA do
        # agente (ver agente/planejador.py -> WAITING_CONFIRMATION e
        # core/alfa_core.py -> _processar_comando). O texto já vem
        # pronto (pergunta natural ou "Ação cancelada."); só ajusta o
        # tom, sem "Claro"/"Certo" de abertura (ainda não foi feito
        # nada, ou acabou de ser cancelado).
        if kind == "TAREFA_CONFIRMACAO":
            return f"{self.nome_usuario}, {texto}", "seria"

        if kind == "CONFIRMACAO_NEGADA":
            return texto, "neutra"

        # Pergunta de confirmação de uma ação sensível (ver
        # core/router.py e security/permissions.py): tom sério, sem
        # abertura de "Claro"/"Certo" porque ainda não foi executado
        # nada — é uma pergunta, não uma confirmação de tarefa feita.
        if intent.get("_pedido_confirmacao"):
            return f"{self.nome_usuario}, {texto}", "seria"

        if eh_falha_retentavel(texto):
            # Falha de rede/IA (conversa livre, visão): vale a pena
            # oferecer tentar de novo, já que costuma ser passageira
            # (ver core/alfa_core.py para a retentativa por voz real).
            abertura = self._proxima_abertura(ABERTURAS_EMPATICA)
            return (
                f"{abertura}, {self.nome_usuario}. {texto} Quer que eu tente de novo?",
                "empatica",
            )

        if any(p in texto_lower for p in PALAVRAS_ERRO):
            abertura = self._proxima_abertura(ABERTURAS_EMPATICA)
            return f"{abertura}, {self.nome_usuario}. {texto}", "empatica"

        # Conversa livre (IA de fallback): a resposta já vem pronta e
        # completa do cérebro conversacional; a personalidade dele é
        # ajustada no próprio prompt do sistema (ver
        # core/alfa_core.py -> criar_brain_fallback), não aqui.
        if kind == "DESCONHECIDO":
            return texto, "descontraida"

        if kind in INTENTS_ACAO_SERIA:
            abertura = self._proxima_abertura(ABERTURAS_SERIA)
            return f"{abertura}, {self.nome_usuario}. {texto}", "seria"

        # Comando local executado com sucesso (mouse, clique, abrir
        # programa, volume, teclado...): tom de confirmação calorosa,
        # sempre profissional na execução em si — o humor fica para a
        # conversa livre, nunca disfarça se algo deu errado.
        abertura = self._proxima_abertura(ABERTURAS_CONFIRMACAO)
        return f"{abertura}, {self.nome_usuario}. {texto}", "confirmacao"
