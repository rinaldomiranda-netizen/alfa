"""
Normalização central de texto transcrito por voz.

Fluxo: texto bruto do reconhecimento -> minúsculas -> remoção de
acentos/pontuação -> colapso de espaços -> correções específicas de
domínio (erros conhecidos do reconhecimento de voz para comandos de
mouse).

As correções de domínio só disparam quando há um verbo de movimento
no contexto da frase, para não substituir palavras legítimas do
português (ex.: "maus" de "os maus", "ovo" de "fritar um ovo") fora
do contexto de comando.
"""

import re
import unicodedata

MOVEMENT_VERBS = [
    "mover", "mova", "move", "movam",
    "mexer", "mexa", "mexe", "mecho", "mexo",
    "leve", "levar", "leva",
    "desloque", "deslocar",
    "arraste", "arrastar",
    "suba", "subir", "sobe",
    "desca", "descer", "desce",
    "baixe", "baixar",
    "eleve", "elevar",
    "jogue", "jogar", "joga",
    "puxe", "puxar",
    "ovo",  # erro comum de STT para "mova"/"mover"
]

MOUSE_NOISE_WORDS = ["maus", "mause", "malwe", "malve", "mou", "mausi"]

# Palavra de ativação: "Beta, abra o navegador" deve ser interpretado
# como "abra o navegador" — só remove o nome quando ele é um VOCATIVO
# no início da frase (endereçando a assistente), nunca quando é o
# objeto da frase ("desligue a beta", "encerre a beta" continuam
# intactos, para o interpretador reconhecer o comando de sair).
# "alfa" também é aceito por compatibilidade com versões anteriores.
_PALAVRA_ATIVACAO = re.compile(r"^(?:beta|alfa)\s+(?=\S)")

# Padrões de correção contextual (aplicados antes da correção genérica).
# Preservam o verbo original quando ele já é uma palavra válida
# (ex.: "mexa"), e só normalizam o verbo quando ele também é ruído de
# reconhecimento (ex.: "ovo").
_DOMAIN_PATTERNS = [
    (re.compile(r"\bovo\s+a?o?\s*(?:maus|mause|malwe|malve|mou|mausi|mouse)\b"), "mover mouse"),
    (re.compile(r"\bmova\s+o\s+(?:maus|mause|malwe|malve|mou|mausi)\b"), "mover mouse"),
    (
        re.compile(
            r"\b(mexa|mexe|leve|arraste|desloque|jogue|puxe|coloque)\s+o\s+"
            r"(?:maus|mause|malwe|malve|mou|mausi)\b"
        ),
        r"\1 o mouse",
    ),
]

_WORD_BOUNDARY_CACHE = {}


def _boundary_pattern(word):
    pattern = _WORD_BOUNDARY_CACHE.get(word)
    if pattern is None:
        pattern = re.compile(rf"\b{re.escape(word)}\b")
        _WORD_BOUNDARY_CACHE[word] = pattern
    return pattern


def strip_accents(text):
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _has_movement_context(text):
    return any(_boundary_pattern(v).search(text) for v in MOVEMENT_VERBS)


def normalize(text):
    """Normaliza uma frase transcrita para uso pelo interpretador de comandos."""

    if not text:
        return ""

    text = text.lower().strip()
    text = strip_accents(text)

    # Remove pontuação, mantendo letras, números e espaços.
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Remove o vocativo de ativação ("Beta, ..." / "Beta ...") do
    # início da frase antes de qualquer outra interpretação.
    text = _PALAVRA_ATIVACAO.sub("", text, count=1)

    # Correções contextuais explícitas (ordem importa).
    for pattern, replacement in _DOMAIN_PATTERNS:
        text = pattern.sub(replacement, text)

    # Correção genérica: só troca ruído de "mouse" quando existe verbo
    # de movimento em algum lugar da frase, para não confundir "maus"
    # (mau, no plural) fora de contexto de comando.
    if _has_movement_context(text):
        for noisy in MOUSE_NOISE_WORDS:
            text = _boundary_pattern(noisy).sub("mouse", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text
