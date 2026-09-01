"""
Preenchimento de formulários orientado a ELEMENTOS, não a coordenadas
fixas de tela — "encontrar o campo Nome -> clicar -> preencher" em
vez de "x=500, y=300", para resistir a mudanças de tamanho/layout de
janela.

Estratégia em camadas (da mais robusta para a mais genérica):
  1. AutomationId real do elemento, quando conhecido de antemão (ver
     core/roteiro_pesquisa.py) — o mais confiável, imune a variações
     de texto/idioma/OCR.
  2. Windows UI Automation por nome/rótulo visível (vision/ui_automation.py)
     — quando o app expõe sua árvore de acessibilidade (a maioria dos
     apps Win32/UWP/WinUI e, via a ponte de acessibilidade do
     Chromium, também páginas abertas no Edge/Chrome).
  3. OCR local (vision/screen_vision.py) — quando o app não expõe UIA,
     mas o rótulo do campo aparece como texto na tela.

Depois de preencher um campo de texto, o valor é LIDO DE VOLTA do
elemento real para confirmar que a digitação realmente "pegou" —
nunca assume sucesso silenciosamente (ver FalhaDeVerificacao).

Nunca executa uma ação a partir de texto de transcrição livre: só os
nomes de campo/opção já extraídos pelo NLU (core/intent_engine.py) ou
definidos num roteiro real (core/roteiro_pesquisa.py) chegam até
aqui.
"""

import time

import pyautogui

from vision import screen_vision, ui_automation

BOTOES_AVANCAR = ["Próximo", "Avançar", "Next", "Continuar"]
BOTOES_VOLTAR = ["Voltar", "Anterior", "Back"]
BOTOES_CONFIRMAR = ["Confirmar", "Enviar", "Concluir", "Finalizar", "OK", "Submit"]


class ElementoNaoEncontrado(Exception):
    pass


class FalhaDeVerificacao(Exception):
    """
    O preenchimento foi tentado, mas ler o valor de volta do elemento
    real não confirmou que o texto foi realmente inserido. Quem chama
    (core/atendimento.py) decide se tenta de novo ou avisa a pessoa.
    """


class FormFiller:
    def __init__(self, pausa_entre_acoes=0.15, deslocamento_rotulo_ocr=32):
        self.pausa = pausa_entre_acoes
        # Quando o campo só é achado via OCR, o que foi lido é o
        # RÓTULO (um <input> vazio não tem texto para o OCR ler) —
        # nos formulários web mais comuns o campo fica logo abaixo do
        # rótulo, então desloca o clique para baixo. É uma heurística
        # (não garante acertar em qualquer layout) — quando o
        # AutomationId ou o UI Automation por nome encontram o
        # elemento de verdade, esse deslocamento nunca é usado.
        self.deslocamento_rotulo_ocr = deslocamento_rotulo_ocr
        # Contexto do agente (ver agente/contexto.py) — associado DEPOIS
        # da construção (core/alfa_core.py), pois o FormFiller nasce
        # antes do ContextoSessao existir. None aqui = comportamento
        # idêntico a antes desta mudança (nenhum contexto atualizado).
        self.contexto = None

    # -----------------------------------------------------------
    # LOCALIZAÇÃO (AutomationId -> UIA por nome -> OCR)
    # -----------------------------------------------------------
    def _localizar(self, nome, tipo_controle=None, automation_id=None):
        if automation_id:
            elemento = ui_automation.encontrar_por_id(automation_id, tipo_controle=tipo_controle)
            if elemento:
                self._registrar_no_contexto(nome, "uia", elemento)
                return "uia", elemento

        elemento = ui_automation.encontrar_elemento(nome, tipo_controle=tipo_controle)
        if elemento:
            self._registrar_no_contexto(nome, "uia", elemento)
            return "uia", elemento

        if screen_vision.ocr_disponivel():
            achado = screen_vision.localizar_texto(nome)
            if achado:
                self._registrar_no_contexto(nome, "ocr", achado)
                return "ocr", achado

        return None, None

    def _registrar_no_contexto(self, nome_procurado, origem, elemento):
        """
        Alimenta o MESMO contexto do agente (ver agente/contexto.py)
        usado pelo caminho moderno de leitura de tela — nunca cria um
        mecanismo de contexto paralelo (ver relatório de unificação).
        Best-effort: sem contexto associado (uso isolado/testes), não
        faz nada; nunca lança exceção para quem chamou localizar algo.
        """
        if self.contexto is None:
            return
        try:
            from agente.leitura_tela import padronizar_resultado

            if origem == "uia":
                resultado = padronizar_resultado(
                    texto=elemento.get("nome") or nome_procurado,
                    nome=elemento.get("nome"),
                    tipo=elemento.get("tipo"),
                    posicao=(elemento.get("x"), elemento.get("y")),
                    ferramenta="form_filler",
                )
            else:  # "ocr"
                resultado = padronizar_resultado(
                    texto=elemento.get("texto") or nome_procurado,
                    tipo="texto_ocr",
                    posicao=(elemento.get("x"), elemento.get("y")),
                    ferramenta="form_filler",
                )
            self.contexto.ultimo_elemento_selecionado = resultado
            self.contexto.definir_resultados([resultado], ferramenta="form_filler")
        except Exception:
            pass

    def _clicar(self, origem, elemento):
        if origem == "uia":
            ui_automation.clicar_elemento(elemento)
        else:
            pyautogui.click(elemento["x"], elemento["y"])
        time.sleep(self.pausa)

    def _clicar_para_digitar(self, origem, elemento):
        """Como _clicar, mas desloca o clique quando a origem é OCR (ver __init__)."""
        if origem == "ocr":
            pyautogui.click(elemento["x"], elemento["y"] + self.deslocamento_rotulo_ocr)
            time.sleep(self.pausa)
        else:
            self._clicar(origem, elemento)

    def localizar(self, alvo, automation_id=None):
        origem, elemento = self._localizar(alvo, automation_id=automation_id)
        if elemento is None:
            return f"Não encontrei '{alvo}' na tela."
        return f"Encontrei '{alvo}' na tela, na posição {elemento['x']} por {elemento['y']}."

    def listar_opcoes(self, nome_campo, automation_id=None):
        """Opções REAIS de um campo de seleção, lidas ao vivo da tela (nunca uma lista fixa)."""
        origem, elemento = self._localizar(nome_campo, tipo_controle="ComboBox", automation_id=automation_id)
        if elemento is None or origem != "uia":
            return []
        return ui_automation.obter_opcoes(elemento)

    # -----------------------------------------------------------
    # AÇÕES DE FORMULÁRIO
    # -----------------------------------------------------------
    def preencher_texto(self, nome_campo, texto, automation_id=None):
        origem, elemento = self._localizar(nome_campo, tipo_controle="Edit", automation_id=automation_id)
        if elemento is None:
            origem, elemento = self._localizar(nome_campo, automation_id=automation_id)
        if elemento is None:
            raise ElementoNaoEncontrado(f"Não encontrei o campo '{nome_campo}' na tela.")

        preenchido_via_uia = origem == "uia" and ui_automation.digitar_no_elemento(elemento, texto)

        if not preenchido_via_uia:
            self._clicar_para_digitar(origem, elemento)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.write(texto, interval=0.01)

        time.sleep(self.pausa)

        # Verificação pós-preenchimento: só é possível ler de volta o
        # valor quando o elemento foi localizado via UIA de verdade.
        if origem == "uia" and texto.strip():
            valor_atual = ui_automation.ler_valor(elemento)
            if valor_atual is not None and texto.strip().lower() not in valor_atual.strip().lower():
                raise FalhaDeVerificacao(
                    f"preenchi '{nome_campo}', mas o valor lido de volta foi "
                    f"'{valor_atual}', não '{texto}'"
                )

        return f"Preenchi '{nome_campo}' com '{texto}'."

    def marcar_checkbox(self, nome_campo, marcar=True, automation_id=None):
        origem, elemento = self._localizar(nome_campo, tipo_controle="CheckBox", automation_id=automation_id)
        if elemento is None:
            origem, elemento = self._localizar(nome_campo, tipo_controle="RadioButton", automation_id=automation_id)
        if elemento is None:
            origem, elemento = self._localizar(nome_campo, automation_id=automation_id)
        if elemento is None:
            raise ElementoNaoEncontrado(f"Não encontrei a caixa de seleção '{nome_campo}'.")

        if origem == "uia":
            ui_automation.marcar_checkbox(elemento, marcar)
            time.sleep(self.pausa)

            estado_atual = ui_automation.esta_marcado(elemento)
            if estado_atual is not None and estado_atual != marcar:
                raise FalhaDeVerificacao(
                    f"tentei {'marcar' if marcar else 'desmarcar'} '{nome_campo}', mas o "
                    f"estado lido de volta foi {'marcado' if estado_atual else 'desmarcado'}"
                )
        else:
            self._clicar(origem, elemento)

        return f"{'Marquei' if marcar else 'Desmarquei'} '{nome_campo}'."

    def selecionar_opcao(self, nome_campo, texto_opcao, automation_id=None):
        origem, elemento = self._localizar(nome_campo, tipo_controle="ComboBox", automation_id=automation_id)
        if elemento is None:
            raise ElementoNaoEncontrado(f"Não encontrei a lista '{nome_campo}'.")

        if origem == "uia":
            ui_automation.selecionar_opcao_combobox(elemento, texto_opcao)
            time.sleep(self.pausa)

            valor_atual = ui_automation.ler_valor(elemento)
            if valor_atual is not None and texto_opcao.strip().lower() not in valor_atual.strip().lower():
                raise FalhaDeVerificacao(
                    f"selecionei '{texto_opcao}' em '{nome_campo}', mas o valor lido de "
                    f"volta foi '{valor_atual}'"
                )
        else:
            self._clicar(origem, elemento)

        return f"Selecionei '{texto_opcao}' em '{nome_campo}'."

    def _pos_clique_ainda_responsivo(self):
        """
        Verificação BEST-EFFORT após um clique: um clique não tem um
        "valor" para reler como um campo de texto tem, então isso só
        confirma que a árvore de UI Automation da janela ativa
        continua respondendo (a página não travou) — não prova que o
        clique teve o efeito específico esperado. Para uma verificação
        mais forte de um clique específico, use verificar_texto_na_tela()
        com o texto que deveria aparecer depois (ex.: uma mensagem de
        sucesso real da tela).
        """
        try:
            janela = ui_automation.janela_ativa()
            if janela is None:
                return False
            janela.descendants()
            return True
        except Exception:
            return False

    def clicar_botao(self, nome_botao, automation_id=None):
        origem, elemento = self._localizar(nome_botao, tipo_controle="Button", automation_id=automation_id)
        if elemento is None:
            origem, elemento = self._localizar(nome_botao, automation_id=automation_id)
        if elemento is None:
            raise ElementoNaoEncontrado(f"Não encontrei '{nome_botao}' na tela.")

        self._clicar(origem, elemento)

        if origem == "uia" and not self._pos_clique_ainda_responsivo():
            raise FalhaDeVerificacao(
                f"cliquei em '{nome_botao}', mas não consegui confirmar que a tela "
                "respondeu depois do clique."
            )

        return f"Cliquei em '{nome_botao}'."

    def _clicar_primeiro_disponivel(self, nomes, acao_nome):
        for nome in nomes:
            origem, elemento = self._localizar(nome, tipo_controle="Button")
            if elemento:
                self._clicar(origem, elemento)
                if origem == "uia" and not self._pos_clique_ainda_responsivo():
                    raise FalhaDeVerificacao(
                        f"cliquei em '{nome}', mas não consegui confirmar que a tela "
                        "respondeu depois do clique."
                    )
                return f"{acao_nome} ({nome})."
        raise ElementoNaoEncontrado(f"Não encontrei um botão de {acao_nome.lower()} na tela.")

    def avancar(self):
        return self._clicar_primeiro_disponivel(BOTOES_AVANCAR, "Avancei")

    def voltar(self):
        return self._clicar_primeiro_disponivel(BOTOES_VOLTAR, "Voltei")

    def confirmar(self):
        return self._clicar_primeiro_disponivel(BOTOES_CONFIRMAR, "Confirmei")

    def verificar_texto_na_tela(self, texto_esperado):
        """Verificação visual pós-ação: o texto esperado apareceu na tela?"""
        if ui_automation.encontrar_elemento(texto_esperado):
            return True
        if screen_vision.ocr_disponivel():
            return screen_vision.localizar_texto(texto_esperado) is not None
        return False
