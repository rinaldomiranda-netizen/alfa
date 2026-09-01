"""
Ferramentas genéricas de arquivo do agente. Nenhuma exclusão é
implementada (não foi pedida) — todas as operações aqui são criar,
copiar, mover, renomear e listar, sempre recusando SOBRESCREVER um
destino existente em vez de silenciosamente substituir algo do
usuário. Reaproveita PASTAS_CONHECIDAS de computer/executor.py (já
baseado em os.path.expanduser — nunca um caminho de usuário fixo).
"""

import os
import shutil

from computer.executor import PASTAS_CONHECIDAS


def localizar_arquivo(nome):
    """Procura `nome` (substring, sem diferenciar maiúsculas) nas
    pastas padrão do usuário ATUAL do sistema operacional."""
    nome_norm = (nome or "").strip().lower()
    if not nome_norm:
        return False, "Não entendi qual arquivo procurar."

    for base in PASTAS_CONHECIDAS.values():
        if not os.path.isdir(base):
            continue
        try:
            itens = os.listdir(base)
        except OSError:
            continue
        for item in itens:
            if nome_norm in item.lower():
                return True, os.path.join(base, item)

    return False, f"Não encontrei nenhum arquivo com '{nome}' nas pastas conhecidas."


def criar_pasta(caminho):
    if not caminho:
        return False, "Não entendi o nome da pasta."
    try:
        os.makedirs(caminho, exist_ok=True)
        return True, caminho
    except Exception as erro:
        return False, f"Não consegui criar a pasta: {erro}"


def listar_arquivos(pasta):
    """Lista o conteúdo de uma pasta (nomes de arquivo, sem recursão)."""
    nome_pasta = PASTAS_CONHECIDAS.get((pasta or "").strip().lower(), pasta)
    if not nome_pasta or not os.path.isdir(nome_pasta):
        return False, f"'{pasta}' não é uma pasta que eu conheça neste computador."
    try:
        itens = sorted(os.listdir(nome_pasta))
        return True, itens
    except OSError as erro:
        return False, f"Não consegui listar '{pasta}': {erro}"


def criar_arquivo(caminho, conteudo=""):
    """Cria um arquivo de texto NOVO — recusa sobrescrever um já
    existente (quem quiser substituir precisa pedir explicitamente,
    isso fica para uma ferramenta futura com confirmação)."""
    if not caminho:
        return False, "Não entendi o nome do arquivo."
    if os.path.exists(caminho):
        return False, f"Já existe um arquivo em '{caminho}' — não vou sobrescrever."
    try:
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo or "")
        return True, caminho
    except Exception as erro:
        return False, f"Não consegui criar o arquivo: {erro}"


def copiar_arquivo(origem, destino):
    if not origem or not destino:
        return False, "Preciso da origem e do destino."
    if not os.path.exists(origem):
        return False, f"'{origem}' não existe."
    if os.path.exists(destino):
        return False, f"Já existe algo em '{destino}' — não vou sobrescrever."
    try:
        shutil.copy2(origem, destino)
        return True, destino
    except Exception as erro:
        return False, f"Não consegui copiar: {erro}"


def mover_arquivo(origem, destino):
    if not origem or not destino:
        return False, "Preciso da origem e do destino."
    if not os.path.exists(origem):
        return False, f"'{origem}' não existe."
    if os.path.exists(destino):
        return False, f"Já existe algo em '{destino}' — não vou sobrescrever."
    try:
        shutil.move(origem, destino)
        return True, destino
    except Exception as erro:
        return False, f"Não consegui mover: {erro}"


def renomear_arquivo(caminho_atual, novo_nome):
    """Renomeia dentro da MESMA pasta — nunca move para outro lugar
    (isso fica para a ferramenta 'mover', ainda não implementada)."""
    if not caminho_atual or not novo_nome:
        return False, "Preciso do caminho atual e do novo nome."
    if not os.path.exists(caminho_atual):
        return False, f"'{caminho_atual}' não existe."

    destino = os.path.join(os.path.dirname(caminho_atual), novo_nome)
    if os.path.exists(destino):
        return False, f"Já existe um arquivo chamado '{novo_nome}' nessa pasta."

    try:
        os.rename(caminho_atual, destino)
        return True, destino
    except Exception as erro:
        return False, f"Não consegui renomear: {erro}"
