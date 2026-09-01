"""
Whitelist de segurança do ALFA.

Nenhum texto transcrito é executado como comando de shell arbitrário.
Toda execução passa primeiro pelo interpretador de intenções
(core/intent_engine.py); somente intenções conhecidas chegam ao
executor (computer/executor.py), e o executor só age sobre os
programas explicitamente listados aqui.
"""

INTENCOES_LOCAIS = {
    "MOVER_MOUSE",
    "ARRASTAR_MOUSE",
    "CLIQUE",
    "POSICAO_MOUSE",
    "COPIAR",
    "COLAR",
    "RECORTAR",
    "DESFAZER",
    "REFAZER",
    "SELECIONAR_TUDO",
    "ENTER",
    "ESC",
    "TAB",
    "BACKSPACE",
    "DIGITAR",
    "ABRIR",
    "FECHAR",
    "SCROLL",
    "MINIMIZAR_JANELA",
    "MAXIMIZAR_JANELA",
    "FECHAR_JANELA",
    "ALTERNAR_JANELA",
    "MOSTRAR_AREA_TRABALHO",
    "VOLUME_AUMENTAR",
    "VOLUME_DIMINUIR",
    "VOLUME_MUDO",
    "DESLIGAR_COMPUTADOR",
    "REINICIAR_COMPUTADOR",
    "CANCELAR_DESLIGAMENTO",
    "PRESENCA",
    "CONVERSA_SAUDACAO",
    "CONVERSA_ESTADO",
    "CONVERSA_AGRADECIMENTO",
    "CONVERSA_DESPEDIDA_LEVE",
    "CONVERSA_AGUARDAR",
    "CONVERSA_CONTINUAR",
    "CONVERSA_HORAS",
    "CONVERSA_DATA",
    "ABRIR_ARQUIVO",
    "ABRIR_PASTA",
    "PRESSIONAR_TECLA",
    "ATALHO",
    "PREENCHER_CAMPO",
    "CLICAR_ELEMENTO",
    "MARCAR_CAIXA",
    "SELECIONAR_OPCAO",
    "LOCALIZAR",
    "INICIAR_ATENDIMENTO",
    "ENCERRAR_ATENDIMENTO",
    "SAIR",
    "TAREFA_ABRIR_E_ESCREVER",
    "TAREFA_EXCEL_PROCURAR",
    "TAREFA_EXCEL_SUBSTITUIR",
    "LER_TELA_AGENTE",
    "ROLAR_ATE_ENCONTRAR",
    "REPETIR",
    "REFERENCIA_AMBIGUA",
    "SELECIONAR_REFERENCIA",
    "CLICAR_REFERENCIA",
    "IDENTIDADE_QUEM_E_VOCE",
    "IDENTIDADE_QUEM_CRIOU",
    "IDENTIDADE_QUEM_E_RINALDO",
    "IDENTIDADE_O_QUE_E_ALFA",
    "IDENTIDADE_POR_QUE_BETA",
    "IDENTIDADE_PARA_QUE_SERVE",
    "IDENTIDADE_O_QUE_CONSEGUE_FAZER",
    "IDENTIDADE_FUNCIONA_OFFLINE",
    "IDENTIDADE_USA_COMPUTADOR",
    "IDENTIDADE_ACESSIBILIDADE",
    "IDENTIDADE_SEM_TECLADO",
    "IDENTIDADE_E_HUMANA",
    "IDENTIDADE_SABE_TUDO",
    "CANCELAR_TAREFA",
    "CONSULTAR_CLIMA",
    "ATIVAR_MODO_PESSOAL",
    "ATIVAR_MODO_ATENDIMENTO",
    "ATIVAR_MODO_PRIVACIDADE",
}

# Intenções que só podem executar depois de uma confirmação falada
# explícita do usuário ("sim"/"confirmar"), por serem difíceis de
# desfazer ou por poderem causar perda de trabalho não salvo.
INTENCOES_SENSIVEIS = {
    "FECHAR",
    "FECHAR_JANELA",
    "DESLIGAR_COMPUTADOR",
    "REINICIAR_COMPUTADOR",
}

CONFIRMACAO_POSITIVA = [
    "sim", "confirmo", "confirma", "confirmar", "pode",
    "isso mesmo", "afirmativo", "manda ver", "ok",
]

CONFIRMACAO_NEGATIVA = [
    "nao", "cancela", "cancelar", "negativo", "esquece", "deixa pra la",
]

# programa falado -> executável autorizado a ser aberto.
PROGRAMAS_ABRIR = {
    "calculadora": "calc.exe",
    "calculator": "calc.exe",
    "bloco de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "explorador": "explorer.exe",
    "explorador de arquivos": "explorer.exe",
    "navegador": "msedge.exe",
    "edge": "msedge.exe",
    "chrome": "chrome.exe",
    "gerenciador de tarefas": "taskmgr.exe",
    "vs code": "code",
    "visual studio code": "code",
}

# programa falado -> nome(s) de processo autorizado(s) a serem encerrados.
PROGRAMAS_FECHAR = {
    "calculadora": ["CalculatorApp.exe"],
    "calculator": ["CalculatorApp.exe"],
    "bloco de notas": ["notepad.exe"],
    "notepad": ["notepad.exe"],
    "paint": ["mspaint.exe"],
    "explorador": ["explorer.exe"],
    "navegador": ["msedge.exe"],
    "edge": ["msedge.exe"],
    "chrome": ["chrome.exe"],
    "gerenciador de tarefas": ["Taskmgr.exe"],
    "vs code": ["Code.exe"],
    "visual studio code": ["Code.exe"],
}


def intencao_permitida(intent):
    return intent in INTENCOES_LOCAIS


# -----------------------------------------------------------------
# Permissões por CATEGORIA (ver agente/ferramentas.py) — migração
# gradual do modelo acima (por intent individual) para um modelo por
# categoria, pedida na FASE 1 da evolução para agente de computador.
# NÃO substitui INTENCOES_LOCAIS/INTENCOES_SENSIVEIS: o roteador de
# comandos por voz (core/router.py) continua usando o mecanismo de
# sempre. Isto é usado só pelo Tool Registry novo (agente/), para
# ferramentas genéricas que ainda não têm (e podem nunca precisar de)
# um intent de voz dedicado.
# -----------------------------------------------------------------
CATEGORIA_BASIC = "BASIC"
CATEGORIA_FILES = "FILES"
CATEGORIA_SYSTEM = "SYSTEM"
CATEGORIA_SENSITIVE = "SENSITIVE"

# Categorias da expansão de plataforma (skills/integrações/dispositivos
# — ver agente/skill_registry.py e integrations/base.py). Toda
# ferramenta nova, venha de uma skill ou de um adaptador de integração,
# se declara em uma destas categorias — nunca executa fora do Tool
# Registry existente (agente/ferramentas.py) nem contorna esta checagem.
CATEGORIA_COMMERCIAL = "COMMERCIAL"  # consultar sistema comercial (estoque/preço) — leitura, não pede confirmação por si só.
CATEGORIA_PAYMENT = "PAYMENT"        # iniciar/confirmar pagamento — SEMPRE exige confirmação (nunca por ordem conversacional simples).
CATEGORIA_ADMIN = "ADMIN"            # ações administrativas (gerenciar habilidades, perfis, dispositivos) — sempre exige confirmação.

# BASIC nunca pede confirmação (abrir app, ler tela, digitar, navegar).
# FILES também não, EXCETO quando a própria ferramenta for destrutiva
# (apagar/sobrescrever) — isso é decidido ferramenta a ferramenta,
# ver agente/registro_padrao.py; nenhuma ferramenta destrutiva de
# arquivo é registrada nesta fase (só localizar/criar pasta/renomear).
# COMMERCIAL segue a mesma lógica de FILES (consulta não pede, uma
# eventual ferramenta que ALTERE dados comerciais decidiria por si).
CATEGORIAS_QUE_EXIGEM_CONFIRMACAO = {
    CATEGORIA_SYSTEM, CATEGORIA_SENSITIVE, CATEGORIA_PAYMENT, CATEGORIA_ADMIN,
}
