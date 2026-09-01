"""
Leitura estruturada da tela — hierarquia de percepção (ver relatório
de auditoria arquitetural): UI Automation primeiro (rápido, exato,
sem custo de IA), OCR como reforço só quando a árvore de acessibilidade
não trouxe nada útil. Nunca inventa elemento: o que não está
disponível fica ausente (None), nunca adivinhado.

Usado por:
  - a ferramenta "ler_tela" (ver agente/registro_padrao.py);
  - "encontrar_na_tela" (busca semântica, com OCR como plano B);
  - "rolar_para_elemento" (rola até achar ou esgotar o limite).
"""

from vision import screen_vision, ui_automation

LIMITE_ROLAGENS_SEGURO = 6


def padronizar_resultado(
    texto=None, nome=None, tipo=None, valor=None, posicao=None,
    identificador=None, aplicativo=None, janela=None, ferramenta=None,
):
    """
    Estrutura ÚNICA e comum de "elemento real encontrado" — usada por
    QUALQUER caminho de busca (este módulo, computer/form_filler.py,
    skills/excel) para alimentar o mesmo contexto do agente (ver
    agente/contexto.py). Campos ausentes ficam None; nada aqui é
    inventado — quem chama só preenche o que realmente sabe.
    """
    return {
        "texto": texto,
        "nome": nome,
        "tipo": tipo,
        "valor": valor,
        "posicao": posicao,
        "identificador": identificador,
        "aplicativo": aplicativo,
        "janela": janela,
        "ferramenta": ferramenta,
    }


def _detalhar_elemento(el):
    """A partir do dict básico de vision/ui_automation.py (wrapper,
    nome, tipo, x, y), extrai os campos extra — cada um isolado em seu
    próprio try/except, para um controle que não suporta um atributo
    não derrubar os outros nem inventar um valor."""
    wrapper = el.get("wrapper") if isinstance(el, dict) else None
    detalhe = {
        "nome": (el or {}).get("nome") or None,
        "tipo": (el or {}).get("tipo") or None,
        "posicao": None,
        "tamanho": None,
        "automation_id": None,
        "habilitado": None,
        "estado": None,
        "valor": None,
    }
    if el and el.get("x") is not None:
        detalhe["posicao"] = (el["x"], el["y"])

    if wrapper is None:
        return detalhe

    try:
        detalhe["automation_id"] = wrapper.element_info.automation_id or None
    except Exception:
        pass
    try:
        detalhe["habilitado"] = bool(wrapper.is_enabled())
    except Exception:
        pass
    try:
        detalhe["estado"] = "visivel" if wrapper.is_visible() else "oculto"
    except Exception:
        pass
    try:
        rect = wrapper.rectangle()
        detalhe["posicao"] = (rect.left, rect.top)
        detalhe["tamanho"] = (rect.width(), rect.height())
    except Exception:
        pass

    marcado = ui_automation.esta_marcado(el)
    if marcado is not None:
        detalhe["valor"] = marcado
    else:
        try:
            valor = ui_automation.ler_valor(el)
            if valor:
                detalhe["valor"] = valor
        except Exception:
            pass

    return detalhe


def ler_tela_estruturada(tipo_controle=None, max_elementos=60):
    """
    Retorna:
    {
        "aplicativo": "..." | None,
        "janela": "..." | None,
        "elementos": [ {nome, tipo, posicao, tamanho, automation_id,
                         habilitado, estado, valor}, ... ],
        "fonte": "ui_automation" | "ocr" | None,
        "texto_ocr": "..." | None,
    }
    """
    resultado = {
        "aplicativo": None, "janela": None, "elementos": [],
        "fonte": None, "texto_ocr": None,
    }

    try:
        janela = ui_automation.janela_ativa()
    except Exception:
        janela = None

    if janela is not None:
        try:
            titulo = janela.window_text() or None
        except Exception:
            titulo = None
        resultado["janela"] = titulo
        resultado["aplicativo"] = titulo

        try:
            brutos = ui_automation.listar_elementos(janela=janela, tipo_controle=tipo_controle)
        except Exception:
            brutos = []

        resultado["elementos"] = [_detalhar_elemento(el) for el in brutos[:max_elementos]]
        if resultado["elementos"]:
            resultado["fonte"] = "ui_automation"

    # OCR só entra quando a UI Automation não trouxe elemento nenhum —
    # evita o custo de captura+OCR quando a acessibilidade já resolveu.
    if not resultado["elementos"] and screen_vision.ocr_disponivel():
        texto = screen_vision.texto_da_tela_como_string()
        if texto:
            resultado["texto_ocr"] = texto
            resultado["fonte"] = "ocr"

    return resultado


def resumo_legivel(estrutura):
    """Texto curto e natural — nunca despeja a estrutura crua numa
    resposta falada."""
    janela = estrutura.get("janela") or "a janela atual"
    if estrutura.get("elementos"):
        nomes = [e["nome"] for e in estrutura["elementos"] if e.get("nome")]
        if nomes:
            amostra = ", ".join(nomes[:6])
            sufixo = "..." if len(nomes) > 6 else ""
            return f"Em {janela}, vejo: {amostra}{sufixo}."
        return f"Estou vendo {janela}, mas sem elementos com nome reconhecível."
    if estrutura.get("texto_ocr"):
        return estrutura["texto_ocr"][:400]
    return "Não consegui identificar nada de útil na tela agora."


def encontrar_na_tela(alvo, tipo_controle=None):
    """
    Busca semântica: UI Automation primeiro (exata), OCR como plano B
    (aproximada, com posição real de clique). Nunca coordenada
    inventada — se não achar em nenhum dos dois, `encontrado=False`.
    """
    if not alvo or not alvo.strip():
        return {"encontrado": False, "elemento": None, "posicao": None, "fonte": None, "confianca": 0.0}

    try:
        el = ui_automation.encontrar_elemento(alvo, tipo_controle=tipo_controle)
    except Exception:
        el = None

    if el is not None:
        return {
            "encontrado": True,
            "elemento": _detalhar_elemento(el),
            "posicao": (el.get("x"), el.get("y")),
            "fonte": "ui_automation",
            "confianca": 1.0,
        }

    if screen_vision.ocr_disponivel():
        try:
            linha = screen_vision.localizar_texto(alvo)
        except Exception:
            linha = None
        if linha:
            return {
                "encontrado": True,
                "elemento": {"nome": linha["texto"], "tipo": "texto_ocr"},
                "posicao": (linha["x"], linha["y"]),
                "fonte": "ocr",
                "confianca": 0.7,
            }

    return {"encontrado": False, "elemento": None, "posicao": None, "fonte": None, "confianca": 0.0}


def rolar_para_elemento(alvo, executor, direcao="baixo", tipo_controle=None, limite=LIMITE_ROLAGENS_SEGURO):
    """
    Lê a tela -> procura `alvo` -> se não achou, rola -> lê de novo ->
    procura de novo -> repete até achar ou esgotar `limite` (nunca
    ilimitado). `executor` é a MESMA instância de computer/executor.py
    já usada pelo resto do agente (reaproveitada, não recriada).
    """
    for tentativa in range(limite + 1):
        resultado = encontrar_na_tela(alvo, tipo_controle=tipo_controle)
        if resultado["encontrado"]:
            resultado["rolagens_necessarias"] = tentativa
            return resultado
        if tentativa == limite:
            break
        try:
            executor.scroll(direcao)
        except Exception:
            break

    return {
        "encontrado": False, "elemento": None, "posicao": None,
        "fonte": None, "confianca": 0.0, "rolagens_necessarias": limite,
    }
