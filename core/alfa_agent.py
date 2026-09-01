import os
import json
import base64
import urllib.request
import subprocess
import time
import pyautogui

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

MODEL_TEXT = "qwen2.5-coder:7b"
MODEL_VISION = "qwen2.5vl:3b"


def ollama_chat(model, messages):

    dados = {
        "model": model,
        "messages": messages,
        "stream": False
    }

    corpo = json.dumps(dados).encode("utf-8")

    requisicao = urllib.request.Request(
        OLLAMA_URL,
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(requisicao, timeout=180) as resposta:
        resultado = json.loads(resposta.read().decode("utf-8"))

    return resultado["message"]["content"]


def capturar_tela():

    arquivo = os.path.abspath("alfa_tela_agente.png")

    imagem = pyautogui.screenshot()
    imagem.save(arquivo)

    return arquivo


def analisar_tela():

    arquivo = capturar_tela()

    with open(arquivo, "rb") as f:
        imagem = base64.b64encode(f.read()).decode("utf-8")

    mensagens = [
        {
            "role": "system",
            "content": """
Você é o módulo de visão do ALFA.

Analise a captura de tela enviada.
Responda em português do Brasil.

Descreva:
1. qual aplicativo está aberto;
2. o que aparece na tela;
3. possíveis erros;
4. botões ou elementos importantes;
5. coordenadas aproximadas de elementos importantes quando forem visíveis.

Não invente elementos que não estejam na imagem.
"""
        },
        {
            "role": "user",
            "content": "Analise minha tela.",
            "images": [imagem]
        }
    ]

    return ollama_chat(MODEL_VISION, mensagens)


def executar_acao(acao):

    tipo = acao.get("acao")

    if tipo == "abrir":

        programa = acao.get("programa", "").lower()

        programas = {
            "calculadora": "calc.exe",
            "notepad": "notepad.exe",
            "bloco de notas": "notepad.exe",
            "paint": "mspaint.exe",
            "explorador": "explorer.exe"
        }

        if programa in programas:
            subprocess.Popen(programas[programa], shell=True)
            return f"{programa} aberto."

        if "vs code" in programa or "visual studio code" in programa:
            subprocess.Popen("code", shell=True)
            return "VS Code aberto."

        return "Não conheço esse programa."

    if tipo == "fechar":

        programa = acao.get("programa", "").lower()

        processos = {
            "calculadora": "CalculatorApp.exe",
            "notepad": "notepad.exe",
            "bloco de notas": "notepad.exe",
            "paint": "mspaint.exe",
            "vs code": "Code.exe"
        }

        nome = processos.get(programa)

        if not nome:
            return "Não tenho o processo desse aplicativo cadastrado."

        encontrado = False

        for processo in __import__("psutil").process_iter(["name"]):

            try:
                if processo.info["name"] and processo.info["name"].lower() == nome.lower():
                    processo.terminate()
                    encontrado = True
            except:
                pass

        return f"{programa} fechado." if encontrado else f"{programa} não está aberto."

    if tipo == "clicar":

        x = acao.get("x")
        y = acao.get("y")

        if x is None or y is None:
            return "Coordenadas inválidas."

        pyautogui.moveTo(int(x), int(y), duration=0.3)
        pyautogui.click()

        return f"Clique realizado em X {x}, Y {y}."

    if tipo == "digitar":

        texto = acao.get("texto", "")

        pyautogui.write(texto, interval=0.01)

        return "Texto digitado."

    if tipo == "enter":

        pyautogui.press("enter")

        return "Enter pressionado."

    if tipo == "mouse":

        x, y = pyautogui.position()

        return f"O mouse está em X {x}, Y {y}."

    return "Ação não reconhecida."


def planejar(comando):

    prompt = f"""
Você é o controlador do computador ALFA.

O usuário disse:

"{comando}"

Determine se é necessário executar uma ação no computador.

Responda SOMENTE com JSON válido.

Use exatamente um destes formatos:

{{"acao":"abrir","programa":"calculadora"}}

{{"acao":"fechar","programa":"calculadora"}}

{{"acao":"clicar","x":500,"y":300}}

{{"acao":"digitar","texto":"texto aqui"}}

{{"acao":"enter"}}

{{"acao":"mouse"}}

{{"acao":"visao"}}

{{"acao":"nenhuma"}}

Não coloque explicações fora do JSON.
"""

    resposta = ollama_chat(
        MODEL_TEXT,
        [
            {
                "role": "system",
                "content": "Você é um planejador de ações para o ALFA."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    inicio = resposta.find("{")
    fim = resposta.rfind("}")

    if inicio == -1 or fim == -1:
        return {"acao": "nenhuma"}

    try:
        return json.loads(resposta[inicio:fim + 1])
    except:
        return {"acao": "nenhuma"}


def responder(comando):

    acao = planejar(comando)

    print("\nALFA PLANO:", acao)

    if acao["acao"] == "visao":

        print("\nALFA: Estou analisando sua tela...\n")

        resultado = analisar_tela()

        print("ALFA VISÃO:")
        print(resultado)

        return resultado

    if acao["acao"] == "nenhuma":

        resposta = ollama_chat(
            MODEL_TEXT,
            [
                {
                    "role": "system",
                    "content": """
Você é ALFA, assistente pessoal do usuário.
Responda em português do Brasil.
Seja objetivo e útil.
"""
                },
                {
                    "role": "user",
                    "content": comando
                }
            ]
        )

        return resposta

    return executar_acao(acao)


def main():

    print("=" * 65)
    print("                         ALFA")
    print("                 ASSISTENTE PESSOAL")
    print("                    MODO AGENTE")
    print("=" * 65)

    print("\nALFA: Sistema de agente iniciado.")
    print("ALFA: Cérebro  = qwen2.5-coder:7b")
    print("ALFA: Visão    = qwen2.5vl:3b")
    print("\nDigite um comando.")
    print("Digite 'sair' para encerrar.\n")

    while True:

        try:

            comando = input("VOCÊ: ").strip()

            if not comando:
                continue

            if comando.lower() in ["sair", "encerrar", "fechar alfa"]:
                print("ALFA: Encerrando.")
                break

            resultado = responder(comando)

            print("\nALFA:", resultado)

        except KeyboardInterrupt:

            print("\nALFA: Encerrado pelo usuário.")
            break

        except Exception as erro:

            print("\nALFA: Erro:", erro)


if __name__ == "__main__":
    main()
