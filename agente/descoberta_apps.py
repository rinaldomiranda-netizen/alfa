"""
Descoberta de aplicativos instalados — sem whitelist fixa e sem
caminho absoluto de nenhuma máquina específica (ver relatório de
auditoria, item J: portabilidade).

Estratégia (nesta ordem, parando na primeira que encontrar):
  1. PATH do sistema (funciona para qualquer programa que se registrou
     no PATH, ex.: muitos instaladores de VS Code).
  2. "App Paths" do registro do Windows — o mecanismo padrão que o
     PRÓPRIO Windows usa para resolver "winword.exe" -> caminho real,
     preenchido pelo instalador de cada programa. É a forma correta e
     portátil de achar Word/Excel/Chrome sem hardcodar `C:\\Program
     Files\\...` de ninguém.

Isto é ADITIVO: computer/executor.py e security/permissions.py
(PROGRAMAS_ABRIR, whitelist fixa) continuam exatamente como estavam e
seguem sendo o caminho usado pelos comandos de voz já existentes
("abra a calculadora" etc.). Esta descoberta nova serve só ao agente
(agente/registro_padrao.py), para pedidos compostos que citam um
programa que não está na whitelist.
"""

import os
import shutil
import subprocess
from difflib import SequenceMatcher

# Nomes populares -> nome(s) real(is) de executável a procurar. Só uma
# tradução de vocabulário falado para nome de arquivo — não é caminho
# nenhum, e a lista pode crescer sem afetar nada mais no projeto.
NOMES_EXECUTAVEL = {
    "word": ["winword.exe"],
    "microsoft word": ["winword.exe"],
    "excel": ["excel.exe"],
    "microsoft excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "navegador": ["msedge.exe", "chrome.exe"],
    "bloco de notas": ["notepad.exe"],
    "notepad": ["notepad.exe"],
    "calculadora": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorador": ["explorer.exe"],
    "gerenciador de tarefas": ["taskmgr.exe"],
    "vs code": ["code.exe"],
    "visual studio code": ["code.exe"],
}


# Variações conhecidas de como o Whisper (principalmente com o
# modelo "small") já transcreveu esses nomes incorretamente nesta
# sessão — usadas SÓ pelo resolvedor contextual abaixo (ver
# resolve_aplicativo_falado), nunca pela descoberta exata acima. Não é
# um corretor geral de português: só entra em jogo quando a intenção
# já é ABRIR e o nome não bateu de primeira.
ALIASES_CONHECIDOS = {
    "word": ["word", "uord", "uorde", "urde", "orde", "ordem"],
    "excel": ["excel", "excell", "eksel", "ecsell", "ekscel"],
    "powerpoint": ["powerpoint", "power point", "pauerpoint", "power pont", "power ponte"],
    "bloco de notas": [
        "bloco de notas", "bloco das notas", "brogo de notas", "broco de notas",
        "bloco de nota", "block de notas", "note pad",
    ],
    "notepad": ["notepad", "note pad", "notepade", "notepd"],
    "calculadora": ["calculadora", "calculador", "calculadola"],
}

CONFIANCA_ALTA = "alta"
CONFIANCA_MEDIA = "media"
CONFIANCA_BAIXA = "baixa"

_LIMIAR_ALTA = 0.72
_LIMIAR_MEDIA = 0.55


def _via_app_paths(executavel):
    """Consulta o registro "App Paths" do Windows — o mesmo lugar que
    o Explorer usa para resolver um nome de executável em caminho
    real, sem precisar saber onde cada programa foi instalado."""
    try:
        import winreg
    except ImportError:
        return None

    caminho_chave = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executavel}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, caminho_chave) as chave:
                valor, _ = winreg.QueryValueEx(chave, None)
                if valor and os.path.exists(valor):
                    return valor
        except OSError:
            continue
    return None


def _via_menu_iniciar(nome_programa):
    """
    Procura um atalho (.lnk) no Menu Iniciar cujo nome contenha
    `nome_programa` — cobre programas que não se registram no PATH
    nem no "App Paths" do registro, mas aparecem no menu (a maioria
    dos instaladores cria pelo menos isso). Só usa pastas do sistema
    via variável de ambiente (%ProgramData%/%APPDATA%) — nunca um
    caminho de usuário fixo.
    """
    import glob

    pastas = [
        os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
    ]

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        return None

    for pasta in pastas:
        if not pasta or not os.path.isdir(pasta):
            continue
        try:
            atalhos = glob.glob(os.path.join(pasta, "**", "*.lnk"), recursive=True)
        except OSError:
            continue
        for caminho_lnk in atalhos:
            nome_atalho = os.path.splitext(os.path.basename(caminho_lnk))[0].lower()
            if nome_programa not in nome_atalho:
                continue
            try:
                alvo = shell.CreateShortCut(caminho_lnk).TargetPath
            except Exception:
                continue
            if alvo and os.path.exists(alvo):
                return alvo

    return None


def localizar_executavel(nome_programa):
    """
    Retorna o caminho real do executável, ou None se este computador
    não tiver o programa instalado (nunca inventa um caminho).

    Ordem de busca: PATH -> "App Paths" do registro -> atalhos do Menu
    Iniciar — cobre a grande maioria dos programas instalados sem
    depender de uma lista fixa de caminhos.
    """
    nome_norm = (nome_programa or "").strip().lower()
    if not nome_norm:
        return None

    candidatos = NOMES_EXECUTAVEL.get(
        nome_norm,
        [nome_norm if nome_norm.endswith(".exe") else f"{nome_norm}.exe"],
    )

    for executavel in candidatos:
        caminho = shutil.which(executavel)
        if caminho:
            return caminho
        caminho = _via_app_paths(executavel)
        if caminho:
            return caminho

    return _via_menu_iniciar(nome_norm)


def resolve_aplicativo_falado(texto, aplicativos_disponiveis):
    """
    Resolve um nome de aplicativo falado mesmo com pequeno erro de
    transcrição do Whisper (ex.: "urde" -> "word"), comparando SÓ
    contra `aplicativos_disponiveis` — um dict {nome_canonico:
    caminho_real} de programas JÁ CONFIRMADOS instalados nesta
    máquina (ver localizar_executavel). Nunca inventa um programa que
    não exista: sem correspondência de verdade, devolve confiança
    BAIXA. Local e rápido — só comparação de texto, sem IA/rede.

    Retorna (nome_canonico | None, confianca, candidatos_empatados).
    """
    alvo = (texto or "").strip().lower()
    if not alvo or not aplicativos_disponiveis:
        return None, CONFIANCA_BAIXA, []

    pontuacoes = []
    for nome_canonico in aplicativos_disponiveis:
        variantes = set(ALIASES_CONHECIDOS.get(nome_canonico, [])) | {nome_canonico}
        melhor = max(SequenceMatcher(None, alvo, variante).ratio() for variante in variantes)
        # "contém" é um sinal mais forte que similaridade de string pura
        # (ex.: "abra o word agora" contém "word" inteiro).
        if any(variante in alvo or alvo in variante for variante in variantes):
            melhor = max(melhor, 0.85)
        pontuacoes.append((nome_canonico, melhor))

    pontuacoes.sort(key=lambda par: par[1], reverse=True)
    melhor_nome, melhor_pontuacao = pontuacoes[0]

    if melhor_pontuacao < _LIMIAR_MEDIA:
        return None, CONFIANCA_BAIXA, []

    # Candidatos "empatados" (dentro de uma margem pequena do melhor)
    # viram ambiguidade — nunca escolhe um dos dois por sorte.
    empatados = [nome for nome, pontuacao in pontuacoes if pontuacao >= melhor_pontuacao - 0.08]

    if len(empatados) > 1:
        return None, CONFIANCA_MEDIA, empatados

    if melhor_pontuacao >= _LIMIAR_ALTA:
        return melhor_nome, CONFIANCA_ALTA, [melhor_nome]

    return melhor_nome, CONFIANCA_MEDIA, [melhor_nome]


def abrir_aplicativo(programa):
    """(sucesso: bool, mensagem: str) — nunca assume que o programa
    existe: só relata "não encontrei" quando é a verdade."""
    caminho = localizar_executavel(programa)
    if not caminho:
        return False, f"Não encontrei esse programa neste computador."

    try:
        subprocess.Popen([caminho])
        return True, f"Abrindo {programa}."
    except Exception as erro:
        return False, f"Encontrei {programa}, mas não consegui abrir: {erro}"
