"""
Monta o Tool Registry padrão do agente, reaproveitando os componentes
que já existem no projeto — nunca duplicando lógica de mouse, teclado,
janelas, OCR ou UI Automation (ver relatório de auditoria arquitetural,
seção "Arquitetura desejada — agente universal").

`construir_registro_padrao(executor)` recebe a MESMA instância de
computer/executor.py:Executor já criada por core/alfa_core.py — as
ferramentas do agente chamam métodos dela, não recriam uma nova.
"""

from datetime import datetime

from agente import ambiente as ambiente_mod
from agente import descoberta_apps, ferramentas_arquivo, ferramentas_navegador
from agente import leitura_tela
from agente import verificador as verificacoes
from agente.ferramentas import Ferramenta, RegistroFerramentas
from core import pesquisa_app
from security.permissions import CATEGORIA_BASIC, CATEGORIA_FILES
from vision import screen_vision, ui_automation


def _verificar_abrir_aplicativo(programa, **_ignorados):
    return verificacoes.verificar_janela_aberta([programa.strip().lower()])


def _verificar_digitar(texto, **_ignorados):
    return verificacoes.verificar_texto_na_tela(texto)


def _verificar_caminho(caminho=None, **_ignorados):
    return verificacoes.verificar_arquivo_existe(caminho)


def _consultar_data_hora(**_ignorados):
    agora = datetime.now()
    return True, agora.strftime("%d/%m/%Y %H:%M")


def _localizar_e_focar_janela(palavras_chave):
    achado = pesquisa_app.encontrar_janela_pesquisa(palavras_chave)
    if not achado:
        return False, "Não encontrei nenhuma janela com esse nome."
    hwnd, titulo = achado
    pesquisa_app.focar_janela(hwnd)
    return True, titulo


def _consultar_web(url):
    import re as _re
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=5) as resposta:
            html = resposta.read().decode("utf-8", errors="ignore")
        texto = _re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=_re.S)
        texto = _re.sub(r"<[^>]+>", " ", texto)
        texto = _re.sub(r"\s+", " ", texto).strip()
        return True, texto[:1200]
    except Exception as erro:
        return False, f"Não consegui acessar '{url}': {erro}"


def _ler_elemento(nome_elemento):
    try:
        elemento = ui_automation.encontrar_elemento(nome_elemento)
    except Exception as erro:
        return False, f"Não consegui procurar '{nome_elemento}': {erro}"
    if elemento is None:
        return False, f"Não encontrei o elemento '{nome_elemento}' na tela."
    try:
        return True, ui_automation.ler_valor(elemento)
    except Exception as erro:
        return False, f"Encontrei '{nome_elemento}', mas não consegui ler o valor: {erro}"


def _clicar_elemento(nome_elemento):
    """
    Recuperação visual (hierarquia de percepção, ver relatório de
    auditoria): tenta por NOME via UI Automation; se não achar, cai
    para localizar o texto por OCR e clica na posição real encontrada
    — só usa coordenada como ÚLTIMO recurso, e ainda assim uma
    coordenada de verdade (achada agora), nunca fixa/inventada.
    """
    try:
        elemento = ui_automation.encontrar_elemento(nome_elemento)
    except Exception:
        elemento = None

    if elemento is not None:
        try:
            ui_automation.clicar_elemento(elemento)
            return True, f"Cliquei em '{nome_elemento}'."
        except Exception as erro:
            return False, f"Encontrei '{nome_elemento}', mas não consegui clicar: {erro}"

    achado = leitura_tela.encontrar_na_tela(nome_elemento)
    if achado["encontrado"] and achado["posicao"]:
        try:
            import pyautogui
            pyautogui.click(*achado["posicao"])
            return True, f"Cliquei em '{nome_elemento}' (localizado por OCR)."
        except Exception as erro:
            return False, f"Localizei '{nome_elemento}' por OCR, mas não consegui clicar: {erro}"

    return False, f"Não encontrei '{nome_elemento}' na tela."


def _digitar_elemento(nome_elemento, texto):
    try:
        elemento = ui_automation.encontrar_elemento(nome_elemento)
    except Exception:
        elemento = None

    if elemento is None:
        return False, f"Não encontrei '{nome_elemento}' na tela."
    try:
        ui_automation.digitar_no_elemento(elemento, texto)
        return True, f"Escrevi em '{nome_elemento}'."
    except Exception as erro:
        return False, f"Encontrei '{nome_elemento}', mas não consegui escrever: {erro}"


def _verificar_elemento_tem_texto(nome_elemento, texto, **_ignorados):
    valor = verificacoes.verificar_elemento(nome_elemento)
    if valor is None:
        return None
    return texto.strip().lower() in str(valor).strip().lower()


def _ler_tela_tool():
    estrutura = leitura_tela.ler_tela_estruturada()
    return True, {"resumo": leitura_tela.resumo_legivel(estrutura), "estrutura": estrutura}


def _encontrar_na_tela_tool(alvo, tipo_controle=None):
    resultado = leitura_tela.encontrar_na_tela(alvo, tipo_controle=tipo_controle)
    if not resultado["encontrado"]:
        return False, f"Não encontrei '{alvo}' na tela."
    return True, resultado


def _rolar_para_elemento_tool(executor, alvo, direcao="baixo"):
    resultado = leitura_tela.rolar_para_elemento(alvo, executor, direcao=direcao)
    if not resultado["encontrado"]:
        return False, f"Rolei a tela, mas não encontrei '{alvo}'."
    return True, resultado


def _verificar_destino_arquivo(destino=None, **_ignorados):
    return verificacoes.verificar_arquivo_existe(destino)


def _verificar_renomeado(caminho_atual=None, novo_nome=None, **_ignorados):
    if not caminho_atual or not novo_nome:
        return None
    import os
    destino = os.path.join(os.path.dirname(caminho_atual), novo_nome)
    return verificacoes.verificar_arquivo_existe(destino)


def _consultar_clima_tool(local=""):
    from core import clima
    resultado = clima.consultar(local)
    if resultado is None:
        return False, "Não consegui consultar a previsão do tempo agora — sem internet ou o serviço está indisponível."
    return True, resultado


def construir_registro_padrao(executor):
    registro = RegistroFerramentas()

    registro.registrar(Ferramenta(
        nome="abrir_aplicativo",
        descricao="Localizar e abrir um programa instalado neste computador",
        parametros={"programa": "nome do programa, ex.: 'word', 'chrome'"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda programa: descoberta_apps.abrir_aplicativo(programa),
        verificador=_verificar_abrir_aplicativo,
    ))

    registro.registrar(Ferramenta(
        nome="fechar_aplicativo",
        descricao="Fechar um programa em execução",
        parametros={"programa": "nome do programa (whitelist existente)"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda programa: executor.fechar(programa),
    ))

    registro.registrar(Ferramenta(
        nome="clicar",
        descricao="Clicar na posição atual do mouse",
        parametros={"botao": "'esquerdo' | 'direito' | 'duplo'"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda botao="esquerdo": executor.clique(botao),
    ))

    registro.registrar(Ferramenta(
        nome="digitar",
        descricao="Digitar um texto no campo com foco atual",
        parametros={"texto": "texto a digitar"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda texto: executor.digitar(texto),
        verificador=_verificar_digitar,
    ))

    registro.registrar(Ferramenta(
        nome="pressionar_tecla",
        descricao="Pressionar uma tecla avulsa ou uma combinação de teclas",
        parametros={"teclas": "tecla única (str) ou combinação, ex.: ('ctrl', 'n')"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda teclas: (
            executor.atalho(tuple(teclas))
            if isinstance(teclas, (tuple, list)) and len(teclas) > 1
            else executor.pressionar_tecla(teclas)
        ),
    ))

    registro.registrar(Ferramenta(
        nome="localizar_janela",
        descricao="Encontrar e trazer para frente uma janela pelo título",
        parametros={"palavras_chave": "lista de palavras a procurar no título"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda palavras_chave: _localizar_e_focar_janela(palavras_chave),
    ))

    registro.registrar(Ferramenta(
        nome="ler_tela",
        descricao="Ler a tela de forma estruturada (UI Automation, com OCR como reforço)",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: _ler_tela_tool(),
    ))

    registro.registrar(Ferramenta(
        nome="ui_automation_ler_elemento",
        descricao="Ler o valor de um elemento de tela pelo nome (UI Automation)",
        parametros={"nome_elemento": "nome/rótulo do elemento"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda nome_elemento: _ler_elemento(nome_elemento),
    ))

    registro.registrar(Ferramenta(
        nome="clicar_elemento",
        descricao="Clicar num elemento da tela pelo nome/rótulo (não por coordenada)",
        parametros={"nome_elemento": "nome/rótulo do elemento, ex.: 'Salvar'"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda nome_elemento: _clicar_elemento(nome_elemento),
    ))

    registro.registrar(Ferramenta(
        nome="digitar_elemento",
        descricao="Digitar um texto num campo da tela pelo nome/rótulo (não por coordenada)",
        parametros={"nome_elemento": "nome/rótulo do campo, ex.: 'Nome'", "texto": "texto a digitar"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda nome_elemento, texto: _digitar_elemento(nome_elemento, texto),
        verificador=_verificar_elemento_tem_texto,
    ))

    registro.registrar(Ferramenta(
        nome="encontrar_na_tela",
        descricao="Procurar um texto/elemento na tela (UI Automation, depois OCR) e informar onde está",
        parametros={"alvo": "texto ou descrição a procurar", "tipo_controle": "tipo de controle (opcional)"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda alvo, tipo_controle=None: _encontrar_na_tela_tool(alvo, tipo_controle),
    ))

    registro.registrar(Ferramenta(
        nome="rolar_para_elemento",
        descricao="Rolar a tela até encontrar um elemento fora da área visível (limite seguro de tentativas)",
        parametros={"alvo": "texto/elemento a procurar", "direcao": "'cima' | 'baixo' (padrão baixo)"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda alvo, direcao="baixo": _rolar_para_elemento_tool(executor, alvo, direcao),
    ))

    registro.registrar(Ferramenta(
        nome="consultar_clima",
        descricao="Consultar a previsão do tempo atual (depende de internet)",
        parametros={"local": "cidade (opcional — usa a localização por IP se vazio)"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda local="": _consultar_clima_tool(local),
    ))

    registro.registrar(Ferramenta(
        nome="consultar_data_hora",
        descricao="Consultar a data e hora atuais do sistema",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=_consultar_data_hora,
    ))

    registro.registrar(Ferramenta(
        nome="localizar_arquivo",
        descricao="Procurar um arquivo pelo nome nas pastas conhecidas do usuário",
        parametros={"nome": "nome (ou parte do nome) do arquivo"},
        categoria=CATEGORIA_FILES,
        funcao=lambda nome: ferramentas_arquivo.localizar_arquivo(nome),
    ))

    registro.registrar(Ferramenta(
        nome="abrir_arquivo",
        descricao="Abrir um arquivo já localizado",
        parametros={"nome": "caminho ou nome do arquivo"},
        categoria=CATEGORIA_FILES,
        funcao=lambda nome: executor.abrir_arquivo(nome),
    ))

    registro.registrar(Ferramenta(
        nome="criar_pasta",
        descricao="Criar uma pasta nova",
        parametros={"caminho": "caminho completo da pasta a criar"},
        categoria=CATEGORIA_FILES,
        funcao=lambda caminho: ferramentas_arquivo.criar_pasta(caminho),
        verificador=_verificar_caminho,
    ))

    registro.registrar(Ferramenta(
        nome="renomear_arquivo",
        descricao="Renomear um arquivo existente (mesma pasta)",
        parametros={"caminho_atual": "caminho do arquivo", "novo_nome": "novo nome"},
        categoria=CATEGORIA_FILES,
        funcao=lambda caminho_atual, novo_nome: ferramentas_arquivo.renomear_arquivo(
            caminho_atual, novo_nome
        ),
        verificador=_verificar_renomeado,
    ))

    try:
        from vision import vision as vision_module

        registro.registrar(Ferramenta(
            nome="camera",
            descricao="Descrever o que a câmera está vendo agora",
            parametros={},
            categoria=CATEGORIA_BASIC,
            funcao=lambda: (True, vision_module.analisar_camera()),
        ))
    except Exception:
        pass

    try:
        from vision.presenca import alguem_presente

        registro.registrar(Ferramenta(
            nome="detectar_presenca",
            descricao="Verificar se há alguém diante da câmera agora (não identifica quem)",
            parametros={},
            categoria=CATEGORIA_BASIC,
            funcao=lambda: (True, alguem_presente()),
        ))
    except Exception:
        pass

    # --- Mouse/teclado adicionais (envolvem só métodos já existentes
    # em computer/executor.py — nada novo, só exposto ao registro) ---
    registro.registrar(Ferramenta(
        nome="duplo_clique",
        descricao="Duplo clique na posição atual do mouse",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: executor.clique("duplo"),
    ))

    registro.registrar(Ferramenta(
        nome="rolar",
        descricao="Rolar a tela para cima ou para baixo",
        parametros={"direcao": "'cima' | 'baixo'"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda direcao="baixo": executor.scroll(direcao),
    ))

    registro.registrar(Ferramenta(
        nome="arrastar",
        descricao="Arrastar o mouse (botão pressionado) numa direção",
        parametros={"direcao": "'esquerda' | 'direita' | 'cima' | 'baixo' | 'centro'"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda direcao: executor.arrastar_mouse(direcao),
    ))

    registro.registrar(Ferramenta(
        nome="alternar_janela",
        descricao="Alternar para a próxima janela (Alt+Tab)",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: executor.alternar_janela(),
    ))

    registro.registrar(Ferramenta(
        nome="selecionar",
        descricao="Selecionar uma opção num combobox/lista pelo nome do campo",
        parametros={"campo": "nome do campo", "opcao": "texto da opção a selecionar"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda campo, opcao: _selecionar_opcao(campo, opcao),
    ))

    registro.registrar(Ferramenta(
        nome="captura_tela",
        descricao="Tirar um print da tela",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: _captura_tela(),
    ))

    # --- Arquivos adicionais ---
    registro.registrar(Ferramenta(
        nome="listar_arquivos",
        descricao="Listar o conteúdo de uma pasta conhecida",
        parametros={"pasta": "nome da pasta, ex.: 'downloads', 'documentos'"},
        categoria=CATEGORIA_FILES,
        funcao=lambda pasta: ferramentas_arquivo.listar_arquivos(pasta),
    ))

    registro.registrar(Ferramenta(
        nome="criar_arquivo",
        descricao="Criar um arquivo de texto novo (nunca sobrescreve um já existente)",
        parametros={"caminho": "caminho completo do arquivo", "conteudo": "conteúdo inicial (opcional)"},
        categoria=CATEGORIA_FILES,
        funcao=lambda caminho, conteudo="": ferramentas_arquivo.criar_arquivo(caminho, conteudo),
        verificador=_verificar_caminho,
    ))

    registro.registrar(Ferramenta(
        nome="copiar_arquivo",
        descricao="Copiar um arquivo para outro local (nunca sobrescreve o destino)",
        parametros={"origem": "caminho de origem", "destino": "caminho de destino"},
        categoria=CATEGORIA_FILES,
        funcao=lambda origem, destino: ferramentas_arquivo.copiar_arquivo(origem, destino),
    ))

    registro.registrar(Ferramenta(
        nome="mover_arquivo",
        descricao="Mover um arquivo para outro local (nunca sobrescreve o destino)",
        parametros={"origem": "caminho de origem", "destino": "caminho de destino"},
        categoria=CATEGORIA_FILES,
        funcao=lambda origem, destino: ferramentas_arquivo.mover_arquivo(origem, destino),
        verificador=_verificar_destino_arquivo,
    ))

    # --- Descoberta de aplicativos e ambiente ---
    registro.registrar(Ferramenta(
        nome="descobrir_aplicativos",
        descricao="Listar quais programas conhecidos estão instalados neste computador",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: (True, ambiente_mod._aplicativos_conhecidos()["aplicativos_encontrados"]),
    ))

    registro.registrar(Ferramenta(
        nome="detectar_ambiente",
        descricao="Verificar CPU/RAM/GPU/microfone/câmera/internet/modelos locais deste computador",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: (True, ambiente_mod.detectar_ambiente()),
    ))

    # --- Navegador (reaproveita a mesma instância de Executor) ---
    registro.registrar(Ferramenta(
        nome="navegador_abrir",
        descricao="Abrir o navegador (opcionalmente já numa URL)",
        parametros={"url": "endereço a abrir (opcional)"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda url=None: ferramentas_navegador.abrir(executor, url),
    ))

    registro.registrar(Ferramenta(
        nome="navegador_pesquisar",
        descricao="Pesquisar um termo no navegador já aberto",
        parametros={"termo": "o que pesquisar"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda termo: ferramentas_navegador.pesquisar(executor, termo),
    ))

    registro.registrar(Ferramenta(
        nome="navegador_voltar",
        descricao="Voltar para a página anterior no navegador",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: ferramentas_navegador.voltar(executor),
    ))

    registro.registrar(Ferramenta(
        nome="navegador_avancar",
        descricao="Avançar para a próxima página no navegador",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: ferramentas_navegador.avancar(executor),
    ))

    registro.registrar(Ferramenta(
        nome="navegador_fechar_aba",
        descricao="Fechar a aba atual do navegador",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: ferramentas_navegador.fechar_aba(executor),
    ))

    registro.registrar(Ferramenta(
        nome="navegador_ler_pagina",
        descricao="Ler o texto visível da página atual do navegador (OCR local)",
        parametros={},
        categoria=CATEGORIA_BASIC,
        funcao=lambda: ferramentas_navegador.ler_pagina(),
    ))

    registro.registrar(Ferramenta(
        nome="consultar_web",
        descricao="Buscar o conteúdo de texto de uma URL diretamente (sem abrir navegador)",
        parametros={"url": "endereço a consultar"},
        categoria=CATEGORIA_BASIC,
        funcao=lambda url: _consultar_web(url),
    ))

    _registrar_skills_office(registro)

    return registro


def _captura_tela():
    try:
        imagem = screen_vision.capturar_tela_pil()
    except Exception as erro:
        return False, f"Não consegui capturar a tela: {erro}"
    if imagem is None:
        return False, "Não consegui capturar a tela."
    return True, "Print capturado."


def _selecionar_opcao(campo, opcao):
    try:
        elemento = ui_automation.encontrar_elemento(campo)
    except Exception as erro:
        return False, f"Não consegui procurar o campo '{campo}': {erro}"
    if elemento is None:
        return False, f"Não encontrei o campo '{campo}' na tela."
    try:
        return True, ui_automation.selecionar_opcao_combobox(elemento, opcao)
    except Exception as erro:
        return False, f"Não consegui selecionar '{opcao}': {erro}"


def _registrar_skills_office(registro):
    """
    Word/Excel/PowerPoint via COM (ver skills/) — registradas sempre;
    se o Office não estiver instalado nesta máquina, cada chamada
    devolve uma falha honesta na hora de executar, não trava o
    registro nem o resto do agente.
    """
    from security.permissions import CATEGORIA_SENSITIVE

    try:
        from skills import word

        registro.registrar(Ferramenta(
            nome="word_abrir", descricao="Abrir o Microsoft Word",
            parametros={}, categoria=CATEGORIA_BASIC, funcao=lambda: word.abrir(),
        ))
        registro.registrar(Ferramenta(
            nome="word_novo_documento", descricao="Criar um documento novo no Word",
            parametros={}, categoria=CATEGORIA_BASIC, funcao=lambda: word.novo_documento(),
        ))
        registro.registrar(Ferramenta(
            nome="word_escrever", descricao="Escrever um texto no documento do Word aberto",
            parametros={"texto": "texto a escrever"}, categoria=CATEGORIA_BASIC,
            funcao=lambda texto: word.escrever(texto),
            verificador=lambda texto, **_i: word.documento_tem_texto(texto),
        ))
        registro.registrar(Ferramenta(
            nome="word_localizar", descricao="Localizar um trecho de texto no documento do Word",
            parametros={"texto": "texto a procurar"}, categoria=CATEGORIA_BASIC,
            funcao=lambda texto: word.localizar(texto),
        ))
        registro.registrar(Ferramenta(
            nome="word_substituir", descricao="Substituir um trecho de texto por outro no Word",
            parametros={"de": "texto atual", "para": "novo texto"}, categoria=CATEGORIA_BASIC,
            funcao=lambda de, para: word.substituir(de, para),
        ))
        registro.registrar(Ferramenta(
            nome="word_salvar", descricao="Salvar o documento do Word aberto",
            parametros={"caminho": "caminho do arquivo (opcional, usa o atual se já salvo)"},
            categoria=CATEGORIA_SENSITIVE,  # grava em disco -> exige confirmação
            funcao=lambda caminho=None: word.salvar(caminho),
        ))
    except Exception:
        pass

    try:
        from skills import excel

        registro.registrar(Ferramenta(
            nome="excel_abrir", descricao="Abrir o Microsoft Excel",
            parametros={}, categoria=CATEGORIA_BASIC, funcao=lambda: excel.abrir(),
        ))
        registro.registrar(Ferramenta(
            nome="excel_localizar_valor", descricao="Localizar um valor na planilha do Excel aberta",
            parametros={"valor": "valor a procurar"}, categoria=CATEGORIA_BASIC,
            funcao=lambda valor: excel.localizar_valor(valor),
        ))
        registro.registrar(Ferramenta(
            nome="excel_localizar_todos",
            descricao="Localizar TODAS as células com um valor (para escolher entre vários resultados)",
            parametros={"valor": "valor a procurar", "limite": "máximo de ocorrências (padrão 20)"},
            categoria=CATEGORIA_BASIC,
            funcao=lambda valor, limite=20: excel.localizar_todos(valor, limite),
        ))
        registro.registrar(Ferramenta(
            nome="excel_selecionar_celula", descricao="Selecionar uma célula pelo endereço, ex.: 'B3'",
            parametros={"endereco": "endereço da célula"}, categoria=CATEGORIA_BASIC,
            funcao=lambda endereco: excel.selecionar_celula(endereco),
        ))
        registro.registrar(Ferramenta(
            nome="excel_definir_valor", descricao="Alterar o valor de uma célula do Excel",
            parametros={"endereco": "endereço da célula", "valor": "novo valor"},
            categoria=CATEGORIA_SENSITIVE,  # altera dado real da planilha -> exige confirmação
            funcao=lambda endereco, valor: excel.definir_valor(endereco, valor),
            verificador=lambda endereco, valor, **_i: excel.celula_tem_valor(endereco, valor),
        ))
        registro.registrar(Ferramenta(
            nome="excel_ler_valor", descricao="Ler o valor de uma célula do Excel",
            parametros={"endereco": "endereço da célula"}, categoria=CATEGORIA_BASIC,
            funcao=lambda endereco: excel.ler_valor(endereco),
        ))
        registro.registrar(Ferramenta(
            nome="excel_salvar", descricao="Salvar a planilha do Excel aberta",
            parametros={"caminho": "caminho do arquivo (opcional, usa o atual se já salvo)"},
            categoria=CATEGORIA_SENSITIVE,  # grava em disco -> exige confirmação
            funcao=lambda caminho=None: excel.salvar(caminho),
        ))
        registro.registrar(Ferramenta(
            nome="excel_localizar_e_substituir",
            descricao="Localizar um valor na planilha e trocar por outro (localiza, checa ambiguidade, altera, relê e confirma)",
            parametros={"valor_antigo": "valor a procurar", "valor_novo": "novo valor"},
            categoria=CATEGORIA_SENSITIVE,  # altera dado real -> exige confirmação
            funcao=lambda valor_antigo, valor_novo: excel.localizar_e_substituir(valor_antigo, valor_novo),
        ))
    except Exception:
        pass

    try:
        from skills import powerpoint

        registro.registrar(Ferramenta(
            nome="powerpoint_abrir", descricao="Abrir o Microsoft PowerPoint",
            parametros={}, categoria=CATEGORIA_BASIC, funcao=lambda: powerpoint.abrir(),
        ))
        registro.registrar(Ferramenta(
            nome="powerpoint_criar_apresentacao", descricao="Criar uma apresentação nova",
            parametros={}, categoria=CATEGORIA_BASIC, funcao=lambda: powerpoint.criar_apresentacao(),
        ))
        registro.registrar(Ferramenta(
            nome="powerpoint_novo_slide", descricao="Criar um novo slide na apresentação atual",
            parametros={}, categoria=CATEGORIA_BASIC, funcao=lambda: powerpoint.novo_slide(),
        ))
        registro.registrar(Ferramenta(
            nome="powerpoint_definir_titulo", descricao="Definir o título do slide atual",
            parametros={"texto": "título do slide"}, categoria=CATEGORIA_BASIC,
            funcao=lambda texto: powerpoint.definir_titulo(texto),
            verificador=lambda texto, **_i: powerpoint.slide_tem_titulo(texto),
        ))
        registro.registrar(Ferramenta(
            nome="powerpoint_definir_conteudo", descricao="Definir o conteúdo do slide atual",
            parametros={"texto": "conteúdo do slide"}, categoria=CATEGORIA_BASIC,
            funcao=lambda texto: powerpoint.definir_conteudo(texto),
            verificador=lambda texto, **_i: powerpoint.slide_tem_conteudo(texto),
        ))
        registro.registrar(Ferramenta(
            nome="powerpoint_salvar", descricao="Salvar a apresentação aberta",
            parametros={"caminho": "caminho do arquivo (opcional, usa o atual se já salvo)"},
            categoria=CATEGORIA_SENSITIVE,  # grava em disco -> exige confirmação
            funcao=lambda caminho=None: powerpoint.salvar(caminho),
        ))
    except Exception:
        pass
