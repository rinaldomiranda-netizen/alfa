"""
Empacota a distribuição BETA PORTÁTIL — uma cópia limpa do núcleo,
sem nada pessoal do ALFA (Rinaldo), pronta para ser copiada para um
pendrive e testada em outro computador.

NÃO reescreve nenhum módulo do núcleo — só copia arquivos já
existentes para uma pasta de saída separada (dist/BETA_PORTATIL/) e
gera dois arquivos novos, exclusivos da distribuição:
  - scripts/verificar_dependencias.py (checagem, nunca instalação)
  - iniciar.bat (atalho para clique duplo no Windows)

Todos os caminhos são resolvidos a partir de __file__ — nenhuma
referência a "C:\\Users\\Rinaldo..." nem a este computador.

Uso:
    python scripts/empacotar_portatil.py
"""

import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(BASE, "dist", "BETA_PORTATIL")

# Pastas do núcleo copiadas integralmente (reaproveitamento total —
# nenhum arquivo novo de lógica é criado aqui).
PASTAS_NUCLEO = [
    "launcher",
    "core",
    "agente",
    "computer",
    "vision",
    "voice",
    "ui",
    "security",
    "skills",
    # Expansão de plataforma (integrações/dispositivos genéricos — ver
    # integrations/base.py e devices/base.py): sem adaptador nenhum
    # registrado por padrão, só a interface.
    "integrations",
    "devices",
    # Marketplace de habilidades local (ver marketplace/pacotes.py) —
    # funciona 100% offline com pacotes locais; admin/ e mobile/ ficam
    # de fora de propósito (não fazem parte do runtime da BETA em si).
    "marketplace",
]

IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")

# Terceiros usados pelo núcleo (ver imports reais do projeto) — só
# para o checador de dependências, nunca para instalar nada.
DEPENDENCIAS_TERCEIROS = [
    "numpy", "cv2", "psutil", "pyautogui", "pygame", "pyttsx3",
    "pywinauto", "requests", "sounddevice", "speech_recognition",
    "edge_tts", "faster_whisper", "ctranslate2", "win32com",
    "win32con", "win32gui", "winsdk", "sentence_transformers", "spacy",
]


def _limpar_dist():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST, exist_ok=True)


def _copiar_nucleo():
    for pasta in PASTAS_NUCLEO:
        origem = os.path.join(BASE, pasta)
        destino = os.path.join(DIST, pasta)
        shutil.copytree(origem, destino, ignore=IGNORAR)

    # NOTA: core/pesquisa_app.py é copiado sem nenhuma alteração —
    # agente/verificador.py depende dele (encontrar_janela_pesquisa é
    # um utilitário genérico de janela, não é exclusivo da pesquisa) e
    # a instrução vigente é nunca tocar nesse arquivo sem permissão
    # explícita. Ele contém um CAMINHO_LOCAL_PADRAO fixo do computador
    # de Rinaldo, mas só é usado por abrir_aplicativo(), que checa
    # os.path.exists() antes de tentar abrir — em outro computador
    # apenas retorna False sem erro. Ver pendências no relatório final.


def _copiar_memoria_sem_dados_pessoais():
    """Só o CÓDIGO de memory/ — nunca memory/atendimentos/ (pessoal de
    Rinaldo) nem memory/ambiente.json (cache de hardware deste PC)."""
    destino = os.path.join(DIST, "memory")
    os.makedirs(destino, exist_ok=True)
    for nome in ("memory.py", "sync.py"):
        shutil.copy2(os.path.join(BASE, "memory", nome), os.path.join(destino, nome))


def _criar_config_portatil_vazia():
    """config/local/ vazio — cada perfil cria sua própria subpasta no
    primeiro uso (ver launcher/iniciar_portatil.py). Nunca inclui
    config/alfa.json (perfil pessoal de Rinaldo)."""
    pasta = os.path.join(DIST, "config", "local")
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, ".gitkeep"), "w", encoding="utf-8") as arquivo:
        arquivo.write("")


def _criar_workspace_vazio():
    pasta = os.path.join(DIST, "workspace")
    os.makedirs(pasta, exist_ok=True)
    shutil.copy2(os.path.join(BASE, "workspace", "LEIAME.txt"), os.path.join(pasta, "LEIAME.txt"))


def _copiar_env_exemplo():
    """Só o .env.example (sem segredo nenhum) — nunca um .env real."""
    origem = os.path.join(BASE, ".env.example")
    if os.path.exists(origem):
        shutil.copy2(origem, os.path.join(DIST, ".env.example"))


def _gerar_verificador_dependencias():
    pasta = os.path.join(DIST, "scripts")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, "verificar_dependencias.py")
    conteudo = '''"""
Verifica se as bibliotecas que a BETA PORTÁTIL precisa já estão
disponíveis no Python deste computador. NUNCA instala nada
automaticamente — só informa o que falta, para instalação manual
(ex.: pip install -r requirements_portatil.txt).

Uso:
    python scripts/verificar_dependencias.py
"""

import importlib

DEPENDENCIAS = ''' + repr(DEPENDENCIAS_TERCEIROS) + '''


def main():
    faltando = []
    for nome in DEPENDENCIAS:
        try:
            importlib.import_module(nome)
        except Exception:
            faltando.append(nome)

    print("=" * 50)
    print("Verificação de dependências — BETA PORTÁTIL")
    print("=" * 50)
    if not faltando:
        print("Todas as dependências verificadas estão disponíveis.")
        return

    print(f"Faltando {len(faltando)} de {len(DEPENDENCIAS)}:")
    for nome in faltando:
        print(f"  - {nome}")
    print()
    print("Nada foi instalado automaticamente. Para instalar:")
    print("    pip install -r requirements_portatil.txt")


if __name__ == "__main__":
    main()
'''
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def _gerar_requirements():
    """Congela as versões já validadas neste projeto (referência), sem
    instalar nada — quem usa o pendrive decide se/quando instalar."""
    import subprocess

    python_venv = os.path.join(BASE, ".venv311", "Scripts", "python.exe")
    interpretador = python_venv if os.path.exists(python_venv) else sys.executable
    try:
        saida = subprocess.check_output([interpretador, "-m", "pip", "freeze"], text=True, timeout=60)
    except Exception:
        saida = ""
    with open(os.path.join(DIST, "requirements_portatil.txt"), "w", encoding="utf-8") as arquivo:
        arquivo.write(saida)


def _gerar_iniciar_bat():
    conteudo = (
        "@echo off\r\n"
        "REM Inicia a BETA PORTATIL a partir desta propria pasta.\r\n"
        "REM Nao assume letra de unidade nem caminho fixo.\r\n"
        "cd /d %~dp0\r\n"
        "python launcher\\iniciar_portatil.py\r\n"
        "pause\r\n"
    )
    with open(os.path.join(DIST, "iniciar.bat"), "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def _gerar_leiame():
    conteudo = """BETA PORTATIL
=============

Como iniciar:
  1) Verifique dependencias:  python scripts\\verificar_dependencias.py
  2) Inicie:                  iniciar.bat   (ou: python launcher\\iniciar_portatil.py)

Primeiro uso nesta maquina:
  A Beta pergunta com quem esta falando e se e uso pessoal ou de uma
  empresa/organizacao. Cada resposta cria um perfil isolado em:
    config\\local\\<perfil>\\
    memory\\portatil\\<perfil>\\
    workspace\\<perfil>\\

  Nenhum perfil enxerga a memoria de outro perfil.

Nuvem (BETA-CLOUD):
  Vem desligada por padrao (cloud.enabled=false, sync.enabled=false).
  A Beta funciona 100% offline sem isso. Para ligar depois, configure
  BETA_CLOUD_PROJECT_URL e BETA_CLOUD_PUBLISHABLE_KEY (ver .env.example)
  - nunca ponha a chave service_role aqui.

Voz (Whisper / Edge TTS):
  Reaproveita os modelos ja configurados/cacheados no Python usado.
  Se o modelo do Whisper nao estiver disponivel neste computador, o
  proprio programa avisa o que falta - nada e baixado automaticamente
  sem necessidade.

Dependencias:
  requirements_portatil.txt lista as versoes ja validadas no projeto
  original, soh como referencia. Nada e instalado sozinho; use
  scripts\\verificar_dependencias.py para saber o que falta e depois:
    pip install -r requirements_portatil.txt
"""
    with open(os.path.join(DIST, "LEIAME.txt"), "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def empacotar():
    _limpar_dist()
    _copiar_nucleo()
    _copiar_memoria_sem_dados_pessoais()
    _criar_config_portatil_vazia()
    _criar_workspace_vazio()
    _copiar_env_exemplo()
    _gerar_verificador_dependencias()
    _gerar_requirements()
    _gerar_iniciar_bat()
    _gerar_leiame()
    return DIST


if __name__ == "__main__":
    caminho = empacotar()
    print(f"Distribuição criada em: {caminho}")
