"""
Skill de Word — automação via COM (win32com.client), a interface real
que o Office expõe para controle programático. Mais robusto que
simular Ctrl+N/teclado: sabe se o documento existe de verdade, sabe
localizar/substituir texto sem depender de OCR, e sabe salvar.

Se o Word chamar Dispatch() e já houver uma instância aberta, o COM
conecta nela (não abre uma segunda) — por isso as funções não guardam
estado entre si, cada uma resolve a instância ativa na hora.
"""


def _obter_word(visivel=True):
    try:
        import win32com.client
    except ImportError as erro:
        return None, f"pywin32 não disponível: {erro}"

    try:
        app = win32com.client.Dispatch("Word.Application")
        app.Visible = visivel
        return app, None
    except Exception as erro:
        return None, "Não consegui abrir o Word — ele parece não estar instalado neste computador."


def abrir():
    app, erro = _obter_word()
    if erro:
        return False, erro
    return True, "Word aberto."


def novo_documento():
    app, erro = _obter_word()
    if erro:
        return False, erro
    try:
        app.Documents.Add()
        return True, "Documento novo criado."
    except Exception as erro:
        return False, f"Não consegui criar o documento: {erro}"


def escrever(texto):
    app, erro = _obter_word()
    if erro:
        return False, erro
    try:
        if app.Documents.Count == 0:
            app.Documents.Add()
        app.Selection.TypeText(texto)
        return True, "Texto escrito."
    except Exception as erro:
        return False, f"Não consegui escrever no documento: {erro}"


def localizar(texto):
    app, erro = _obter_word()
    if erro:
        return False, erro
    try:
        if app.Documents.Count == 0:
            return False, "Não há nenhum documento aberto."
        encontrado = bool(app.Selection.Find.Execute(FindText=texto))
        if encontrado:
            return True, f"Encontrei '{texto}'."
        return False, f"Não encontrei '{texto}' no documento."
    except Exception as erro:
        return False, f"Não consegui procurar: {erro}"


def substituir(de, para):
    app, erro = _obter_word()
    if erro:
        return False, erro
    try:
        if app.Documents.Count == 0:
            return False, "Não há nenhum documento aberto."
        WD_REPLACE_ALL = 2
        substituido = bool(
            app.ActiveDocument.Content.Find.Execute(
                FindText=de, ReplaceWith=para, Replace=WD_REPLACE_ALL
            )
        )
        if substituido:
            return True, f"Troquei '{de}' por '{para}'."
        return False, f"Não encontrei '{de}' para trocar."
    except Exception as erro:
        return False, f"Não consegui substituir: {erro}"


def salvar(caminho=None):
    app, erro = _obter_word()
    if erro:
        return False, erro
    try:
        if app.Documents.Count == 0:
            return False, "Não há nenhum documento aberto para salvar."
        doc = app.ActiveDocument
        if caminho:
            doc.SaveAs2(caminho)
            return True, caminho
        doc.Save()
        return True, doc.FullName
    except Exception as erro:
        return False, f"Não consegui salvar: {erro}"


def documento_tem_texto(texto):
    """Verificação (ver agente/verificador.py): True/False/None — nunca
    inventa. None quando o próprio Word/documento não está acessível."""
    app, erro = _obter_word()
    if erro or app.Documents.Count == 0:
        return None
    try:
        return bool(app.Selection.Find.Execute(FindText=texto))
    except Exception:
        return None
