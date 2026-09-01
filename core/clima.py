"""
Consulta de previsão do tempo — serviço gratuito e sem chave de API
(wttr.in, texto simples). Só é útil com internet disponível; se a
chamada falhar por qualquer motivo (sem internet, serviço fora do ar),
`consultar()` devolve None e quem chama informa isso claramente ao
usuário em vez de inventar uma previsão (ver core/router.py e
agente/registro_padrao.py — o mesmo código atende os dois).
"""

import urllib.parse
import urllib.request

# Formato de texto puro (sem emoji): %C é a condição por EXTENSO
# ("Sunny", "Partly cloudy"...), não o ícone — evita o mesmo tipo de
# UnicodeEncodeError já visto neste projeto em consoles Windows com
# codepage legada (cp1252) ao tentar imprimir/falar um emoji.
URL_BASE = "http://wttr.in/{local}?format=%l:+%C+%t&lang=pt"
TIMEOUT_SEGUNDOS = 5


def consultar(local=""):
    try:
        url = URL_BASE.format(local=urllib.parse.quote((local or "").strip()))
        with urllib.request.urlopen(url, timeout=TIMEOUT_SEGUNDOS) as resposta:
            texto = resposta.read().decode("utf-8", errors="ignore").strip()
        if not texto or "unknown location" in texto.lower():
            return None
        # Defesa extra: remove qualquer caractere fora do texto comum
        # (emoji residual, símbolo exótico) que ainda tenha passado.
        texto = texto.encode("cp1252", errors="ignore").decode("cp1252")
        return texto or None
    except Exception:
        return None
