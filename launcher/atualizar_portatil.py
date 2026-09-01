"""
Atualizador da BETA PORTÁTIL — FASE H da expansão de plataforma (item
20 do pedido: "criar mecanismo seguro de atualização").

Fluxo real, executado só localmente (nenhum servidor embutido aqui):

    verifica versão instalada (core/version.py)
    -> procura um pacote de atualização em `origem` (uma pasta local —
       pendrive, pasta baixada por outro meio; NUNCA um download
       automático daqui: sem internet obrigatória, ver item 24)
    -> lê o manifesto do pacote (versao + compatibilidade mínima)
    -> verifica integridade por hash SHA-256 (nunca instala um pacote
       sem o .sha256 batendo)
    -> faz backup COMPLETO da distribuição atual antes de tocar nela
    -> aplica a atualização (copia os arquivos por cima)
    -> verifica que os módulos principais ainda compilam
    -> em caso de falha, restaura o backup automaticamente (rollback)

Sem `origem` configurada ou sem internet, a BETA PORTÁTIL continua
funcionando normalmente com a versão já instalada — atualizar nunca é
obrigatório para o uso do dia a dia.
"""

import hashlib
import json
import os
import py_compile
import shutil
import time

from core.version import compativel

NOME_MANIFESTO = "manifest_atualizacao.json"
NOME_HASH = "pacote.sha256"

# Arquivos cuja compilação é checada após aplicar a atualização — se
# algum deles não compilar, a atualização é revertida (item 20: "não
# atualizar silenciosamente arquivos críticos sem verificação").
ARQUIVOS_VERIFICACAO = [
    os.path.join("launcher", "iniciar_portatil.py"),
    os.path.join("core", "alfa_core.py"),
]


class AtualizacaoIndisponivel(Exception):
    pass


class FalhaIntegridade(Exception):
    pass


def _hash_pasta(pasta):
    """SHA-256 determinístico do conteúdo de uma pasta (nome + bytes
    de cada arquivo, em ordem estável) — usado para conferir
    integridade sem depender de um único arquivo .zip.

    NUNCA inclui o próprio manifesto nem o arquivo de hash no cálculo
    — senão o hash mudaria só por gravar o .sha256 ao lado do pacote
    (problema do "ovo e a galinha": o hash precisa ser calculado ANTES
    de existir o arquivo que vai guardá-lo, e continuar batendo depois)."""
    hasher = hashlib.sha256()
    for raiz, _dirs, arquivos in os.walk(pasta):
        for nome in sorted(arquivos):
            if raiz == pasta and nome in (NOME_MANIFESTO, NOME_HASH):
                continue
            caminho = os.path.join(raiz, nome)
            relativo = os.path.relpath(caminho, pasta)
            hasher.update(relativo.replace("\\", "/").encode("utf-8"))
            with open(caminho, "rb") as arquivo:
                hasher.update(arquivo.read())
    return hasher.hexdigest()


NOME_ARQUIVO_VERSAO = "VERSAO_INSTALADA.txt"


def versao_instalada(pasta_instalada):
    """
    Lê a versão REAL gravada na distribuição alvo (nunca a versão
    estática de core/version.py do código que está rodando o
    atualizador — podem ser distribuições diferentes). Sem o arquivo
    (instalação anterior a este atualizador), assume "0.0.0": qualquer
    pacote real conta como mais novo.
    """
    caminho = os.path.join(pasta_instalada, NOME_ARQUIVO_VERSAO)
    if not os.path.isfile(caminho):
        return "0.0.0"
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return arquivo.read().strip() or "0.0.0"


def _gravar_versao_instalada(pasta_instalada, versao):
    with open(os.path.join(pasta_instalada, NOME_ARQUIVO_VERSAO), "w", encoding="utf-8") as arquivo:
        arquivo.write(versao)


def verificar_atualizacao_disponivel(origem, pasta_instalada):
    """
    Lê `origem/manifest_atualizacao.json`. Retorna o manifesto (dict)
    se houver uma versão mais nova (que a REALMENTE instalada em
    `pasta_instalada`, ver versao_instalada) E compatível; levanta
    AtualizacaoIndisponivel caso contrário (sem pacote, versão igual/
    mais velha, ou incompatível) — nunca finge que há atualização.
    """
    caminho_manifesto = os.path.join(origem, NOME_MANIFESTO)
    if not os.path.isfile(caminho_manifesto):
        raise AtualizacaoIndisponivel(f"Nenhum pacote de atualização encontrado em '{origem}'.")

    with open(caminho_manifesto, "r", encoding="utf-8") as arquivo:
        manifesto = json.load(arquivo)

    versao_nova = manifesto.get("versao")
    if not versao_nova:
        raise AtualizacaoIndisponivel("Manifesto de atualização sem campo 'versao'.")

    versao_atual = versao_instalada(pasta_instalada)
    if tuple(map(int, versao_nova.split("."))) <= tuple(map(int, versao_atual.split("."))):
        raise AtualizacaoIndisponivel(
            f"Pacote encontrado (versão {versao_nova}) não é mais novo que o instalado ({versao_atual})."
        )

    exigencias = manifesto.get("compativel_minimo", {})
    for componente, minimo in exigencias.items():
        if not compativel(componente, minimo):
            raise AtualizacaoIndisponivel(
                f"Pacote exige {componente} >= {minimo}, incompatível com esta instalação."
            )

    return manifesto


def verificar_integridade(origem):
    """Confere o hash real do pacote contra origem/pacote.sha256.
    Levanta FalhaIntegridade se o arquivo de hash não existir ou não
    bater — nunca instala um pacote sem essa checagem."""
    caminho_hash = os.path.join(origem, NOME_HASH)
    if not os.path.isfile(caminho_hash):
        raise FalhaIntegridade(f"Pacote em '{origem}' não tem arquivo de assinatura ({NOME_HASH}).")

    with open(caminho_hash, "r", encoding="utf-8") as arquivo:
        hash_esperado = arquivo.read().strip()

    hash_real = _hash_pasta(origem)
    if hash_real != hash_esperado:
        raise FalhaIntegridade("Hash do pacote não confere — atualização não será aplicada.")

    return True


def fazer_backup(pasta_instalada, pasta_backups):
    os.makedirs(pasta_backups, exist_ok=True)
    # Sufixo numérico evita colisão se duas atualizações acontecerem
    # no mesmo segundo (ex.: testes automatizados em sequência rápida).
    base = f"backup_{time.strftime('%Y%m%d_%H%M%S')}"
    nome_backup = base
    contador = 1
    while os.path.exists(os.path.join(pasta_backups, nome_backup)):
        contador += 1
        nome_backup = f"{base}_{contador}"
    caminho_backup = os.path.join(pasta_backups, nome_backup)
    shutil.copytree(pasta_instalada, caminho_backup)
    return caminho_backup


def _copiar_pacote(origem, destino):
    for item in os.listdir(origem):
        if item in (NOME_MANIFESTO, NOME_HASH):
            continue
        caminho_origem = os.path.join(origem, item)
        caminho_destino = os.path.join(destino, item)
        if os.path.isdir(caminho_origem):
            if os.path.isdir(caminho_destino):
                shutil.rmtree(caminho_destino)
            shutil.copytree(caminho_origem, caminho_destino)
        else:
            shutil.copy2(caminho_origem, caminho_destino)


def verificar_inicializacao(pasta_instalada):
    """Compila (sem executar) os arquivos mais críticos — se algum
    tiver erro de sintaxe após a atualização, é motivo de rollback
    imediato."""
    for relativo in ARQUIVOS_VERIFICACAO:
        caminho = os.path.join(pasta_instalada, relativo)
        if not os.path.isfile(caminho):
            return False, f"Arquivo esperado ausente após atualização: {relativo}"
        try:
            py_compile.compile(caminho, doraise=True)
        except py_compile.PyCompileError as erro:
            return False, f"Falha ao compilar {relativo}: {erro}"
    return True, "Verificação pós-atualização OK."


def rollback(caminho_backup, pasta_instalada):
    if os.path.isdir(pasta_instalada):
        shutil.rmtree(pasta_instalada)
    shutil.copytree(caminho_backup, pasta_instalada)


def atualizar(origem, pasta_instalada, pasta_backups=None):
    """
    Executa o fluxo completo. Retorna um dict de relatório — nunca
    levanta exceção para fora (todo erro esperado vira
    {"sucesso": False, "etapa": ..., "mensagem": ...}).
    """
    pasta_backups = pasta_backups or os.path.join(os.path.dirname(pasta_instalada), "backups_atualizacao")

    try:
        manifesto = verificar_atualizacao_disponivel(origem, pasta_instalada)
    except AtualizacaoIndisponivel as erro:
        return {"sucesso": False, "etapa": "verificar_versao", "mensagem": str(erro)}

    try:
        verificar_integridade(origem)
    except FalhaIntegridade as erro:
        return {"sucesso": False, "etapa": "verificar_integridade", "mensagem": str(erro)}

    try:
        caminho_backup = fazer_backup(pasta_instalada, pasta_backups)
    except Exception as erro:
        return {"sucesso": False, "etapa": "backup", "mensagem": f"Falha ao fazer backup: {erro}"}

    try:
        _copiar_pacote(origem, pasta_instalada)
    except Exception as erro:
        rollback(caminho_backup, pasta_instalada)
        return {"sucesso": False, "etapa": "aplicar", "mensagem": f"Falha ao copiar pacote, revertido: {erro}"}

    ok, mensagem_verificacao = verificar_inicializacao(pasta_instalada)
    if not ok:
        rollback(caminho_backup, pasta_instalada)
        return {
            "sucesso": False, "etapa": "verificar_inicializacao",
            "mensagem": f"{mensagem_verificacao} — revertido para a versão anterior.",
        }

    _gravar_versao_instalada(pasta_instalada, manifesto["versao"])

    return {
        "sucesso": True,
        "etapa": "concluido",
        "mensagem": f"Atualizado para a versão {manifesto['versao']}.",
        "backup": caminho_backup,
    }
