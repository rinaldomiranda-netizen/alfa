"""
Camada de verificação do agente.

Cada função aqui responde True (confirmado), False (confirmado que
NÃO aconteceu) ou None (não foi possível verificar de verdade neste
computador/situação) — nunca inventa sucesso. Reaproveita componentes
locais já existentes (core/pesquisa_app.py, vision/screen_vision.py)
em vez de duplicar lógica de janelas ou OCR.
"""

import time

from core import pesquisa_app
from core.normalizer import normalize
from vision import screen_vision


def verificar_janela_aberta(palavras_chave, timeout_segundos=8, intervalo=0.5):
    """
    Espera até `timeout_segundos` por uma janela cujo título contenha
    alguma das palavras-chave. core/pesquisa_app.py já é genérico (só
    era usado até agora para a tela de pesquisa) — reaproveitado aqui
    sem alterar uma linha dele.
    """
    fim = time.monotonic() + timeout_segundos
    while True:
        if pesquisa_app.encontrar_janela_pesquisa(palavras_chave):
            return True
        if time.monotonic() >= fim:
            return False
        time.sleep(intervalo)


def verificar_texto_na_tela(fragmento, tentativas=3, intervalo=0.7):
    """
    Confere, via OCR local (vision/screen_vision.py — motor nativo do
    Windows, offline), se um trecho do texto esperado apareceu na
    tela. Se o OCR não estiver disponível neste Windows, retorna None
    (não verificável) em vez de fingir que verificou.
    """
    if not screen_vision.ocr_disponivel():
        return None

    alvo = normalize(fragmento or "")[:40]
    if not alvo:
        return None

    for tentativa in range(tentativas):
        try:
            texto_tela = normalize(screen_vision.texto_da_tela_como_string())
        except Exception:
            return None

        if alvo in texto_tela:
            return True

        if tentativa < tentativas - 1:
            time.sleep(intervalo)

    return False


def verificar_arquivo_existe(caminho):
    if not caminho:
        return False
    import os
    return os.path.exists(caminho)


def verificar_elemento(nome_elemento, janela=None):
    """
    Relê um elemento de UI Automation (vision/ui_automation.py). None
    se não conseguir sequer localizar o elemento — não confunde
    "elemento sumiu" com "não consegui checar".
    """
    from vision import ui_automation

    try:
        elemento = ui_automation.encontrar_elemento(nome_elemento, janela=janela)
    except Exception:
        return None
    if elemento is None:
        return None
    try:
        return ui_automation.ler_valor(elemento)
    except Exception:
        return None
