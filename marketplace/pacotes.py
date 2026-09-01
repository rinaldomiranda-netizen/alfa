"""
Marketplace de habilidades — FASE 4 da expansão de plataforma.

Local, hoje: um "pacote" é uma pasta com manifest.json + código (mesmo
formato de skills/<nome>/, ver agente/skill_registry.py) e,
opcionalmente, um arquivo de hash ao lado (pacote.sha256) para conferir
integridade antes de instalar. Preparado para, no futuro, um
marketplace ONLINE alimentar `instalar_pacote` com um pacote já
baixado por marketplace/cliente_distribuicao.py — hoje ninguém baixa
nada sozinho.

NUNCA executa nenhum arquivo .py de um pacote — instalar só copia
arquivos e valida o manifesto; ativar (ver agente/skill_registry.py)
só torna a skill visível/executável através do Tool Registry já
existente, que continua exigindo permissão normalmente. Uma skill
instalada nunca roda sozinha só por ter sido instalada.
"""

import json
import os
import shutil

from agente.skill_registry import ManifestoInvalido, SkillManifest
from core.version import compativel
from security.permissions import (
    CATEGORIA_ADMIN,
    CATEGORIA_BASIC,
    CATEGORIA_COMMERCIAL,
    CATEGORIA_FILES,
    CATEGORIA_PAYMENT,
    CATEGORIA_SENSITIVE,
    CATEGORIA_SYSTEM,
)

CATEGORIAS_VALIDAS = {
    CATEGORIA_BASIC, CATEGORIA_FILES, CATEGORIA_SYSTEM, CATEGORIA_SENSITIVE,
    CATEGORIA_COMMERCIAL, CATEGORIA_PAYMENT, CATEGORIA_ADMIN,
}

NOME_HASH = "pacote.sha256"


class PacoteInvalido(Exception):
    pass


def _hash_pasta(pasta):
    import hashlib

    hasher = hashlib.sha256()
    for raiz, _dirs, arquivos in os.walk(pasta):
        for nome in sorted(arquivos):
            if raiz == pasta and nome == NOME_HASH:
                continue
            caminho = os.path.join(raiz, nome)
            relativo = os.path.relpath(caminho, pasta)
            hasher.update(relativo.replace("\\", "/").encode("utf-8"))
            with open(caminho, "rb") as arquivo:
                hasher.update(arquivo.read())
    return hasher.hexdigest()


def listar_pacotes_locais(pasta_pacotes):
    """Lista subpastas de `pasta_pacotes` que têm um manifest.json —
    descoberta, não validação completa (ver validar_manifesto)."""
    if not os.path.isdir(pasta_pacotes):
        return []
    candidatos = []
    for nome in sorted(os.listdir(pasta_pacotes)):
        caminho = os.path.join(pasta_pacotes, nome)
        if os.path.isfile(os.path.join(caminho, "manifest.json")):
            candidatos.append(caminho)
    return candidatos


def validar_manifesto(caminho_pacote):
    caminho_manifesto = os.path.join(caminho_pacote, "manifest.json")
    if not os.path.isfile(caminho_manifesto):
        raise PacoteInvalido(f"Pacote sem manifest.json: {caminho_pacote}")
    with open(caminho_manifesto, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    try:
        return SkillManifest(dados, caminho_manifesto)
    except ManifestoInvalido as erro:
        raise PacoteInvalido(str(erro)) from erro


def verificar_permissoes(manifesto):
    """True se todas as permissões declaradas forem categorias
    conhecidas (ver security/permissions.py) — nunca instala um
    pacote pedindo uma categoria inventada."""
    desconhecidas = [p for p in manifesto.permissoes if p not in CATEGORIAS_VALIDAS]
    if desconhecidas:
        raise PacoteInvalido(f"Permissões desconhecidas no manifesto: {desconhecidas}")
    return True


def verificar_hash(caminho_pacote):
    """True/False se houver pacote.sha256; None se o pacote não tiver
    (hash é opcional para um pacote local feito à mão — ver
    instalar_pacote(exigir_hash=...) para tornar obrigatório)."""
    caminho_hash = os.path.join(caminho_pacote, NOME_HASH)
    if not os.path.isfile(caminho_hash):
        return None
    with open(caminho_hash, "r", encoding="utf-8") as arquivo:
        hash_esperado = arquivo.read().strip()
    return _hash_pasta(caminho_pacote) == hash_esperado


def verificar_compatibilidade(manifesto):
    compat = manifesto.compatibilidade if isinstance(manifesto.compatibilidade, dict) else {}
    minimo = compat.get("core_minimo")
    if minimo and not compativel("core", minimo):
        raise PacoteInvalido(f"Pacote exige core >= {minimo}, incompatível com esta instalação.")
    return True


def instalar_pacote(caminho_pacote, pasta_skills, exigir_hash=False):
    """
    Valida manifesto + permissões + compatibilidade (+ hash, se
    `exigir_hash=True`) e copia o pacote para dentro de `pasta_skills`.
    Retorna (sucesso, mensagem) — nunca levanta exceção para fora.
    """
    try:
        manifesto = validar_manifesto(caminho_pacote)
        verificar_permissoes(manifesto)
        verificar_compatibilidade(manifesto)

        if exigir_hash:
            resultado_hash = verificar_hash(caminho_pacote)
            if resultado_hash is not True:
                return False, "Pacote sem assinatura de integridade válida — instalação recusada."

        destino = os.path.join(pasta_skills, manifesto.nome)
        if os.path.isdir(destino):
            shutil.rmtree(destino)
        shutil.copytree(caminho_pacote, destino, ignore=shutil.ignore_patterns(NOME_HASH))

        return True, f"Pacote '{manifesto.nome}' (versão {manifesto.versao}) instalado."
    except PacoteInvalido as erro:
        return False, str(erro)
    except Exception as erro:
        return False, f"Falha ao instalar pacote: {erro}"


def remover_pacote(nome, pasta_skills):
    destino = os.path.join(pasta_skills, nome)
    if not os.path.isdir(destino):
        return False, f"Pacote '{nome}' não está instalado."
    try:
        shutil.rmtree(destino)
        return True, f"Pacote '{nome}' removido."
    except Exception as erro:
        return False, f"Falha ao remover '{nome}': {erro}"


def atualizar_pacote(caminho_pacote_novo, pasta_skills, exigir_hash=False):
    """
    Instala uma versão nova só se for de fato mais nova que a já
    instalada — reaproveita instalar_pacote depois da checagem de
    versão, para nunca "atualizar" para uma versão igual/mais antiga.
    """
    try:
        manifesto_novo = validar_manifesto(caminho_pacote_novo)
    except PacoteInvalido as erro:
        return False, str(erro)

    caminho_manifesto_atual = os.path.join(pasta_skills, manifesto_novo.nome, "manifest.json")
    if os.path.isfile(caminho_manifesto_atual):
        with open(caminho_manifesto_atual, "r", encoding="utf-8") as arquivo:
            versao_atual = json.load(arquivo).get("versao", "0.0.0")
        if tuple(map(int, manifesto_novo.versao.split("."))) <= tuple(map(int, versao_atual.split("."))):
            return False, f"Versão {manifesto_novo.versao} não é mais nova que a instalada ({versao_atual})."

    return instalar_pacote(caminho_pacote_novo, pasta_skills, exigir_hash=exigir_hash)
