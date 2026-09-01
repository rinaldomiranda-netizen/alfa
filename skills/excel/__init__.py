"""
Skill de Excel — automação via COM. Endereça células por referência
("B3"), nunca por coordenada de tela: continua funcionando não importa
o tamanho da janela, o zoom ou a resolução.
"""


def _obter_excel(visivel=True):
    try:
        import win32com.client
    except ImportError as erro:
        return None, f"pywin32 não disponível: {erro}"

    try:
        app = win32com.client.Dispatch("Excel.Application")
        app.Visible = visivel
        return app, None
    except Exception as erro:
        return None, "Não consegui abrir o Excel — ele parece não estar instalado neste computador."


def abrir():
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            app.Workbooks.Add()
        return True, "Excel aberto."
    except Exception as erro:
        return False, f"Não consegui preparar a planilha: {erro}"


def localizar_valor(valor):
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta."
        planilha = app.ActiveSheet
        celula = planilha.Cells.Find(str(valor))
        if celula is None:
            return False, f"Não encontrei '{valor}' na planilha."
        celula.Select()
        endereco = celula.Address(False, False)
        return True, f"Encontrei na célula {endereco}.", {"endereco": endereco}
    except Exception as erro:
        return False, f"Não consegui procurar: {erro}"


def localizar_todos(valor, limite=20):
    """
    Enumera TODAS as células com `valor` (até `limite`, nunca
    ilimitado) — usado para o contexto de múltiplos resultados (ver
    agente/contexto.py). Não seleciona nada sozinho; quem chama decide
    o que fazer com a lista.
    """
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta."

        planilha = app.ActiveSheet
        primeira = planilha.Cells.Find(str(valor))
        if primeira is None:
            return False, f"Não encontrei '{valor}' na planilha."

        encontrados = [primeira.Address(False, False)]
        atual = primeira
        while len(encontrados) < limite:
            proxima = planilha.Cells.FindNext(atual)
            endereco_proxima = proxima.Address(False, False) if proxima else None
            if not endereco_proxima or endereco_proxima == encontrados[0]:
                break
            encontrados.append(endereco_proxima)
            atual = proxima

        resultados = [{"texto": str(valor), "endereco": endereco} for endereco in encontrados]
        if len(resultados) == 1:
            planilha.Range(resultados[0]["endereco"]).Select()
            return True, f"Encontrei na célula {resultados[0]['endereco']}.", {"resultados": resultados}
        return True, f"Encontrei {len(resultados)} ocorrências de '{valor}'.", {"resultados": resultados}
    except Exception as erro:
        return False, f"Não consegui procurar: {erro}"


def selecionar_celula(endereco):
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta."
        app.ActiveSheet.Range(endereco).Select()
        return True, endereco
    except Exception as erro:
        return False, f"Não consegui selecionar '{endereco}': {erro}"


def definir_valor(endereco, valor):
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta."
        app.ActiveSheet.Range(endereco).Value = valor
        return True, f"{endereco} agora é {valor}."
    except Exception as erro:
        return False, f"Não consegui alterar '{endereco}': {erro}"


def ler_valor(endereco):
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta."
        return True, app.ActiveSheet.Range(endereco).Value
    except Exception as erro:
        return False, f"Não consegui ler '{endereco}': {erro}"


def salvar(caminho=None):
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta para salvar."
        pasta = app.ActiveWorkbook
        if caminho:
            pasta.SaveAs(caminho)
            return True, caminho
        pasta.Save()
        return True, pasta.FullName
    except Exception as erro:
        return False, f"Não consegui salvar: {erro}"


def localizar_e_substituir(valor_antigo, valor_novo):
    """
    Fluxo composto real: localizar -> checar ambiguidade -> alterar ->
    reler -> confirmar, numa função só (em vez de decomposto em etapas
    do Planner) porque checar ambiguidade exige lógica condicional que
    o Planner ainda só sabe fazer em sequência linear, não com desvios
    (ver ResultadoDaEtapa em agente/planejador.py para o encadeamento
    simples que já existe, usado em "excel_localizar_valor ->
    excel_ler_valor"). Ainda assim nunca assume êxito: relê a célula
    depois de escrever.
    """
    app, erro = _obter_excel()
    if erro:
        return False, erro
    try:
        if app.Workbooks.Count == 0:
            return False, "Não há nenhuma planilha aberta."

        planilha = app.ActiveSheet
        primeira = planilha.Cells.Find(str(valor_antigo))
        if primeira is None:
            return False, f"Não encontrei '{valor_antigo}' na planilha."

        endereco = primeira.Address(False, False)
        segunda = planilha.Cells.FindNext(primeira)
        if segunda is not None and segunda.Address(False, False) != endereco:
            return False, (
                f"Encontrei mais de uma célula com '{valor_antigo}' "
                f"(pelo menos {endereco} e {segunda.Address(False, False)}). "
                "Diga o endereço exato da célula para eu trocar."
            )

        primeira.Value = valor_novo
        valor_relido = planilha.Range(endereco).Value
        if str(valor_relido) != str(valor_novo):
            return False, f"Tentei trocar em {endereco}, mas não confirmei a alteração ao reler."

        return True, f"Troquei '{valor_antigo}' por '{valor_novo}' na célula {endereco}."
    except Exception as erro:
        return False, f"Não consegui trocar o valor: {erro}"


def celula_tem_valor(endereco, valor_esperado):
    """Verificação: relê a célula e compara — nunca assume que a
    escrita funcionou só porque a chamada COM não lançou exceção."""
    app, erro = _obter_excel()
    if erro or app.Workbooks.Count == 0:
        return None
    try:
        atual = app.ActiveSheet.Range(endereco).Value
        return str(atual) == str(valor_esperado)
    except Exception:
        return None
