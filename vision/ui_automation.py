"""
Automação orientada a ELEMENTOS via Windows UI Automation (pywinauto).

Preferida sobre coordenadas fixas de tela ("x=500, y=300") e sobre
OCR sempre que o app em primeiro plano expõe sua árvore de
acessibilidade — o caso da maioria dos aplicativos nativos do
Windows (Win32, UWP, WinUI, e a maioria dos navegadores/apps
Electron mais recentes). Quando o app não expõe nada, quem chama
(computer/form_filler.py) recorre a vision/screen_vision.py (OCR).

Buscar por NOME em vez de coordenadas é o que torna a automação
resistente a mudanças de tamanho/posição de janela.
"""

from difflib import SequenceMatcher

from pywinauto import Desktop


def janela_ativa():
    """Retorna o wrapper pywinauto da janela em primeiro plano, ou None."""
    try:
        return Desktop(backend="uia").window(active_only=True, top_level_only=True)
    except Exception:
        return None


def listar_elementos(janela=None, tipo_controle=None):
    """
    Lista os elementos visíveis da janela ativa (ou de `janela`),
    opcionalmente filtrando por tipo de controle (ex.: "Edit",
    "Button", "CheckBox", "ComboBox").
    """
    alvo = janela or janela_ativa()
    if alvo is None:
        return []

    try:
        descendentes = (
            alvo.descendants(control_type=tipo_controle)
            if tipo_controle
            else alvo.descendants()
        )
    except Exception:
        return []

    elementos = []
    for elemento in descendentes:
        try:
            if not elemento.is_visible():
                continue
            rect = elemento.rectangle()
            elementos.append({
                "wrapper": elemento,
                "nome": (elemento.window_text() or "").strip(),
                "tipo": elemento.friendly_class_name(),
                "x": (rect.left + rect.right) // 2,
                "y": (rect.top + rect.bottom) // 2,
            })
        except Exception:
            continue

    return elementos


def encontrar_por_id(automation_id, tipo_controle=None, janela=None):
    """
    Procura um elemento pelo AutomationId real (no Chromium/Edge, o
    próprio atributo `id` do HTML) — mais robusto que casar pelo
    texto visível, quando o id do campo é conhecido de antemão (ver
    core/roteiro_pesquisa.py, que usa os ids reais lidos do código-
    fonte da pesquisa a ser preenchida).
    """
    if not automation_id:
        return None

    alvo = janela or janela_ativa()
    if alvo is None:
        return None

    try:
        descendentes = (
            alvo.descendants(control_type=tipo_controle)
            if tipo_controle
            else alvo.descendants()
        )
    except Exception:
        return None

    for elemento in descendentes:
        try:
            if not elemento.is_visible():
                continue
            if elemento.automation_id() != automation_id:
                continue
            rect = elemento.rectangle()
            return {
                "wrapper": elemento,
                "nome": (elemento.window_text() or "").strip(),
                "tipo": elemento.friendly_class_name(),
                "x": (rect.left + rect.right) // 2,
                "y": (rect.top + rect.bottom) // 2,
            }
        except Exception:
            continue

    return None


def _similaridade(a, b):
    return SequenceMatcher(None, a, b).ratio()


def encontrar_elemento(nome_procurado, tipo_controle=None, janela=None):
    """
    Procura um elemento pelo nome/rótulo visível: primeiro
    correspondência exata, depois substring, depois por similaridade
    (tolera pequenas variações de como a fala foi transcrita).

    Retorna o dict do elemento (ver listar_elementos) ou None.
    """
    alvo = nome_procurado.strip().lower()
    if not alvo:
        return None

    elementos = listar_elementos(janela, tipo_controle)

    for el in elementos:
        if el["nome"].strip().lower() == alvo:
            return el

    for el in elementos:
        if alvo in el["nome"].strip().lower():
            return el

    melhor, melhor_score = None, 0.0
    for el in elementos:
        nome_el = el["nome"].strip().lower()
        if not nome_el:
            continue
        score = _similaridade(alvo, nome_el)
        if score > melhor_score:
            melhor, melhor_score = el, score

    return melhor if melhor_score >= 0.6 else None


def clicar_elemento(elemento):
    try:
        elemento["wrapper"].click_input()
        return True
    except Exception:
        return False


def digitar_no_elemento(elemento, texto):
    try:
        elemento["wrapper"].click_input()
        elemento["wrapper"].type_keys(texto, with_spaces=True, with_tabs=False)
        return True
    except Exception:
        return False


def marcar_checkbox(elemento, marcar=True):
    try:
        wrapper = elemento["wrapper"]

        if hasattr(wrapper, "get_toggle_state"):
            estado_atual = wrapper.get_toggle_state()
            quer_marcado = 1 if marcar else 0
            if estado_atual != quer_marcado:
                wrapper.click_input()
        else:
            wrapper.click_input()

        return True
    except Exception:
        return False


def selecionar_opcao_combobox(elemento, texto_opcao):
    try:
        elemento["wrapper"].select(texto_opcao)
        return True
    except Exception:
        return False


def esta_marcado(elemento):
    """
    Lê o estado atual de marcação de um checkbox/radio button (True
    marcado, False desmarcado), ou None se não for possível
    determinar (ex.: o elemento não suporta nenhum dos padrões de
    seleção conhecidos). Usado para VERIFICAR de verdade que marcar
    uma caixa/selecionar um radio realmente teve efeito.
    """
    try:
        wrapper = elemento["wrapper"]
    except Exception:
        return None

    try:
        if hasattr(wrapper, "get_toggle_state"):
            return wrapper.get_toggle_state() == 1
    except Exception:
        pass

    try:
        if hasattr(wrapper, "is_selected"):
            return bool(wrapper.is_selected())
    except Exception:
        pass

    try:
        if hasattr(wrapper, "is_checked"):
            return bool(wrapper.is_checked())
    except Exception:
        pass

    return None


def obter_opcoes(elemento):
    """
    Lista as opções REAIS de um combobox/lista (ex.: as <option> de um
    <select> HTML) lidas ao vivo da tela — nunca uma lista fixa
    imaginada de antemão. Usado para a BETA perguntar "as opções são
    X, Y ou Z?" com o conteúdo verdadeiro atual da tela.
    """
    try:
        wrapper = elemento["wrapper"]
    except Exception:
        return []

    try:
        if hasattr(wrapper, "texts"):
            textos = wrapper.texts()
            return [t.strip() for t in textos if t and t.strip()]
    except Exception:
        pass

    try:
        if hasattr(wrapper, "item_texts"):
            return [t.strip() for t in wrapper.item_texts() if t and t.strip()]
    except Exception:
        pass

    return []


def ler_valor(elemento):
    """
    Lê o valor ATUAL de um campo (ex.: um <input> depois de digitado)
    para verificação pós-preenchimento — nunca assume que a digitação
    funcionou só porque nenhuma exceção foi levantada.
    """
    try:
        wrapper = elemento["wrapper"]
    except Exception:
        return None

    try:
        if hasattr(wrapper, "get_value"):
            valor = wrapper.get_value()
            if valor:
                return valor
    except Exception:
        pass

    try:
        return wrapper.window_text()
    except Exception:
        return None
