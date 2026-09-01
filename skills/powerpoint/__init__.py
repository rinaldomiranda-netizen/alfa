"""
Skill de PowerPoint — automação via COM. Suporte inicial: abrir, criar
apresentação, criar slide, definir título/conteúdo.
"""

PP_LAYOUT_TEXTO = 2  # ppLayoutText: título + corpo de texto


def _obter_powerpoint():
    try:
        import win32com.client
    except ImportError as erro:
        return None, f"pywin32 não disponível: {erro}"

    try:
        app = win32com.client.Dispatch("PowerPoint.Application")
        try:
            app.Visible = True  # PowerPoint exige Visible=True em várias versões
        except Exception:
            pass
        return app, None
    except Exception as erro:
        return None, "Não consegui abrir o PowerPoint — ele parece não estar instalado neste computador."


def abrir():
    app, erro = _obter_powerpoint()
    if erro:
        return False, erro
    return True, "PowerPoint aberto."


def criar_apresentacao():
    app, erro = _obter_powerpoint()
    if erro:
        return False, erro
    try:
        app.Presentations.Add()
        return True, "Apresentação criada."
    except Exception as erro:
        return False, f"Não consegui criar a apresentação: {erro}"


def novo_slide(layout=PP_LAYOUT_TEXTO):
    app, erro = _obter_powerpoint()
    if erro:
        return False, erro
    try:
        if app.Presentations.Count == 0:
            app.Presentations.Add()
        apresentacao = app.ActivePresentation
        indice = apresentacao.Slides.Count + 1
        apresentacao.Slides.Add(indice, layout)
        return True, f"Slide {indice} criado."
    except Exception as erro:
        return False, f"Não consegui criar o slide: {erro}"


def _slide_atual(app):
    apresentacao = app.ActivePresentation
    if apresentacao.Slides.Count == 0:
        return None
    return apresentacao.Slides(apresentacao.Slides.Count)


def definir_titulo(texto):
    app, erro = _obter_powerpoint()
    if erro:
        return False, erro
    try:
        slide = _slide_atual(app)
        if slide is None:
            return False, "Não há nenhum slide para receber o título."
        slide.Shapes.Title.TextFrame.TextRange.Text = texto
        return True, texto
    except Exception as erro:
        return False, f"Não consegui definir o título: {erro}"


def definir_conteudo(texto):
    app, erro = _obter_powerpoint()
    if erro:
        return False, erro
    try:
        slide = _slide_atual(app)
        if slide is None:
            return False, "Não há nenhum slide para receber o conteúdo."
        if slide.Shapes.Placeholders.Count < 2:
            return False, "Este slide não tem um espaço de conteúdo."
        slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = texto
        return True, texto
    except Exception as erro:
        return False, f"Não consegui definir o conteúdo: {erro}"


def salvar(caminho=None):
    app, erro = _obter_powerpoint()
    if erro:
        return False, erro
    try:
        if app.Presentations.Count == 0:
            return False, "Não há nenhuma apresentação aberta para salvar."
        apresentacao = app.ActivePresentation
        if caminho:
            apresentacao.SaveAs(caminho)
            return True, caminho
        apresentacao.Save()
        return True, apresentacao.FullName
    except Exception as erro:
        return False, f"Não consegui salvar: {erro}"


def slide_tem_titulo(texto):
    """Verificação (ver agente/verificador.py): True/False/None —
    nunca inventa. Relê o título do slide atual e compara."""
    app, erro = _obter_powerpoint()
    if erro:
        return None
    try:
        slide = _slide_atual(app)
        if slide is None:
            return None
        atual = slide.Shapes.Title.TextFrame.TextRange.Text
        return str(atual).strip() == str(texto).strip()
    except Exception:
        return None


def slide_tem_conteudo(texto):
    app, erro = _obter_powerpoint()
    if erro:
        return None
    try:
        slide = _slide_atual(app)
        if slide is None or slide.Shapes.Placeholders.Count < 2:
            return None
        atual = slide.Shapes.Placeholders(2).TextFrame.TextRange.Text
        return str(atual).strip() == str(texto).strip()
    except Exception:
        return None
