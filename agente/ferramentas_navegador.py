"""
Controle genérico de navegador — sem Selenium/Playwright (nenhuma
dependência nova): trata o navegador como qualquer outra janela do
Windows, usando os mesmos atalhos universais que funcionam em
Chrome/Edge/Firefox, mais OCR local para "ler a página". Mais leve e
100% offline, ao custo de não enxergar o DOM (não sabe clicar num link
específico pelo texto, por exemplo — isso ficaria para uma versão
futura com Playwright, caso vire prioridade).
"""

import time

from agente import descoberta_apps
from vision import screen_vision

# Cada função recebe o `executor` já compartilhado (mesma instância de
# computer/executor.py criada por core/alfa_core.py) em vez de criar
# um novo — ver agente/registro_padrao.py, que faz o binding.


def abrir(executor, url=None):
    sucesso, mensagem = descoberta_apps.abrir_aplicativo("navegador")
    if not sucesso:
        return False, mensagem

    if url:
        time.sleep(1.5)  # dar tempo do navegador abrir antes de digitar a URL
        executor.atalho(("ctrl", "l"))  # foco na barra de endereço (padrão universal)
        executor.digitar(url)
        executor.enter()
        return True, f"Abrindo {url} no navegador."

    return True, "Navegador aberto."


def pesquisar(executor, termo):
    if not termo:
        return False, "Não entendi o que pesquisar."
    executor.atalho(("ctrl", "l"))
    executor.digitar(termo)
    executor.enter()
    return True, f"Pesquisando '{termo}'."


def voltar(executor):
    executor.atalho(("alt", "left"))
    return True, "Voltando."


def avancar(executor):
    executor.atalho(("alt", "right"))
    return True, "Avançando."


def fechar_aba(executor):
    executor.atalho(("ctrl", "w"))
    return True, "Aba fechada."


def ler_pagina():
    """OCR local da janela atual — não lê o DOM, só o que está
    visivelmente na tela (ver vision/screen_vision.py)."""
    texto = screen_vision.texto_da_tela_como_string()
    if not texto:
        return False, "Não consegui ler texto nesta página."
    return True, texto
