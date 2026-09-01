"""
Módulo de visão do ALFA.

Usado apenas para os comandos que REALMENTE precisam de IA
(VISUALIZAR / CAMERA): analisar o conteúdo da tela ou da câmera exige
um modelo multimodal, ao contrário de mover o mouse ou abrir um
programa, que são resolvidos localmente sem IA.
"""

import base64
import json
import os
import time
import urllib.request

import pyautogui

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODELO_VISAO_PADRAO = "qwen2.5vl:3b"


def _ollama_chat(mensagens, modelo=MODELO_VISAO_PADRAO, timeout=60):
    dados = {
        "model": modelo,
        "messages": mensagens,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }

    requisicao = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(dados).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        resultado = json.loads(resposta.read().decode("utf-8"))

    return resultado["message"]["content"].strip()


def capturar_tela():
    arquivo = os.path.join(BASE, "visao_tela.png")
    imagem = pyautogui.screenshot()
    imagem.save(arquivo)
    return arquivo


def capturar_camera():
    import cv2

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


def _imagem_base64(caminho):
    with open(caminho, "rb") as arquivo:
        return base64.b64encode(arquivo.read()).decode("utf-8")


def analisar_tela(timeout=60):
    """
    `timeout` menor (poucos segundos) é usado por chamadores
    "best-effort" que não podem travar esperando uma IA opcional —
    ex.: AtendimentoBeta.identificar_tela() — mantendo o princípio de
    que serviços online são sempre opcionais e nunca bloqueiam o
    ALFA por muito tempo quando estão fora do ar.
    """
    try:
        arquivo = capturar_tela()
        imagem = _imagem_base64(arquivo)

        mensagens = [
            {
                "role": "system",
                "content": (
                    "Você é o módulo de visão do ALFA. Analise a captura "
                    "de tela enviada e responda em português do Brasil. "
                    "Descreva o aplicativo aberto, o que aparece na tela "
                    "e elementos importantes. Não invente elementos que "
                    "não estejam na imagem."
                ),
            },
            {
                "role": "user",
                "content": "Analise minha tela.",
                "images": [imagem],
            },
        ]

        return _ollama_chat(mensagens, timeout=timeout)
    except Exception as erro:
        return f"Não consegui analisar a tela agora: {erro}"


def analisar_camera():
    try:
        arquivo = capturar_camera()
        if not arquivo:
            return "Não consegui acessar a câmera."

        imagem = _imagem_base64(arquivo)

        mensagens = [
            {
                "role": "system",
                "content": (
                    "Você é o módulo de visão do ALFA. Analise a imagem "
                    "da câmera e responda em português do Brasil. "
                    "Descreva o ambiente e objetos visíveis. Não atribua "
                    "identidade a pessoas."
                ),
            },
            {
                "role": "user",
                "content": "Analise esta imagem da câmera.",
                "images": [imagem],
            },
        ]

        return _ollama_chat(mensagens)
    except Exception as erro:
        return f"Não consegui analisar a câmera agora: {erro}"
