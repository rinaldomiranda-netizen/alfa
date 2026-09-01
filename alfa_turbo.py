import os
import sys
import time
import base64
import json
import subprocess
import webbrowser
import urllib.request
import pyautogui
import cv2

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from voice.alfa_voice import ALFA
from core.semantic_router import SemanticRouter
from core.intent_engine import IntentEngine

intent_engine = IntentEngine()

OLLAMA = "http://127.0.0.1:11434/api/chat"


def perguntar_visao(imagem, pergunta, modelo="qwen2.5vl:3b"):
    with open(imagem, "rb") as f:
        img = base64.b64encode(f.read()).decode()

    dados = {
        "model": modelo,
        "messages": [{
            "role": "user",
            "content": pergunta,
            "images": [img]
        }],
        "stream": False, "keep_alive": -1, "options": {"temperature": 0.1, "num_predict": 120}
    }

    req = urllib.request.Request(
        OLLAMA,
        data=json.dumps(dados).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=120) as resposta:
        resultado = json.loads(resposta.read().decode())

    return resultado["message"]["content"]


def captura_tela():
    arquivo = os.path.join(BASE, "visao_tela.png")
    imagem = pyautogui.screenshot()
    imagem.save(arquivo)
    return arquivo


def captura_camera():
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        return None

    time.sleep(1)

    ok, frame = camera.read()
    camera.release()

    if not ok:
        return None

    arquivo = os.path.join(BASE, "visao_camera.jpg")
    cv2.imwrite(arquivo, frame)

    return arquivo


def abrir_programa(nome):

    programas = {
        "calculadora": "calc.exe",
        "bloco de notas": "notepad.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "gerenciador de tarefas": "taskmgr.exe",
        "explorador": "explorer.exe",
        "explorador de arquivos": "explorer.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe"
    }

    nome = nome.lower()

    for chave, exe in programas.items():
        if chave in nome:
            subprocess.Popen(exe)
            return f"{chave} aberto."

    if "chrome" in nome:
        subprocess.Popen("chrome.exe")
        return "Chrome aberto."

    if "edge" in nome:
        subprocess.Popen("msedge.exe")
        return "Edge aberto."

    if "vs code" in nome or "visual studio code" in nome:
        subprocess.Popen("code")
        return "VS Code aberto."

    return None


def fechar_programa(nome):

    processos = {
        "calculadora": "CalculatorApp.exe",
        "bloco de notas": "notepad.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "vs code": "Code.exe"
    }

    nome = nome.lower()

    for chave, processo in processos.items():

        if chave in nome:

            resultado = subprocess.run(
                ["taskkill", "/F", "/IM", processo],
                capture_output=True,
                text=True
            )

            if resultado.returncode == 0:
                return f"{chave} fechado."

            return f"{chave} não está aberto."

    return None



def comando_mouse_voz(comando):
    import re
    import unicodedata

    c = comando.lower()
    c = ''.join(
        x for x in unicodedata.normalize("NFD", c)
        if unicodedata.category(x) != "Mn"
    )

    # Erros comuns do reconhecimento de voz
    movimento = any(x in c for x in [
        "mova", "move", "movi", "moval", "mover",
        "mexa", "mexer", "leve", "levar",
        "coloque", "colocar", "arraste", "arrastar"
    ])

    mouse = any(x in c for x in [
        "mouse", "mause", "maus", "malwe", "malve", "mou"
    ])

    if not (movimento and mouse):
        return None

    largura, altura = pyautogui.size()
    x, y = pyautogui.position()

    if any(x in c for x in ["direita", "lado direito", "pra direita"]):
        pyautogui.moveTo(min(largura - 1, x + 300), y, duration=0.03)
        return "Mouse movido para a direita."

    if any(x in c for x in ["esquerda", "lado esquerdo", "pra esquerda"]):
        pyautogui.moveTo(max(0, x - 300), y, duration=0.03)
        return "Mouse movido para a esquerda."

    if "cima" in c:
        pyautogui.moveTo(x, max(0, y - 300), duration=0.03)
        return "Mouse movido para cima."

    if "baixo" in c:
        pyautogui.moveTo(x, min(altura - 1, y + 300), duration=0.03)
        return "Mouse movido para baixo."

    if "centro" in c:
        pyautogui.moveTo(largura // 2, altura // 2, duration=0.03)
        return "Mouse movido para o centro."

    return "Entendi que voc? quer mover o mouse. Diga: direita, esquerda, cima, baixo ou centro."


def comando_rapido(comando):

    c = comando.lower().strip()

    if any(x in c for x in [
        "abrir calculadora",
        "abra a calculadora",
        "abre a calculadora"
    ]):
        return abrir_programa("calculadora")

    if any(x in c for x in [
        "fechar calculadora",
        "feche a calculadora",
        "fecha a calculadora",
        "fecha calculadora"
    ]):
        return fechar_programa("calculadora")

    if "abrir bloco de notas" in c or "abra o bloco de notas" in c:
        return abrir_programa("bloco de notas")

    if "fechar bloco de notas" in c or "feche o bloco de notas" in c:
        return fechar_programa("bloco de notas")

    if "abrir chrome" in c or "abra o chrome" in c:
        return abrir_programa("chrome")

    if "abrir edge" in c or "abra o edge" in c:
        return abrir_programa("edge")

    if "abrir vs code" in c or "abra o vs code" in c:
        return abrir_programa("vs code")

    if "posição do mouse" in c or "posicao do mouse" in c:
        x, y = pyautogui.position()
        return f"O mouse está na posição {x} por {y}."

    if "mova o mouse para o centro" in c or "mova o mouse pro centro" in c:
        largura, altura = pyautogui.size()
        pyautogui.moveTo(largura // 2, altura // 2, duration=0.05)
        return "Mouse movido para o centro da tela."

    if "mova o mouse para cima" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(x, max(0, y - 200), duration=0.05)
        return "Mouse movido para cima."

    if "mova o mouse para baixo" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(x, y + 200, duration=0.05)
        return "Mouse movido para baixo."

    if "mova o mouse para a esquerda" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(max(0, x - 200), y, duration=0.05)
        return "Mouse movido para a esquerda."

    if "mova o mouse para a direita" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(x + 200, y, duration=0.05)
        return "Mouse movido para a direita."

    if "clique" in c and "botão esquerdo" in c:
        pyautogui.click()
        return "Clique realizado."

    if "clique" in c and "botão direito" in c:
        pyautogui.rightClick()
        return "Clique direito realizado."

    if "clique" in c:
        pyautogui.click()
        return "Clique realizado."

    return None




def executar_intencao_semantica(intencao, alfa):

    tipo = intencao.get("intent")

    if tipo == "MOVER_MOUSE":

        largura, altura = pyautogui.size()
        x, y = pyautogui.position()
        direcao = intencao.get("direcao")

        if direcao == "direita":
            pyautogui.moveTo(
                min(largura - 1, x + 300),
                y,
                duration=0.02
            )
            alfa.falar("Mouse movido para a direita.")
            return True

        if direcao == "esquerda":
            pyautogui.moveTo(
                max(0, x - 300),
                y,
                duration=0.02
            )
            alfa.falar("Mouse movido para a esquerda.")
            return True

        if direcao == "cima":
            pyautogui.moveTo(
                x,
                max(0, y - 300),
                duration=0.02
            )
            alfa.falar("Mouse movido para cima.")
            return True

        if direcao == "baixo":
            pyautogui.moveTo(
                x,
                min(altura - 1, y + 300),
                duration=0.02
            )
            alfa.falar("Mouse movido para baixo.")
            return True

        if direcao == "centro":
            pyautogui.moveTo(
                largura // 2,
                altura // 2,
                duration=0.02
            )
            alfa.falar("Mouse movido para o centro.")
            return True

        alfa.falar(
            "Entendi que voc? quer mover o mouse. "
            "Diga a dire??o."
        )
        return True

    if tipo == "CLIQUE":

        botao = intencao.get("botao")

        if botao == "direito":
            pyautogui.rightClick()

        elif botao == "duplo":
            pyautogui.doubleClick()

        else:
            pyautogui.click()

        alfa.falar("Clique realizado.")
        return True

    if tipo == "POSICAO_MOUSE":

        x, y = pyautogui.position()

        alfa.falar(
            f"O mouse est? na posi??o {x} por {y}."
        )

        return True

    if tipo == "COPIAR":
        pyautogui.hotkey("ctrl", "c")
        alfa.falar("Copiado.")
        return True

    if tipo == "COLAR":
        pyautogui.hotkey("ctrl", "v")
        alfa.falar("Colado.")
        return True

    if tipo == "DESFAZER":
        pyautogui.hotkey("ctrl", "z")
        alfa.falar("Desfeito.")
        return True

    if tipo == "SELECIONAR_TUDO":
        pyautogui.hotkey("ctrl", "a")
        alfa.falar("Tudo selecionado.")
        return True

    if tipo == "ENTER":
        pyautogui.press("enter")
        alfa.falar("Enter pressionado.")
        return True

    if tipo == "ESC":
        pyautogui.press("esc")
        alfa.falar("Escape pressionado.")
        return True

    if tipo in ("ABRIR", "FECHAR"):

        programa = intencao.get("programa")

        if programa:

            comando = (
                "abra " if tipo == "ABRIR"
                else "feche "
            ) + programa

            resultado = executar_local(comando)

            if resultado:
                alfa.falar(resultado)
                return True

    return False




def executar_intencao_alfa(intencao, alfa):

    tipo = intencao.get("intent")

    if tipo == "MOVER_MOUSE":

        import pyautogui

        direcao = intencao.get("direcao")

        largura, altura = pyautogui.size()
        x, y = pyautogui.position()

        distancia = 300

        if direcao == "esquerda":
            pyautogui.moveTo(
                max(0, x - distancia),
                y,
                duration=0.02
            )
            alfa.falar("Mouse movido para a esquerda.")
            return True

        if direcao == "direita":
            pyautogui.moveTo(
                min(largura - 1, x + distancia),
                y,
                duration=0.02
            )
            alfa.falar("Mouse movido para a direita.")
            return True

        if direcao == "cima":
            pyautogui.moveTo(
                x,
                max(0, y - distancia),
                duration=0.02
            )
            alfa.falar("Mouse movido para cima.")
            return True

        if direcao == "baixo":
            pyautogui.moveTo(
                x,
                min(altura - 1, y + distancia),
                duration=0.02
            )
            alfa.falar("Mouse movido para baixo.")
            return True

        if direcao == "centro":
            pyautogui.moveTo(
                largura // 2,
                altura // 2,
                duration=0.02
            )
            alfa.falar("Mouse movido para o centro.")
            return True

        # Entendeu mouse + movimento, mas n?o entendeu dire??o.
        alfa.falar(
            "Entendi que voc? quer mover o mouse. "
            "Para qual lado?"
        )
        return True

    if tipo == "POSICAO_MOUSE":

        import pyautogui

        x, y = pyautogui.position()

        alfa.falar(
            f"O mouse est? na posi??o {x} por {y}."
        )
        return True

    if tipo == "CLIQUE":

        import pyautogui

        botao = intencao.get("botao")

        if botao == "direito":
            pyautogui.rightClick()
        elif botao == "duplo":
            pyautogui.doubleClick()
        else:
            pyautogui.click()

        alfa.falar("Clique realizado.")
        return True

    if tipo == "COPIAR":
        import pyautogui
        pyautogui.hotkey("ctrl", "c")
        alfa.falar("Copiado.")
        return True

    if tipo == "COLAR":
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
        alfa.falar("Colado.")
        return True

    if tipo == "DESFAZER":
        import pyautogui
        pyautogui.hotkey("ctrl", "z")
        alfa.falar("Desfeito.")
        return True

    if tipo == "SELECIONAR_TUDO":
        import pyautogui
        pyautogui.hotkey("ctrl", "a")
        alfa.falar("Tudo selecionado.")
        return True

    if tipo == "ENTER":
        import pyautogui
        pyautogui.press("enter")
        alfa.falar("Enter pressionado.")
        return True

    if tipo == "ESC":
        import pyautogui
        pyautogui.press("esc")
        alfa.falar("Escape pressionado.")
        return True

    return False


def main():

    alfa = ALFA()
    semantic_router = SemanticRouter()

    print("=" * 65)
    print("                         ALFA TURBO")
    print("              VISÃO + CÂMERA + COMPUTADOR")
    print("=" * 65)

    alfa.falar(
        "ALFA Turbo iniciado. Estou pronto."
    )

    while True:

        try:

            comando = alfa.ouvir()

            if not comando:
                continue

            comando = comando.lower().strip()

            print("\nVOCÊ:", comando)

            if any(x in comando for x in [
                "sair",
                "saia",
                "encerra",
                "encerrar",
                "desligar alfa",
                "pare alfa"
            ]):
                alfa.falar("Encerrando o ALFA.")
                break

            resultado_mouse_voz = comando_mouse_voz(comando)

            if resultado_mouse_voz:
                print("ALFA MOUSE:", resultado_mouse_voz)
                alfa.falar(resultado_mouse_voz)
                continue

            resultado = comando_rapido(comando)

            if resultado:
                print("ALFA:", resultado)
                alfa.falar(resultado)
                continue

            if any(x in comando for x in [
                "olhe minha tela",
                "veja minha tela",
                "analise minha tela",
                "olhe a tela",
                "o que está na minha tela",
                "o que esta na minha tela"
            ]):

                alfa.falar("Estou olhando sua tela.")

                arquivo = captura_tela()

                resposta = perguntar_visao(
                    arquivo,
                    "Analise esta tela. Descreva o que está acontecendo e destaque botões, janelas, textos e elementos importantes."
                )

                print("\nVISÃO:", resposta)
                alfa.falar(resposta[:700])

                continue

            if any(x in comando for x in [
                "veja pela câmera",
                "veja pela camera",
                "olhe pela câmera",
                "olhe pela camera",
                "veja o ambiente",
                "olhe o ambiente",
                "o que você está vendo",
                "o que voce esta vendo"
            ]):

                alfa.falar("Vou olhar pela câmera.")

                arquivo = captura_camera()

                if not arquivo:
                    alfa.falar("Não consegui acessar a câmera.")
                    continue

                resposta = perguntar_visao(
                    arquivo,
                    "Analise esta imagem da câmera. Descreva o ambiente, objetos e pessoas visíveis. Não tente determinar a identidade de pessoas não cadastradas."
                )

                print("\nCÂMERA:", resposta)
                alfa.falar(resposta[:700])

                continue

            if "sou eu" in comando or "reconheça meu rosto" in comando:

                arquivo = captura_camera()

                if not arquivo:
                    alfa.falar("Não consegui acessar a câmera.")
                    continue

                resposta = perguntar_visao(
                    arquivo,
                    "Há uma pessoa nesta imagem. Descreva visualmente a pessoa e diga apenas se há uma pessoa visível. Não atribua identidade ou nome."
                )

                print("\nCÂMERA:", resposta)
                alfa.falar(resposta[:700])

                continue

            alfa.falar(
                "Vou consultar meu cérebro para entender esse comando."
            )

            try:

                dados = {
                    "model": "qwen2.5-coder:7b",
                    "messages": [{
                        "role": "user",
                        "content": (
                            "Você é o cérebro do ALFA. "
                            "Responda em português do Brasil, "
                            "de forma curta e objetiva. "
                            "O usuário disse: " + comando
                        )
                    }],
                    "stream": False, "keep_alive": -1, "options": {"temperature": 0.1, "num_predict": 120}
                }

                req = urllib.request.Request(
                    OLLAMA,
                    data=json.dumps(dados).encode(),
                    headers={"Content-Type": "application/json"}
                )

                with urllib.request.urlopen(req, timeout=120) as r:
                    resposta = json.loads(
                        r.read().decode()
                    )["message"]["content"]

                print("\nALFA:", resposta)
                alfa.falar(resposta[:700])

            except Exception as erro:

                print("ERRO IA:", erro)

                alfa.falar(
                    "Ainda não consigo executar essa ação."
                )

        except KeyboardInterrupt:

            print("\nALFA encerrado.")
            break

        except Exception as erro:

            print("\nERRO:", erro)


if __name__ == "__main__":
    main()




