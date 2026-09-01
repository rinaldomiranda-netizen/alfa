from pathlib import Path

p = Path("alfa_turbo.py")

codigo = r'''
import os
import sys
import re
import time
import json
import base64
import urllib.request
import subprocess
import unicodedata
from difflib import SequenceMatcher

import pyautogui
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice.alfa_voice import ALFA


OLLAMA = "http://127.0.0.1:11434/api/chat"
VISION_MODEL = "qwen2.5vl:3b"
BRAIN_MODEL = "qwen2.5-coder:7b"


# ============================================================
# NORMALIZAÇÃO INTELIGENTE
# ============================================================

def limpar(texto):
    texto = texto.lower().strip()

    texto = ''.join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )

    texto = re.sub(r"\balfa\b", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def parecido(texto, palavras, limite=0.62):

    for palavra in palavras:

        if palavra in texto:
            return True

        partes = texto.split()

        for parte in partes:

            if len(parte) >= 3:

                nota = SequenceMatcher(
                    None,
                    parte,
                    palavra
                ).ratio()

                if nota >= limite:
                    return True

    return False


# ============================================================
# CONTROLE DO MOUSE
# ============================================================

def mouse(comando):

    c = limpar(comando)

    quer_mover = (
        parecido(c, [
            "mova",
            "move",
            "mover",
            "mexa",
            "mexer",
            "leve",
            "levar",
            "coloque",
            "colocar",
            "arraste",
            "arrastar",
            "moval"
        ])
        and
        parecido(c, [
            "mouse",
            "mause",
            "malwe",
            "malve",
            "maus",
            "mou"
        ])
    )

    if not quer_mover:
        return None

    largura, altura = pyautogui.size()
    x, y = pyautogui.position()

    if parecido(c, ["direita"]):
        pyautogui.moveTo(
            min(largura - 1, x + 300),
            y,
            duration=0.03
        )
        return "Mouse movido para a direita."

    if parecido(c, ["esquerda"]):
        pyautogui.moveTo(
            max(0, x - 300),
            y,
            duration=0.03
        )
        return "Mouse movido para a esquerda."

    if parecido(c, ["cima"]):
        pyautogui.moveTo(
            x,
            max(0, y - 300),
            duration=0.03
        )
        return "Mouse movido para cima."

    if parecido(c, ["baixo"]):
        pyautogui.moveTo(
            x,
            min(altura - 1, y + 300),
            duration=0.03
        )
        return "Mouse movido para baixo."

    if parecido(c, ["centro"]):
        pyautogui.moveTo(
            largura // 2,
            altura // 2,
            duration=0.03
        )
        return "Mouse movido para o centro."

    return "Diga a direção: direita, esquerda, cima, baixo ou centro."


# ============================================================
# CLIQUES
# ============================================================

def clique(comando):

    c = limpar(comando)

    if not parecido(c, ["clique", "clicar", "clica", "clic"]):
        return None

    if parecido(c, ["direito"]):
        pyautogui.rightClick()
        return "Clique direito realizado."

    if parecido(c, ["duplo", "dupla"]):
        pyautogui.doubleClick()
        return "Duplo clique realizado."

    pyautogui.click()
    return "Clique realizado."


# ============================================================
# TECLADO
# ============================================================

def teclado(comando):

    c = limpar(comando)

    comandos = {

        "enter": ["pressione enter", "aperte enter", "tecle enter"],
        "esc": ["pressione esc", "aperte esc", "escape"],
        "tab": ["pressione tab", "aperte tab"],
        "space": ["pressione espaco", "aperte espaco"],
        "backspace": ["backspace", "apague"],
        "delete": ["delete", "deletar"],
        "home": ["inicio da pagina", "home"],
        "end": ["fim da pagina", "end"],

    }

    for tecla, frases in comandos.items():

        if any(frase in c for frase in frases):

            pyautogui.press(tecla)

            return f"{tecla} pressionado."

    if "copiar" in c:
        pyautogui.hotkey("ctrl", "c")
        return "Copiado."

    if "colar" in c:
        pyautogui.hotkey("ctrl", "v")
        return "Colado."

    if "recortar" in c:
        pyautogui.hotkey("ctrl", "x")
        return "Recortado."

    if "desfazer" in c:
        pyautogui.hotkey("ctrl", "z")
        return "Desfeito."

    if "refazer" in c:
        pyautogui.hotkey("ctrl", "y")
        return "Refeito."

    if "selecionar tudo" in c:
        pyautogui.hotkey("ctrl", "a")
        return "Tudo selecionado."

    return None


# ============================================================
# PROGRAMAS
# ============================================================

ABRIR = {
    "calculadora": "calc.exe",
    "bloco de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "explorador": "explorer.exe",
    "explorador de arquivos": "explorer.exe",
    "gerenciador de tarefas": "taskmgr.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
}

FECHAR = {
    "calculadora": "CalculatorApp.exe",
    "bloco de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "vs code": "Code.exe",
}


def programas(comando):

    c = limpar(comando)

    if any(x in c for x in [
        "vs code",
        "visual studio code"
    ]):

        if any(x in c for x in ["abra", "abrir", "abre"]):

            try:
                subprocess.Popen("code")
                return "VS Code aberto."
            except:
                return "Não consegui abrir o VS Code."

        if any(x in c for x in ["feche", "fecha", "fechar"]):

            subprocess.run(
                ["taskkill", "/F", "/IM", "Code.exe"],
                capture_output=True
            )

            return "VS Code fechado."

    for nome, exe in ABRIR.items():

        if nome in c and any(
            x in c for x in ["abra", "abrir", "abre"]
        ):

            try:
                subprocess.Popen(exe)
                return f"{nome} aberto."
            except:
                return f"Não consegui abrir {nome}."

    for nome, processo in FECHAR.items():

        if nome in c and any(
            x in c for x in ["feche", "fecha", "fechar"]
        ):

            resultado = subprocess.run(
                ["taskkill", "/F", "/IM", processo],
                capture_output=True,
                text=True
            )

            if resultado.returncode == 0:
                return f"{nome} fechado."

            return f"{nome} não está aberto."

    return None


# ============================================================
# JANELAS DO WINDOWS
# ============================================================

def sistema(comando):

    c = limpar(comando)

    if "minimize tudo" in c or "minimizar tudo" in c:
        pyautogui.hotkey("win", "d")
        return "Janelas minimizadas."

    if "mostrar area de trabalho" in c:
        pyautogui.hotkey("win", "d")
        return "Área de trabalho mostrada."

    if "alt tab" in c or "troque de janela" in c:
        pyautogui.hotkey("alt", "tab")
        return "Janela alternada."

    if "abrir explorador" in c:
        subprocess.Popen("explorer.exe")
        return "Explorador aberto."

    return None


# ============================================================
# VISÃO DA TELA
# ============================================================

def capturar_tela():

    arquivo = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "_alfa_tela.png"
    )

    pyautogui.screenshot(arquivo)

    return arquivo


def consultar_visao(arquivo, pergunta):

    with open(arquivo, "rb") as f:
        imagem = base64.b64encode(
            f.read()
        ).decode()

    dados = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": pergunta,
            "images": [imagem]
        }],
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.1,
            "num_predict": 180
        }
    }

    requisicao = urllib.request.Request(
        OLLAMA,
        data=json.dumps(dados).encode(),
        headers={
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(
        requisicao,
        timeout=45
    ) as resposta:

        dados = json.loads(
            resposta.read().decode()
        )

    return dados["message"]["content"]


def visao(comando):

    c = limpar(comando)

    if not any(x in c for x in [
        "veja minha tela",
        "olhe minha tela",
        "analise minha tela",
        "veja a tela",
        "olhe a tela",
        "o que esta na minha tela"
    ]):
        return None

    arquivo = capturar_tela()

    return consultar_visao(
        arquivo,
        "Analise esta tela do computador. "
        "Descreva de forma curta o que aparece, "
        "incluindo janelas, botões, textos e elementos importantes."
    )


# ============================================================
# CÂMERA
# ============================================================

def capturar_camera():

    camera = cv2.VideoCapture(
        0,
        cv2.CAP_DSHOW
    )

    if not camera.isOpened():
        return None

    time.sleep(0.5)

    ok, frame = camera.read()

    camera.release()

    if not ok:
        return None

    arquivo = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "_alfa_camera.jpg"
    )

    cv2.imwrite(
        arquivo,
        frame
    )

    return arquivo


def camera(comando):

    c = limpar(comando)

    if not any(x in c for x in [
        "camera",
        "camera",
        "ambiente",
        "pela camera"
    ]):
        return None

    arquivo = capturar_camera()

    if not arquivo:
        return "Não consegui acessar a câmera."

    return consultar_visao(
        arquivo,
        "Analise esta imagem da câmera. "
        "Descreva o ambiente, objetos e pessoas "
        "visíveis. Não atribua identidade a pessoas."
    )


# ============================================================
# POSIÇÃO DO MOUSE
# ============================================================

def posicao(comando):

    c = limpar(comando)

    if any(x in c for x in [
        "posicao do mouse",
        "onde esta o mouse",
        "onde fica o mouse"
    ]):

        x, y = pyautogui.position()

        return f"O mouse está na posição {x} por {y}."

    return None


# ============================================================
# ROTEADOR LOCAL
# ============================================================

def executar_local(comando):

    funcoes = [
        mouse,
        clique,
        teclado,
        programas,
        sistema,
        posicao,
    ]

    for funcao in funcoes:

        try:

            resultado = funcao(comando)

            if resultado is not None:
                return resultado

        except Exception as erro:

            print("ERRO LOCAL:", erro)
            return "Não consegui executar essa ação."

    return None


# ============================================================
# CÉREBRO — SOMENTE ÚLTIMO RECURSO
# ============================================================

def cerebro(comando):

    dados = {
        "model": BRAIN_MODEL,
        "messages": [{
            "role": "user",
            "content": (
                "Você é o cérebro do ALFA. "
                "Responda em português do Brasil. "
                "Seja extremamente curto e objetivo. "
                "Não diga que não pode controlar o computador. "
                "Apenas explique ou responda ao usuário.\n\n"
                "Usuário: " + comando
            )
        }],
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.1,
            "num_predict": 100
        }
    }

    requisicao = urllib.request.Request(
        OLLAMA,
        data=json.dumps(dados).encode(),
        headers={
            "Content-Type": "application/json"
        }
    )

    try:

        with urllib.request.urlopen(
            requisicao,
            timeout=20
        ) as resposta:

            dados = json.loads(
                resposta.read().decode()
            )

        return dados["message"]["content"]

    except Exception:

        return "Não consegui processar esse comando."


# ============================================================
# ALFA
# ============================================================

def main():

    alfa = ALFA()

    print("=" * 60)
    print("                 ALFA TURBO")
    print("          CONTROLE LOCAL + VISÃO")
    print("=" * 60)

    alfa.falar(
        "ALFA iniciado. Estou pronto."
    )

    while True:

        try:

            comando = alfa.ouvir()

            if not comando:
                continue

            print("\nVOCÊ:", comando)

            c = limpar(comando)

            if any(x in c for x in [
                "sair",
                "saia",
                "encerre",
                "encerrar",
                "fechar alfa",
                "desligar alfa",
                "pare alfa"
            ]):

                alfa.falar(
                    "Encerrando o ALFA."
                )

                break

            # VISÃO
            resultado = visao(comando)

            if resultado:

                print("ALFA VISÃO:", resultado)
                alfa.falar(resultado[:500])
                continue

            # CÂMERA
            resultado = camera(comando)

            if resultado:

                print("ALFA CÂMERA:", resultado)
                alfa.falar(resultado[:500])
                continue

            # COMANDOS LOCAIS
            resultado = executar_local(comando)

            if resultado:

                print("ALFA:", resultado)
                alfa.falar(resultado)
                continue

            # SÓ AGORA USA O CÉREBRO
            print("ALFA: comando complexo — consultando IA...")

            resultado = cerebro(comando)

            print("ALFA:", resultado)

            alfa.falar(
                resultado[:500]
            )

        except KeyboardInterrupt:

            print("\nALFA encerrado.")
            break

        except Exception as erro:

            print("ERRO:", erro)

            try:
                alfa.falar(
                    "Ocorreu um erro."
                )
            except:
                pass


if __name__ == "__main__":
    main()
'''

p.write_text(codigo, encoding="utf-8")

print("ALFA TURBO REESTRUTURADO.")
