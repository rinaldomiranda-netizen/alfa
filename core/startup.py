"""
Inicialização automática do ALFA com o Windows.

Cria/remove um atalho na pasta de Inicialização do usuário atual
(shell:startup) apontando para scripts/iniciar_alfa_silencioso.vbs,
que roda o ALFA em segundo plano (sem janela de console) usando o
Python do ambiente virtual do projeto.

Não é chamado automaticamente em nenhum lugar do projeto: só é
executado quando o usuário pedir explicitamente (via
`python main.py --instalar-inicializacao`, `--remover-inicializacao`
ou rodando os scripts .ps1 equivalentes em scripts/).
"""

import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VBS_PATH = os.path.join(BASE, "scripts", "iniciar_alfa_silencioso.vbs")
NOME_ATALHO = "ALFA.lnk"


def _pasta_inicializacao():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("Variável de ambiente APPDATA não encontrada.")
    return os.path.join(
        appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )


def _caminho_atalho():
    return os.path.join(_pasta_inicializacao(), NOME_ATALHO)


def esta_instalado():
    return os.path.exists(_caminho_atalho())


def instalar():
    if not os.path.exists(VBS_PATH):
        raise FileNotFoundError(f"Não encontrei {VBS_PATH}.")

    import win32com.client

    atalho_path = _caminho_atalho()

    shell = win32com.client.Dispatch("WScript.Shell")
    atalho = shell.CreateShortCut(atalho_path)
    atalho.TargetPath = "wscript.exe"
    atalho.Arguments = f'"{VBS_PATH}"'
    atalho.WorkingDirectory = BASE
    atalho.Description = "Inicia o assistente de voz ALFA junto com o Windows"
    atalho.Save()

    return atalho_path


def remover():
    atalho_path = _caminho_atalho()
    if os.path.exists(atalho_path):
        os.remove(atalho_path)
        return True
    return False
