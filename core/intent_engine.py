"""
Interpretador de comandos (NLU) do ALFA.

Recebe o texto transcrito e devolve uma intenção estruturada:
{"intent": ..., "confidence": ..., **parametros}.

Regra central: a palavra "mouse" NÃO é obrigatória em todas as
frases. Um verbo de movimento combinado com uma direção clara já é
suficiente para reconhecer MOVER_MOUSE (ex.: "mova para a direita").
"""

import re

from core.normalizer import normalize

MOUSE_WORDS = [
    "mouse", "mause", "maus", "malwe", "malve", "mou",
    "cursor", "ponteiro",
]

MOVE_VERBS = [
    "mover", "mova", "move", "movam",
    "mexer", "mexa", "mexe", "mecho", "mexo",
    "leve", "levar", "leva",
    "desloque", "deslocar",
    "suba", "subir", "sobe",
    "desca", "descer", "desce",
    "baixe", "baixar",
    "eleve", "elevar",
    "jogue", "jogar", "joga",
    "coloque", "colocar",
]

DRAG_VERBS = [
    "arraste", "arrastar", "arrasta",
    "puxe", "puxar", "puxa",
]

DIRECTION_WORDS = {
    "esquerda": ["esquerda", "esquerdo", "esquer"],
    "direita": ["direita", "direito", "direit", "direto"],
    "cima": ["cima", "acima", "topo", "suba", "sobe", "eleva", "alto"],
    "baixo": ["baixo", "abaixo", "fundo", "desca", "desce", "baixe"],
    "centro": ["centro", "meio"],
}

PROGRAM_WORDS = [
    "calculadora", "calculator", "chrome", "edge", "navegador",
    "explorador", "explorador de arquivos", "bloco de notas",
    "notepad", "paint", "gerenciador de tarefas",
    "vs code", "visual studio code",
]

SCROLL_VERBS = ["role", "rolar", "rola", "deslize", "deslizar"]

DIGITAR_REGEX = re.compile(
    r"\b(digite|digitar|escreva|escrever)\b[:\s]+(.+)",
    re.IGNORECASE,
)

# Primeiro fluxo real do agente de computador (ver agente/orquestrador.py
# e FASE 1 do plano de implementação): "abra o Word e escreva: X" vira
# uma tarefa composta em vez de cair em DIGITAR (que perderia o "abra o
# Word") ou em DESCONHECIDO. Verificado ANTES de DIGITAR_REGEX por isso
# — ver core/router.py para o despacho.
TAREFA_ABRIR_E_ESCREVER_REGEX = re.compile(
    r"abr[ae]\s+(?:o|a)\s+(?P<programa>[a-zà-ú ]+?)\s+e\s+escrev[ae]\s*:?\s+(?P<texto>.+)",
    re.IGNORECASE,
)

# Tarefas compostas do Excel (ver skills/excel/ e agente/orquestrador.py)
# — exigem a palavra "excel" explícita para não sequestrar um "procure"
# genérico sem relação nenhuma com planilha.
TAREFA_EXCEL_PROCURAR_REGEX = re.compile(
    r"excel.*?procur[ae]\w*\s+(?:o\s+valor\s+|pelo\s+valor\s+)?(?P<valor>.+)"
    r"|procur[ae]\w*\s+(?:o\s+valor\s+|pelo\s+valor\s+)?(?P<valor2>.+?)\s+no\s+excel",
    re.IGNORECASE,
)
# Exige "excel" explícito de propósito: "troque X por Y" sem
# programa nomeado é ambíguo (podia ser Word ou Excel) e fica para o
# planejador via LLM decidir, com o contexto de qual programa foi
# aberto por último (ver agente/orquestrador.py -> ultimo_programa).
TAREFA_EXCEL_SUBSTITUIR_REGEX = re.compile(
    r"no\s+excel[,]?\s+troqu[ea]\w*\s+(?P<de>.+?)\s+por\s+(?P<para>.+)"
    r"|troqu[ea]\w*\s+(?P<de2>.+?)\s+por\s+(?P<para2>.+?)\s+no\s+excel",
    re.IGNORECASE,
)

# "Clique naquele botão"/"clique nisso"/"clique nesse" — contrações de
# "em" + referência (na=em+a, naquele=em+aquele...) que
# CLICAR_ELEMENTO_REGEX (mais abaixo) não casa, porque exige "no/na/em"
# como palavra SEPARADA. Resolve contra o último elemento encontrado
# no contexto (ver agente/contexto.py), nunca inventa posição.
CLICAR_REFERENCIA_REGEX = re.compile(
    r"cliqu[ea]\w*\s+(?:nisso|nesse|nessa|naquele|naquela)\b", re.IGNORECASE,
)

# Rolar ATÉ ACHAR algo (ver agente/leitura_tela.py:rolar_para_elemento)
# — diferente do SCROLL simples (que só rola, sem procurar nada).
ROLAR_ATE_ENCONTRAR_REGEX = re.compile(
    r"rol[ea]\w*\s+at[eé]\s+(?:encontrar|achar)\s+(?P<alvo>.+)",
    re.IGNORECASE,
)

# Preenchimento de campo com preservação de maiúsculas/acentos do
# valor (extraído do texto ORIGINAL, igual ao DIGITAR_REGEX acima).
PREENCHER_REGEX = re.compile(
    r"preenc(?:ha|her)\s+(?:o\s+)?campo\s+(?P<campo>.+?)\s+com\s+(?P<valor>.+)",
    re.IGNORECASE,
)

# Ações orientadas a ELEMENTOS da tela (UI Automation/OCR), em vez de
# coordenadas fixas — ver vision/ui_automation.py e
# computer/form_filler.py.
CLICAR_ELEMENTO_REGEX = re.compile(
    r"cliqu[ea]\w*\s+(?:no|na|em)\s+(?:botao\s+|link\s+|campo\s+)?(?P<nome>.+)"
)
MARCAR_CAIXA_REGEX = re.compile(
    r"(?P<desmarcar>des)?marqu[ea]\w*\s+(?:a\s+caixa|o\s+checkbox|a\s+opcao)\s+(?P<campo>.+)"
)
SELECIONAR_OPCAO_REGEX = re.compile(
    r"(?:selecione|escolha)\s+(?P<opcao>.+?)\s+no\s+campo\s+(?P<campo>.+)"
)
LOCALIZAR_REGEX = re.compile(
    r"(?:onde esta|encontre|localize)\s+(?:o|a)?\s*(?P<alvo>.+)"
)

# Teclas avulsas, além das já tratadas como intents próprias
# (ENTER/ESC/TAB/BACKSPACE) por serem as mais frequentes.
TECLAS_NOMEADAS = {
    "espaco": "space",
    "delete": "delete",
    "supr": "delete",
    "home": "home",
    "fim": "end",
    "pagina para cima": "pageup",
    "pagina para baixo": "pagedown",
    "seta para cima": "up",
    "seta para baixo": "down",
    "seta para esquerda": "left",
    "seta para direita": "right",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}

# Atalhos de teclado nomeados (exigem a palavra "atalho" na frase
# para não colidir com ditado/comandos livres).
ATALHOS_NOMEADOS = {
    "salvar": ("ctrl", "s"),
    "novo": ("ctrl", "n"),
    "imprimir": ("ctrl", "p"),
    "localizar": ("ctrl", "f"),
    "pesquisar": ("ctrl", "f"),
    "atualizar": ("f5",),
    "fechar aba": ("ctrl", "w"),
    "nova aba": ("ctrl", "t"),
    "trocar de aba": ("ctrl", "tab"),
}


def _contains_any(text, words):
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def _direction(text):
    for direction, variants in DIRECTION_WORDS.items():
        if _contains_any(text, variants):
            return direction
    return None


def _program(text):
    for program in PROGRAM_WORDS:
        if program in text:
            return program
    return None


# Referências ordinais a um resultado de uma busca anterior (ver
# agente/contexto.py -> resolver_referencia) — -1 é o código interno
# para "o último", nunca confundido com um índice de verdade.
ORDINAIS_MAPA = {
    "primeiro": 1, "primeira": 1,
    "segundo": 2, "segunda": 2,
    "terceiro": 3, "terceira": 3,
    "quarto": 4, "quarta": 4,
    "quinto": 5, "quinta": 5,
    "ultimo": -1, "ultima": -1,
}


def _extrair_ordinal(text):
    for palavra, valor in ORDINAIS_MAPA.items():
        if re.search(rf"\b{palavra}\b", text):
            return valor
    return None


class IntentEngine:
    """Interpretador determinístico de comandos locais do ALFA."""

    def __init__(self):
        # Guarda o último alvo de comando (ex.: MOUSE) para permitir
        # frases de continuação como "mova mais para a esquerda" logo
        # depois de outro comando de mouse.
        self.last_target = None

    def normalizar(self, texto):
        return normalize(texto)

    def interpretar(self, texto, texto_original=None):
        if texto_original is None:
            texto_original = texto

        c = self.normalizar(texto)

        if not c:
            return {"intent": "DESCONHECIDO", "confidence": 0.0}

        # -----------------------------------------------------------
        # TAREFA COMPOSTA ("abra o Word e escreva: ...") — ver
        # agente/orquestrador.py. Precisa vir ANTES de DIGITAR_REGEX,
        # senão "escreva: ..." seria casado por ele sozinho e a parte
        # "abra o Word" se perderia.
        # -----------------------------------------------------------
        match_tarefa = TAREFA_ABRIR_E_ESCREVER_REGEX.search(texto_original)
        if match_tarefa and match_tarefa.group("texto").strip():
            return {
                "intent": "TAREFA_ABRIR_E_ESCREVER",
                "confidence": 1.0,
                "programa": match_tarefa.group("programa").strip(),
                "texto": match_tarefa.group("texto").strip(),
            }

        match_excel_substituir = TAREFA_EXCEL_SUBSTITUIR_REGEX.search(texto_original)
        if match_excel_substituir:
            de = match_excel_substituir.group("de") or match_excel_substituir.group("de2")
            para = match_excel_substituir.group("para") or match_excel_substituir.group("para2")
            if de and para and de.strip() and para.strip():
                return {
                    "intent": "TAREFA_EXCEL_SUBSTITUIR",
                    "confidence": 1.0,
                    "de": de.strip(),
                    "para": para.strip(),
                }

        match_excel_procurar = TAREFA_EXCEL_PROCURAR_REGEX.search(texto_original)
        if match_excel_procurar:
            valor = match_excel_procurar.group("valor") or match_excel_procurar.group("valor2")
            if valor and valor.strip():
                return {
                    "intent": "TAREFA_EXCEL_PROCURAR",
                    "confidence": 1.0,
                    "valor": valor.strip(),
                }

        # Referência a um resultado de busca anterior, JUNTO com um
        # verbo de ação ("selecione o segundo", "escolha o último") —
        # ver agente/contexto.py. Precisa vir ANTES de
        # SELECIONAR_OPCAO_REGEX (mais abaixo), que é um padrão
        # diferente ("selecione X no campo Y").
        ordinal_com_verbo = _extrair_ordinal(c)
        if ordinal_com_verbo is not None and _contains_any(c, ["selecione", "escolha", "selecionar", "quero o", "quero a"]):
            return {"intent": "SELECIONAR_REFERENCIA", "confidence": 1.0, "ordinal": ordinal_com_verbo}

        # Precisa vir ANTES do SCROLL genérico (mais abaixo): "role até
        # encontrar X" é mais específico e não pode ser engolido pelo
        # scroll simples só porque a frase também contém "tela".
        match_rolar_ate = ROLAR_ATE_ENCONTRAR_REGEX.search(texto_original)
        if match_rolar_ate and match_rolar_ate.group("alvo").strip():
            return {
                "intent": "ROLAR_ATE_ENCONTRAR",
                "confidence": 1.0,
                "alvo": match_rolar_ate.group("alvo").strip(),
            }

        # -----------------------------------------------------------
        # DITADO LIVRE ("digite ...")
        # Precisa vir ANTES de qualquer outra checagem: o conteúdo
        # ditado pode conter palavras como "sair" ou "mouse" sem que
        # isso deva disparar outro comando. Usa o texto ORIGINAL (não
        # normalizado) para preservar maiúsculas/acentuação do que
        # será digitado.
        # -----------------------------------------------------------
        match_digitar = DIGITAR_REGEX.search(texto_original)
        if match_digitar and match_digitar.group(2).strip():
            return {
                "intent": "DIGITAR",
                "confidence": 1.0,
                "texto": match_digitar.group(2).strip(),
            }

        # -----------------------------------------------------------
        # PREENCHER CAMPO ("preencha o campo Nome com João da Silva")
        # Mesmo motivo do DIGITAR: usa o texto ORIGINAL para preservar
        # o valor exatamente como foi dito.
        # -----------------------------------------------------------
        match_preencher = PREENCHER_REGEX.search(texto_original)
        if match_preencher:
            campo = match_preencher.group("campo").strip()
            valor = match_preencher.group("valor").strip()
            if campo and valor:
                return {
                    "intent": "PREENCHER_CAMPO",
                    "confidence": 1.0,
                    "campo": campo,
                    "valor": valor,
                }

        # -----------------------------------------------------------
        # MODO DE ATENDIMENTO (ver core/atendimento.py)
        # -----------------------------------------------------------
        if _contains_any(c, [
            "iniciar atendimento", "inicie o atendimento",
            "comecar atendimento", "comece o atendimento",
            "novo atendimento",
        ]):
            return {"intent": "INICIAR_ATENDIMENTO", "confidence": 1.0}

        if _contains_any(c, [
            "encerrar atendimento", "encerre o atendimento",
            "finalizar atendimento", "finalize o atendimento",
            "cancelar atendimento", "cancele o atendimento",
        ]):
            return {"intent": "ENCERRAR_ATENDIMENTO", "confidence": 1.0}

        # -----------------------------------------------------------
        # SAIR
        # -----------------------------------------------------------
        if _contains_any(c, [
            "sair", "saia",
            "encerre o alfa", "feche o alfa", "pare o alfa",
            "desligue o alfa", "encerrar alfa",
            "encerre a beta", "feche a beta", "pare a beta",
            "desligue a beta", "encerrar beta", "tchau beta",
        ]):
            return {"intent": "SAIR", "confidence": 1.0}

        # -----------------------------------------------------------
        # CANCELAR TAREFA DO AGENTE (ver agente/orquestrador.py)
        # Normalmente já é tratado ANTES de chegar aqui, direto em
        # core/alfa_core.py, quando há uma confirmação pendente — isto
        # cobre o caso de dizer "cancela"/"pare" sem nada pendente.
        # -----------------------------------------------------------
        # "pare"/"para" sozinhos (frase INTEIRA, não substring) também
        # contam — mas só como palavra isolada, para "vou para casa"
        # ou qualquer frase real com "para" no meio nunca virar cancelamento.
        if c.strip() in ("pare", "para") or _contains_any(c, [
            "cancela", "cancele", "cancelar tarefa", "pode parar",
            "esquece", "esqueca", "nao faca mais", "para com isso",
        ]):
            return {"intent": "CANCELAR_TAREFA", "confidence": 1.0}

        # -----------------------------------------------------------
        # MODOS DE OPERAÇÃO (ver core/alfa_core.py -> _modo_beta)
        # -----------------------------------------------------------
        if _contains_any(c, ["modo pessoal", "ativar modo pessoal", "voltar ao modo pessoal"]):
            return {"intent": "ATIVAR_MODO_PESSOAL", "confidence": 1.0}

        if _contains_any(c, ["modo atendimento", "ativar modo atendimento"]):
            return {"intent": "ATIVAR_MODO_ATENDIMENTO", "confidence": 1.0}

        if _contains_any(c, [
            "modo privacidade", "ativar modo privacidade", "modo de privacidade",
        ]):
            return {"intent": "ATIVAR_MODO_PRIVACIDADE", "confidence": 1.0}

        # Totem (ver ui/totem/totem_app.py) roda como PROCESSO/JANELA
        # separada — não é um valor de _modo_beta desta sessão.
        if _contains_any(c, ["ativar modo totem", "modo totem", "abrir o totem", "iniciar o totem"]):
            return {"intent": "ATIVAR_MODO_TOTEM", "confidence": 1.0}

        # -----------------------------------------------------------
        # PRESENÇA ("Beta, você está aí?")
        # -----------------------------------------------------------
        if _contains_any(c, ["voce esta ai", "voce ta ai", "esta ai", "cade voce"]):
            return {"intent": "PRESENCA", "confidence": 1.0}

        # -----------------------------------------------------------
        # CONVERSA (saudações e frases sociais curtas)
        # Precisam ser reconhecidas ANTES de qualquer coisa cair em
        # DESCONHECIDO: são as frases mais comuns do dia a dia e não
        # podem ir para a IA de fallback (lenta, depende de rede) nem
        # virar "não consegui processar" (ver core/router.py e
        # core/personality.py para as respostas).
        # -----------------------------------------------------------
        if _contains_any(c, ["bom dia"]):
            return {"intent": "CONVERSA_SAUDACAO", "confidence": 1.0, "saudacao": "bom_dia"}

        if _contains_any(c, ["boa tarde"]):
            return {"intent": "CONVERSA_SAUDACAO", "confidence": 1.0, "saudacao": "boa_tarde"}

        if _contains_any(c, ["boa noite"]):
            return {"intent": "CONVERSA_SAUDACAO", "confidence": 1.0, "saudacao": "boa_noite"}

        if _contains_any(c, ["oi", "ola"]):
            return {"intent": "CONVERSA_SAUDACAO", "confidence": 1.0, "saudacao": "oi"}

        if _contains_any(c, ["como voce esta", "como voce ta", "tudo bem", "tudo bom"]):
            return {"intent": "CONVERSA_ESTADO", "confidence": 1.0}

        if _contains_any(c, ["obrigado", "obrigada", "valeu"]):
            return {"intent": "CONVERSA_AGRADECIMENTO", "confidence": 1.0}

        if _contains_any(c, ["ate logo", "ate mais", "ate breve"]):
            return {"intent": "CONVERSA_DESPEDIDA_LEVE", "confidence": 1.0}

        if _contains_any(c, ["pode esperar", "espera ai", "espere um pouco"]):
            return {"intent": "CONVERSA_AGUARDAR", "confidence": 1.0}

        if _contains_any(c, ["vamos continuar", "pode continuar"]):
            return {"intent": "CONVERSA_CONTINUAR", "confidence": 1.0}

        # Perguntas básicas de hora/data — respondidas com o relógio
        # local do computador (ver core/personality.py).
        if _contains_any(c, [
            "que horas sao", "que hora e", "que horas e", "qual e a hora",
            "voce sabe as horas", "voce sabe que horas sao",
        ]):
            return {"intent": "CONVERSA_HORAS", "confidence": 1.0}

        if _contains_any(c, [
            "que dia e hoje", "que dia eh hoje", "qual e a data de hoje",
            "qual a data de hoje", "qual e o dia de hoje", "qual dia e hoje",
        ]):
            return {"intent": "CONVERSA_DATA", "confidence": 1.0}

        # Previsão do tempo — depende de internet (ver core/clima.py);
        # se não houver, a resposta é honesta em vez de inventada.
        if _contains_any(c, [
            "previsao do tempo", "que tempo faz", "como esta o tempo",
            "vai chover", "clima hoje", "qual e o clima", "tempo hoje",
        ]):
            return {"intent": "CONSULTAR_CLIMA", "confidence": 1.0}

        # -----------------------------------------------------------
        # IDENTIDADE INSTITUCIONAL DA BETA (ver core/personality.py) —
        # pública e offline, nunca expõe dados pessoais do ALFA
        # (usuário/família ficam só na configuração).
        # -----------------------------------------------------------
        if _contains_any(c, ["quem e voce", "qual seu nome", "qual e o seu nome"]):
            return {"intent": "IDENTIDADE_QUEM_E_VOCE", "confidence": 1.0}

        # História/origem completa do projeto — checado ANTES do
        # "quem criou você" (curto) porque frases como "como você foi
        # criada" e "quem criou você" compartilham palavras, e aqui
        # queremos a resposta longa quando a pergunta é sobre a
        # HISTÓRIA, não só o nome do criador.
        if _contains_any(c, [
            "qual e a sua historia", "qual e sua historia", "conte sua historia",
            "conte a sua historia", "como voce foi criada", "como voce foi criado",
            "como voce comecou", "como surgiu a beta", "de onde voce veio",
            "como nasceu o projeto alfa", "como nasceu o alfa",
            "qual e a origem do alfa", "qual a origem do alfa",
        ]):
            return {"intent": "IDENTIDADE_HISTORIA", "confidence": 1.0}

        if _contains_any(c, [
            "quem criou voce", "quem te criou", "quem fez voce", "quem e seu criador",
            "quem desenvolveu voce", "quem te desenvolveu", "quem foi seu criador",
            "quem esta por tras do projeto", "quem esta por tras da beta",
            "quem esta por tras do alfa",
        ]):
            return {"intent": "IDENTIDADE_QUEM_CRIOU", "confidence": 1.0}

        if _contains_any(c, ["quem e rinaldo", "quem e o rinaldo"]):
            return {"intent": "IDENTIDADE_QUEM_E_RINALDO", "confidence": 1.0}

        if _contains_any(c, ["o que e o alfa", "o que e alfa", "o que significa alfa"]):
            return {"intent": "IDENTIDADE_O_QUE_E_ALFA", "confidence": 1.0}

        if _contains_any(c, [
            "por que voce se chama beta", "por que seu nome e beta",
            "porque voce se chama beta",
        ]):
            return {"intent": "IDENTIDADE_POR_QUE_BETA", "confidence": 1.0}

        if _contains_any(c, ["para que voce serve", "pra que voce serve"]):
            return {"intent": "IDENTIDADE_PARA_QUE_SERVE", "confidence": 1.0}

        if _contains_any(c, [
            "o que voce consegue fazer", "o que voce sabe fazer", "quais suas funcoes",
        ]):
            return {"intent": "IDENTIDADE_O_QUE_CONSEGUE_FAZER", "confidence": 1.0}

        if _contains_any(c, ["voce funciona sem internet", "voce funciona offline"]):
            return {"intent": "IDENTIDADE_FUNCIONA_OFFLINE", "confidence": 1.0}

        if _contains_any(c, [
            "voce consegue usar o computador", "voce controla o computador",
            "voce consegue mexer no computador",
        ]):
            return {"intent": "IDENTIDADE_USA_COMPUTADOR", "confidence": 1.0}

        if _contains_any(c, [
            "voce consegue ajudar uma pessoa que nao enxerga",
            "voce ajuda quem tem deficiencia visual", "voce ajuda quem nao enxerga",
        ]):
            return {"intent": "IDENTIDADE_ACESSIBILIDADE", "confidence": 1.0}

        if _contains_any(c, [
            "voce consegue funcionar sem teclado", "da pra usar voce sem teclado",
            "funciona sem teclado",
        ]):
            return {"intent": "IDENTIDADE_SEM_TECLADO", "confidence": 1.0}

        if _contains_any(c, ["voce e humana", "voce e uma pessoa de verdade", "voce e real"]):
            return {"intent": "IDENTIDADE_E_HUMANA", "confidence": 1.0}

        if _contains_any(c, ["voce sabe tudo", "voce sabe de tudo"]):
            return {"intent": "IDENTIDADE_SABE_TUDO", "confidence": 1.0}

        # -----------------------------------------------------------
        # RECONHECIMENTO FACIAL (ver vision/face_identity.py) — cadastro
        # explícito, nunca automático (item 9 do pedido).
        # -----------------------------------------------------------
        if _contains_any(c, [
            "cadastrar meu rosto", "cadastrar minha identificacao facial",
            "cadastre meu rosto", "quero cadastrar meu rosto",
            "cadastrar reconhecimento facial", "cadastrar minha face",
        ]):
            return {"intent": "CADASTRAR_ROSTO", "confidence": 1.0}

        # -----------------------------------------------------------
        # SKILLS (ver agente/skill_registry.py) — descoberta local,
        # nunca executa nada, só lista o que já está instalado.
        # -----------------------------------------------------------
        if _contains_any(c, [
            "quais habilidades voce tem", "quais habilidades estao disponiveis",
            "que habilidades voce tem", "liste suas habilidades",
            "quais skills voce tem", "quais suas habilidades",
        ]):
            return {"intent": "LISTAR_HABILIDADES", "confidence": 1.0}

        if _contains_any(c, [
            "remover meu rosto", "remover minha identificacao facial",
            "apagar meu rosto", "apagar minha identificacao facial",
            "remover meu cadastro facial", "apagar meu cadastro facial",
        ]):
            return {"intent": "REMOVER_ROSTO", "confidence": 1.0}

        # -----------------------------------------------------------
        # REPETIR a última resposta falada (ver core/alfa_core.py)
        # -----------------------------------------------------------
        if _contains_any(c, ["repita", "repete", "pode repetir", "fala de novo", "diz de novo"]):
            return {"intent": "REPETIR", "confidence": 1.0}

        # -----------------------------------------------------------
        # ENERGIA DO COMPUTADOR (ações sensíveis, ver security/permissions.py)
        # -----------------------------------------------------------
        if _contains_any(c, [
            "cancelar desligamento", "cancele o desligamento",
            "cancelar reinicio", "nao desligue", "aborte o desligamento",
        ]):
            return {"intent": "CANCELAR_DESLIGAMENTO", "confidence": 1.0}

        if "computador" in c or "maquina" in c or re.search(r"\bpc\b", c):
            if _contains_any(c, ["desligar", "desligue", "deslige"]):
                return {"intent": "DESLIGAR_COMPUTADOR", "confidence": 1.0}
            if _contains_any(c, ["reiniciar", "reinicie", "reinicia"]):
                return {"intent": "REINICIAR_COMPUTADOR", "confidence": 1.0}

        tem_mouse = _contains_any(c, MOUSE_WORDS)
        tem_verbo_mover = _contains_any(c, MOVE_VERBS)
        tem_verbo_arrastar = _contains_any(c, DRAG_VERBS)
        direcao = _direction(c)

        # -----------------------------------------------------------
        # ARRASTAR (drag real, mantendo o botão pressionado)
        # -----------------------------------------------------------
        if tem_verbo_arrastar and (tem_mouse or direcao):
            self.last_target = "MOUSE"
            return {
                "intent": "ARRASTAR_MOUSE",
                "confidence": 1.0,
                "direcao": direcao,
            }

        # -----------------------------------------------------------
        # MOVER_MOUSE
        # A palavra "mouse"/"cursor"/"ponteiro" NÃO é obrigatória:
        # verbo de movimento + direção clara já basta.
        # -----------------------------------------------------------
        if tem_mouse and tem_verbo_mover:
            self.last_target = "MOUSE"
            return {
                "intent": "MOVER_MOUSE",
                "confidence": 1.0,
                "direcao": direcao,
            }

        if tem_verbo_mover and direcao and direcao != "centro":
            self.last_target = "MOUSE"
            return {
                "intent": "MOVER_MOUSE",
                "confidence": 1.0,
                "direcao": direcao,
            }

        if tem_mouse and direcao and not tem_verbo_mover:
            self.last_target = "MOUSE"
            return {
                "intent": "MOVER_MOUSE",
                "confidence": 1.0,
                "direcao": direcao,
            }

        # Continuação de contexto: "mova mais para a esquerda" logo
        # após um comando de mouse, mesmo sem repetir "mouse".
        if self.last_target == "MOUSE" and direcao and _contains_any(c, [
            "mais", "um pouco", "de novo", "novamente",
        ]):
            return {
                "intent": "MOVER_MOUSE",
                "confidence": 1.0,
                "direcao": direcao,
                "contexto": True,
            }

        # "mova o mouse" / "mexa o mouse" sem direção reconhecida:
        # ainda é MOVER_MOUSE (a camada de execução pede a direção).
        if tem_mouse and tem_verbo_mover:
            return {"intent": "MOVER_MOUSE", "confidence": 1.0, "direcao": None}

        # -----------------------------------------------------------
        # SCROLL
        # -----------------------------------------------------------
        if _contains_any(c, SCROLL_VERBS) and ("pagina" in c or "tela" in c or direcao):
            direcao_scroll = direcao or "baixo"
            return {
                "intent": "SCROLL",
                "confidence": 1.0,
                "direcao": direcao_scroll,
            }

        # -----------------------------------------------------------
        # POSIÇÃO DO MOUSE
        # -----------------------------------------------------------
        if (
            "posicao do mouse" in c
            or "posicao do cursor" in c
            or "onde esta o mouse" in c
            or "onde fica o mouse" in c
            or "onde esta o cursor" in c
            or "onde fica o cursor" in c
        ):
            return {"intent": "POSICAO_MOUSE", "confidence": 1.0}

        # -----------------------------------------------------------
        # AÇÕES ORIENTADAS A ELEMENTOS DA TELA
        # ("clique no botão salvar", "marque a caixa concordo",
        # "selecione masculino no campo gênero") — vêm ANTES do
        # CLIQUE genérico porque, quando há um nome de elemento, a
        # intenção é clicar NAQUELE elemento (via UI Automation/OCR),
        # não simplesmente clicar na posição atual do mouse.
        # -----------------------------------------------------------
        match_selecionar = SELECIONAR_OPCAO_REGEX.search(c)
        if match_selecionar:
            return {
                "intent": "SELECIONAR_OPCAO",
                "confidence": 1.0,
                "campo": match_selecionar.group("campo").strip(),
                "opcao": match_selecionar.group("opcao").strip(),
            }

        match_marcar = MARCAR_CAIXA_REGEX.search(c)
        if match_marcar:
            return {
                "intent": "MARCAR_CAIXA",
                "confidence": 1.0,
                "campo": match_marcar.group("campo").strip(),
                "marcar": not bool(match_marcar.group("desmarcar")),
            }

        if CLICAR_REFERENCIA_REGEX.search(c):
            return {"intent": "CLICAR_REFERENCIA", "confidence": 1.0}

        match_clicar_elemento = CLICAR_ELEMENTO_REGEX.search(c)
        if match_clicar_elemento:
            return {
                "intent": "CLICAR_ELEMENTO",
                "confidence": 1.0,
                "nome": match_clicar_elemento.group("nome").strip(),
            }

        # -----------------------------------------------------------
        # CLIQUE
        # -----------------------------------------------------------
        if _contains_any(c, ["clique", "clicar", "clica", "clic"]) or "cliques" in c:
            if "direito" in c:
                botao = "direito"
            elif (
                "duplo" in c
                or "dupla" in c
                or "duas vezes" in c
                or "dois cliques" in c
            ):
                botao = "duplo"
            else:
                botao = "esquerdo"

            return {"intent": "CLIQUE", "confidence": 1.0, "botao": botao}

        # -----------------------------------------------------------
        # TECLADO (atalhos)
        # -----------------------------------------------------------
        if "copiar" in c or "copie" in c:
            return {"intent": "COPIAR", "confidence": 1.0}

        if "colar" in c or "cole" in c:
            return {"intent": "COLAR", "confidence": 1.0}

        if "recortar" in c or "recorte" in c:
            return {"intent": "RECORTAR", "confidence": 1.0}

        if "desfazer" in c or "desfaca" in c:
            return {"intent": "DESFAZER", "confidence": 1.0}

        if "refazer" in c or "refaca" in c:
            return {"intent": "REFAZER", "confidence": 1.0}

        if "selecionar tudo" in c or "selecione tudo" in c or "marcar tudo" in c:
            return {"intent": "SELECIONAR_TUDO", "confidence": 1.0}

        if "pressione enter" in c or "aperte enter" in c or "tecle enter" in c:
            return {"intent": "ENTER", "confidence": 1.0}

        if "pressione esc" in c or "aperte esc" in c or c.strip() == "escape":
            return {"intent": "ESC", "confidence": 1.0}

        if "pressione tab" in c or "aperte tab" in c or "tecle tab" in c:
            return {"intent": "TAB", "confidence": 1.0}

        if "apagar" in c or "backspace" in c or "apague isso" in c:
            return {"intent": "BACKSPACE", "confidence": 1.0}

        # Atalhos nomeados (exigem a palavra "atalho" para não colidir
        # com ditado/comandos livres, ex.: "atalho salvar").
        if "atalho" in c:
            for nome_atalho, teclas in ATALHOS_NOMEADOS.items():
                if nome_atalho in c:
                    return {
                        "intent": "ATALHO",
                        "confidence": 1.0,
                        "nome": nome_atalho,
                        "teclas": teclas,
                    }

        # Tecla avulsa genérica ("pressione delete", "aperte espaço").
        if _contains_any(c, ["pressione", "aperte", "tecle"]):
            for nome_tecla, tecla_pyautogui in TECLAS_NOMEADAS.items():
                if nome_tecla in c:
                    return {
                        "intent": "PRESSIONAR_TECLA",
                        "confidence": 1.0,
                        "tecla": tecla_pyautogui,
                    }

        # -----------------------------------------------------------
        # JANELAS
        # -----------------------------------------------------------
        if "janela" in c and _contains_any(c, ["feche", "fechar", "fecha", "encerre"]):
            return {"intent": "FECHAR_JANELA", "confidence": 1.0}

        if _contains_any(c, ["minimize", "minimizar", "minimiza"]):
            return {"intent": "MINIMIZAR_JANELA", "confidence": 1.0}

        if _contains_any(c, ["maximize", "maximizar", "maximiza"]):
            return {"intent": "MAXIMIZAR_JANELA", "confidence": 1.0}

        if _contains_any(c, ["alternar janela", "troque de janela", "trocar de janela", "mude de janela"]):
            return {"intent": "ALTERNAR_JANELA", "confidence": 1.0}

        if _contains_any(c, ["area de trabalho", "mostrar area de trabalho", "minimizar tudo"]):
            return {"intent": "MOSTRAR_AREA_TRABALHO", "confidence": 1.0}

        # -----------------------------------------------------------
        # VOLUME
        # -----------------------------------------------------------
        if "volume" in c:
            if _contains_any(c, ["aumentar", "aumente", "suba", "sobe", "mais alto"]):
                return {"intent": "VOLUME_AUMENTAR", "confidence": 1.0}
            if _contains_any(c, ["diminuir", "diminua", "abaixe", "baixe", "mais baixo"]):
                return {"intent": "VOLUME_DIMINUIR", "confidence": 1.0}

        if _contains_any(c, ["mudo", "silenciar", "silencie", "tira o som", "tire o som"]):
            return {"intent": "VOLUME_MUDO", "confidence": 1.0}

        # -----------------------------------------------------------
        # LEITURA SEMÂNTICA DA TELA (ver agente/leitura_tela.py) —
        # caminho rápido/local (UI Automation + OCR, SEM IA), para
        # navegação por voz sem mouse/teclado. Palavras diferentes de
        # VISUALIZAR (abaixo, que usa IA multimodal) de propósito, para
        # não mudar esse comportamento já existente.
        # -----------------------------------------------------------
        if _contains_any(c, [
            "leia a tela", "leia isso", "descreva a tela", "descreva minha tela",
            "o que voce ve agora", "o que voce ve na tela",
            "ler minha tela", "ler a tela",
            "visualize minha tela", "visualizar minha tela", "visualiza minha tela",
            "visualiza a minha tela", "visualize a minha tela",
            "veja minha tela", "veja a minha tela", "veja a tela",
            "veja o que tem na minha tela", "veja o que tem na tela",
            "olhe a tela", "olhe minha tela", "olhe a minha tela",
            "o que tem na minha tela", "o que tem na tela",
            "o que aparece na tela", "o que aparece na minha tela",
            "o que esta aparecendo", "me diga o que esta na tela",
        ]):
            return {"intent": "LER_TELA_AGENTE", "confidence": 1.0}

        # -----------------------------------------------------------
        # VISÃO (tela / câmera) — requer IA, tratado pelo router.
        # -----------------------------------------------------------
        if _contains_any(c, [
            "olhe minha tela", "veja minha tela", "analise minha tela",
            "olhe a tela", "veja a tela",
        ]) or "o que tem na tela" in c or "o que esta na tela" in c:
            return {"intent": "VISUALIZAR", "confidence": 1.0}

        if _contains_any(c, [
            "veja pela camera", "olhe pela camera", "veja o ambiente",
            "olhe o ambiente",
        ]):
            return {"intent": "CAMERA", "confidence": 1.0}

        # Localização diagnóstica de um elemento ("onde está o botão
        # salvar", "encontre o campo nome") — usa a mesma via de
        # UI Automation/OCR de computer/form_filler.py, sem clicar.
        match_localizar = LOCALIZAR_REGEX.search(c)
        if match_localizar and match_localizar.group("alvo").strip():
            return {
                "intent": "LOCALIZAR",
                "confidence": 1.0,
                "alvo": match_localizar.group("alvo").strip(),
            }

        # -----------------------------------------------------------
        # ABRIR ARQUIVO / PASTA / PROGRAMA
        # -----------------------------------------------------------
        # Não depende de a frase COMEÇAR com o verbo: "pode abrir o
        # navegador?", "quero abrir o navegador" e "abra o navegador"
        # devem resultar na mesma intenção.
        match_abrir = re.search(r"\b(?:abra|abrir|abre)\b\s+(.+)", c)
        if match_abrir:
            resto = match_abrir.group(1).strip()

            if resto.startswith("a pasta ") or resto.startswith("pasta "):
                nome = resto.split("pasta ", 1)[1].strip()
                return {"intent": "ABRIR_PASTA", "confidence": 1.0, "nome": nome}

            if resto.startswith("o arquivo ") or resto.startswith("arquivo "):
                nome = resto.split("arquivo ", 1)[1].strip()
                return {"intent": "ABRIR_ARQUIVO", "confidence": 1.0, "nome": nome}

            return {
                "intent": "ABRIR",
                "confidence": 1.0,
                "programa": _program(c),
                # Texto bruto pedido (sem o verbo) para quando o nome NÃO
                # está na whitelist fixa PROGRAM_WORDS — ver
                # core/router.py, que usa isso como entrada para a
                # descoberta real de aplicativos do agente (PATH/registro/
                # Menu Iniciar) em vez de desistir na hora.
                "programa_bruto": resto,
            }

        match_fechar = re.search(r"\b(?:feche|fechar|fecha)\b\s+(.+)", c)
        if match_fechar or "encerre a " in c or "encerre o " in c:
            return {
                "intent": "FECHAR",
                "confidence": 1.0,
                "programa": _program(c),
            }

        # -----------------------------------------------------------
        # REFERÊNCIA CONVERSACIONAL SOLTA ("isso", "o segundo",
        # "aquele"...) sem comando junto — checado por ÚLTIMO de
        # propósito, só pega o que mais nada acima já resolveu como
        # comando de verdade. Sem um contexto genérico de "último
        # resultado" ainda implementado, a honestidade vem antes de
        # adivinhar (ver core/personality.py).
        # -----------------------------------------------------------
        if len(c.split()) <= 5 and _contains_any(c, [
            "isso", "esse", "essa", "aquilo", "aquele", "aquela",
            "ele", "ela", "o primeiro", "a primeira", "o segundo",
            "a segunda", "o terceiro", "a terceira", "o quarto", "a quarta",
            "o quinto", "a quinta", "o ultimo", "a ultima", "volte",
            "esse resultado", "aquele resultado", "essa opcao", "aquela opcao",
        ]):
            return {
                "intent": "REFERENCIA_AMBIGUA",
                "confidence": 0.0,
                "ordinal": _extrair_ordinal(c),
            }

        return {"intent": "DESCONHECIDO", "confidence": 0.0}
