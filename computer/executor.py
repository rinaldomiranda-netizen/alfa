"""
Camada de execução real do ALFA.

Recebe uma intenção estruturada (ver core/intent_engine.py) e executa
a ação correspondente no sistema operacional via pyautogui/psutil.

Segurança: nenhuma string de texto transcrito chega até aqui. Só os
campos já extraídos pela intenção (direção, programa, botão) são
usados, e apenas para os intents e programas listados em
security/permissions.py. Não há execução de shell arbitrário a
partir de texto de voz.
"""

import os
import subprocess

import psutil
import pyautogui

from security.permissions import (
    PROGRAMAS_ABRIR,
    PROGRAMAS_FECHAR,
    intencao_permitida,
)

SAIR = "__SAIR__"
INICIAR_ATENDIMENTO_SINAL = "__INICIAR_ATENDIMENTO__"
ENCERRAR_ATENDIMENTO_SINAL = "__ENCERRAR_ATENDIMENTO__"

# Intenções puramente conversacionais: não executam nada no sistema,
# o texto falado real vem de core/personality.py (ver compor()), que
# ignora este retorno — ele só precisa ser não vazio para a whitelist
# de security/permissions.py deixar passar.
CONVERSA_INTENTS = {
    "CONVERSA_SAUDACAO",
    "CONVERSA_ESTADO",
    "CONVERSA_AGRADECIMENTO",
    "CONVERSA_DESPEDIDA_LEVE",
    "CONVERSA_AGUARDAR",
    "CONVERSA_CONTINUAR",
    "CONVERSA_HORAS",
    "CONVERSA_DATA",
    "IDENTIDADE_QUEM_E_VOCE",
    "IDENTIDADE_QUEM_CRIOU",
    "IDENTIDADE_QUEM_E_RINALDO",
    "IDENTIDADE_O_QUE_E_ALFA",
    "IDENTIDADE_POR_QUE_BETA",
    "IDENTIDADE_PARA_QUE_SERVE",
    "IDENTIDADE_O_QUE_CONSEGUE_FAZER",
    "IDENTIDADE_FUNCIONA_OFFLINE",
    "IDENTIDADE_USA_COMPUTADOR",
    "IDENTIDADE_ACESSIBILIDADE",
    "IDENTIDADE_SEM_TECLADO",
    "IDENTIDADE_E_HUMANA",
    "IDENTIDADE_SABE_TUDO",
    "REFERENCIA_AMBIGUA",
}

PASTAS_CONHECIDAS = {
    "area de trabalho": os.path.join(os.path.expanduser("~"), "Desktop"),
    "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    "documentos": os.path.join(os.path.expanduser("~"), "Documents"),
    "imagens": os.path.join(os.path.expanduser("~"), "Pictures"),
    "videos": os.path.join(os.path.expanduser("~"), "Videos"),
    "musicas": os.path.join(os.path.expanduser("~"), "Music"),
}


class Executor:
    def __init__(self, passo_pixels=120, duracao=0.05, form_filler=None):
        self.passo_pixels = passo_pixels
        self.duracao = duracao
        # Opcional: injeta a camada de automação orientada a
        # elementos (computer/form_filler.py). Se None (ex.:
        # pywinauto/winsdk indisponíveis), os intents que dependem
        # dela respondem com uma mensagem clara em vez de travar.
        self.form_filler = form_filler

    # -----------------------------------------------------------
    # MOUSE
    # -----------------------------------------------------------
    def _delta_direcao(self, direcao):
        mapa = {
            "esquerda": (-self.passo_pixels, 0),
            "direita": (self.passo_pixels, 0),
            "cima": (0, -self.passo_pixels),
            "baixo": (0, self.passo_pixels),
        }
        return mapa.get(direcao)

    def mover_mouse(self, direcao):
        if not direcao:
            return (
                "Entendi que você quer mover o mouse. "
                "Para qual lado: esquerda, direita, cima ou baixo?"
            )

        largura, altura = pyautogui.size()

        if direcao == "centro":
            pyautogui.moveTo(largura // 2, altura // 2, duration=self.duracao)
            return "Mouse movido para o centro."

        delta = self._delta_direcao(direcao)
        if not delta:
            return f"Não conheço a direção '{direcao}'."

        x, y = pyautogui.position()
        novo_x = min(max(0, x + delta[0]), largura - 1)
        novo_y = min(max(0, y + delta[1]), altura - 1)

        pyautogui.moveTo(novo_x, novo_y, duration=self.duracao)
        return f"Mouse movido para {direcao}."

    def arrastar_mouse(self, direcao):
        if not direcao:
            return "Entendi que você quer arrastar o mouse. Para qual lado?"

        largura, altura = pyautogui.size()

        if direcao == "centro":
            destino = (largura // 2, altura // 2)
        else:
            delta = self._delta_direcao(direcao)
            if not delta:
                return f"Não conheço a direção '{direcao}'."
            x, y = pyautogui.position()
            destino = (
                min(max(0, x + delta[0]), largura - 1),
                min(max(0, y + delta[1]), altura - 1),
            )

        pyautogui.mouseDown()
        try:
            pyautogui.moveTo(*destino, duration=max(self.duracao, 0.15))
        finally:
            pyautogui.mouseUp()

        return f"Mouse arrastado para {direcao}."

    def posicao_mouse(self):
        x, y = pyautogui.position()
        return f"O mouse está em {x} por {y}."

    def presenca(self):
        return "Presença confirmada."

    def clique(self, botao):
        if botao == "direito":
            pyautogui.rightClick()
        elif botao == "duplo":
            pyautogui.doubleClick()
        else:
            pyautogui.click()
        return "Clique realizado."

    def scroll(self, direcao):
        quantidade = 500 if direcao == "cima" else -500
        pyautogui.scroll(quantidade)
        return f"Página rolada para {direcao or 'baixo'}."

    # -----------------------------------------------------------
    # TECLADO
    # -----------------------------------------------------------
    def copiar(self):
        pyautogui.hotkey("ctrl", "c")
        return "Copiado."

    def colar(self):
        pyautogui.hotkey("ctrl", "v")
        return "Colado."

    def recortar(self):
        pyautogui.hotkey("ctrl", "x")
        return "Recortado."

    def desfazer(self):
        pyautogui.hotkey("ctrl", "z")
        return "Desfeito."

    def refazer(self):
        pyautogui.hotkey("ctrl", "y")
        return "Refeito."

    def selecionar_tudo(self):
        pyautogui.hotkey("ctrl", "a")
        return "Tudo selecionado."

    def enter(self):
        pyautogui.press("enter")
        return "Enter pressionado."

    def esc(self):
        pyautogui.press("esc")
        return "Escape pressionado."

    def tab(self):
        pyautogui.press("tab")
        return "Tab pressionado."

    def backspace(self):
        pyautogui.press("backspace")
        return "Apagado."

    def digitar(self, texto):
        if not texto:
            return "Não entendi o que você quer que eu digite."
        pyautogui.write(texto, interval=0.01)
        return "Texto digitado."

    # -----------------------------------------------------------
    # JANELAS
    # -----------------------------------------------------------
    def minimizar_janela(self):
        pyautogui.hotkey("win", "down")
        return "Janela minimizada."

    def maximizar_janela(self):
        pyautogui.hotkey("win", "up")
        return "Janela maximizada."

    def fechar_janela(self):
        pyautogui.hotkey("alt", "f4")
        return "Janela fechada."

    def alternar_janela(self):
        pyautogui.hotkey("alt", "tab")
        return "Alternando janela."

    def mostrar_area_trabalho(self):
        pyautogui.hotkey("win", "d")
        return "Área de trabalho exibida."

    # -----------------------------------------------------------
    # VOLUME
    # -----------------------------------------------------------
    def volume_aumentar(self):
        for _ in range(3):
            pyautogui.press("volumeup")
        return "Volume aumentado."

    def volume_diminuir(self):
        for _ in range(3):
            pyautogui.press("volumedown")
        return "Volume diminuído."

    def volume_mudo(self):
        pyautogui.press("volumemute")
        return "Som silenciado."

    # -----------------------------------------------------------
    # ENERGIA DO COMPUTADOR (ações sensíveis — confirmadas pelo router
    # antes de chegar aqui; sempre com atraso e opção de cancelar)
    # -----------------------------------------------------------
    def desligar_computador(self, atraso_segundos=60):
        subprocess.run(
            ["shutdown", "/s", "/t", str(atraso_segundos)],
            capture_output=True,
            text=True,
        )
        return (
            f"Desligando o computador em {atraso_segundos} segundos. "
            "Diga 'cancelar desligamento' para interromper."
        )

    def reiniciar_computador(self, atraso_segundos=60):
        subprocess.run(
            ["shutdown", "/r", "/t", str(atraso_segundos)],
            capture_output=True,
            text=True,
        )
        return (
            f"Reiniciando o computador em {atraso_segundos} segundos. "
            "Diga 'cancelar desligamento' para interromper."
        )

    def cancelar_desligamento(self):
        resultado = subprocess.run(
            ["shutdown", "/a"],
            capture_output=True,
            text=True,
        )
        if resultado.returncode == 0:
            return "Desligamento cancelado."
        return "Não havia nenhum desligamento agendado."

    # -----------------------------------------------------------
    # TECLAS AVULSAS E ATALHOS
    # -----------------------------------------------------------
    def pressionar_tecla(self, tecla):
        if not tecla:
            return "Não entendi qual tecla pressionar."
        pyautogui.press(tecla)
        return f"Tecla {tecla} pressionada."

    def atalho(self, teclas):
        if not teclas:
            return "Não entendi qual atalho usar."
        pyautogui.hotkey(*teclas)
        return "Atalho executado."

    # -----------------------------------------------------------
    # ARQUIVOS E PASTAS
    # -----------------------------------------------------------
    def _procurar_em_pastas_conhecidas(self, nome_normalizado, apenas_pastas):
        for base in PASTAS_CONHECIDAS.values():
            if not os.path.isdir(base):
                continue
            try:
                itens = os.listdir(base)
            except OSError:
                continue
            for item in itens:
                caminho = os.path.join(base, item)
                eh_pasta = os.path.isdir(caminho)
                if eh_pasta != apenas_pastas:
                    continue
                if nome_normalizado in item.lower():
                    return caminho, item
        return None, None

    def abrir_pasta(self, nome):
        if not nome:
            return "Não entendi qual pasta você quer abrir."

        if os.path.isdir(nome):
            os.startfile(nome)
            return f"Pasta {nome} aberta."

        nome_normalizado = nome.strip().lower()
        caminho_conhecido = PASTAS_CONHECIDAS.get(nome_normalizado)
        if caminho_conhecido and os.path.isdir(caminho_conhecido):
            os.startfile(caminho_conhecido)
            return f"Abri a pasta {nome}."

        caminho, item = self._procurar_em_pastas_conhecidas(nome_normalizado, apenas_pastas=True)
        if caminho:
            os.startfile(caminho)
            return f"Abri a pasta {item}."

        return f"Não encontrei a pasta '{nome}'."

    def abrir_arquivo(self, nome):
        if not nome:
            return "Não entendi qual arquivo você quer abrir."

        if os.path.isfile(nome):
            os.startfile(nome)
            return f"Arquivo {nome} aberto."

        nome_normalizado = nome.strip().lower()
        caminho, item = self._procurar_em_pastas_conhecidas(nome_normalizado, apenas_pastas=False)
        if caminho:
            os.startfile(caminho)
            return f"Abri o arquivo {item}."

        return f"Não encontrei o arquivo '{nome}'."

    # -----------------------------------------------------------
    # AÇÕES ORIENTADAS A ELEMENTOS (delegadas ao FormFiller)
    # -----------------------------------------------------------
    def _delegar_form_filler(self, metodo, *args):
        if self.form_filler is None:
            return "Recurso de localização de elementos na tela não está disponível."
        try:
            funcao = getattr(self.form_filler, metodo)
            return funcao(*args)
        except Exception as erro:
            return f"Não consegui: {erro}"

    # -----------------------------------------------------------
    # PROGRAMAS
    # -----------------------------------------------------------
    def abrir(self, programa):
        if not programa:
            return "Não entendi qual programa você quer abrir."

        exe = PROGRAMAS_ABRIR.get(programa)
        if not exe:
            return f"Ainda não tenho permissão configurada para abrir {programa}."

        try:
            subprocess.Popen(exe, shell=True)
            return f"{programa} aberto."
        except Exception as erro:
            return f"Não consegui abrir {programa}: {erro}"

    def fechar(self, programa):
        if not programa:
            return "Não entendi qual programa você quer fechar."

        nomes = PROGRAMAS_FECHAR.get(programa)
        if not nomes:
            return f"Ainda não tenho o comando para fechar {programa}."

        encontrado = False
        for processo in psutil.process_iter(["name"]):
            try:
                nome = processo.info["name"]
                if nome and nome.lower() in [n.lower() for n in nomes]:
                    processo.terminate()
                    encontrado = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if encontrado:
            return f"{programa} fechado."
        return f"{programa} não está aberto."

    # -----------------------------------------------------------
    # DISPATCH
    # -----------------------------------------------------------
    def executar(self, intent):
        kind = intent.get("intent")

        if not intencao_permitida(kind):
            return "Comando não reconhecido."

        if kind == "SAIR":
            return SAIR

        if kind == "INICIAR_ATENDIMENTO":
            return INICIAR_ATENDIMENTO_SINAL

        if kind == "ENCERRAR_ATENDIMENTO":
            return ENCERRAR_ATENDIMENTO_SINAL

        if kind == "MOVER_MOUSE":
            return self.mover_mouse(intent.get("direcao"))

        if kind == "ARRASTAR_MOUSE":
            return self.arrastar_mouse(intent.get("direcao"))

        if kind == "POSICAO_MOUSE":
            return self.posicao_mouse()

        if kind == "PRESENCA":
            return self.presenca()

        if kind in CONVERSA_INTENTS:
            return "Conversa reconhecida."

        if kind == "ATIVAR_MODO_PESSOAL":
            return "Modo pessoal ativado."

        if kind == "ATIVAR_MODO_ATENDIMENTO":
            return "Modo atendimento ativado."

        if kind == "ATIVAR_MODO_PRIVACIDADE":
            return "Modo privacidade ativado. Vou parar de responder a comandos por voz."

        if kind == "CLIQUE":
            return self.clique(intent.get("botao", "esquerdo"))

        if kind == "SCROLL":
            return self.scroll(intent.get("direcao"))

        if kind == "COPIAR":
            return self.copiar()

        if kind == "COLAR":
            return self.colar()

        if kind == "RECORTAR":
            return self.recortar()

        if kind == "DESFAZER":
            return self.desfazer()

        if kind == "REFAZER":
            return self.refazer()

        if kind == "SELECIONAR_TUDO":
            return self.selecionar_tudo()

        if kind == "ENTER":
            return self.enter()

        if kind == "ESC":
            return self.esc()

        if kind == "TAB":
            return self.tab()

        if kind == "BACKSPACE":
            return self.backspace()

        if kind == "DIGITAR":
            return self.digitar(intent.get("texto"))

        if kind == "MINIMIZAR_JANELA":
            return self.minimizar_janela()

        if kind == "MAXIMIZAR_JANELA":
            return self.maximizar_janela()

        if kind == "FECHAR_JANELA":
            return self.fechar_janela()

        if kind == "ALTERNAR_JANELA":
            return self.alternar_janela()

        if kind == "MOSTRAR_AREA_TRABALHO":
            return self.mostrar_area_trabalho()

        if kind == "VOLUME_AUMENTAR":
            return self.volume_aumentar()

        if kind == "VOLUME_DIMINUIR":
            return self.volume_diminuir()

        if kind == "VOLUME_MUDO":
            return self.volume_mudo()

        if kind == "DESLIGAR_COMPUTADOR":
            return self.desligar_computador()

        if kind == "REINICIAR_COMPUTADOR":
            return self.reiniciar_computador()

        if kind == "CANCELAR_DESLIGAMENTO":
            return self.cancelar_desligamento()

        if kind == "ABRIR":
            return self.abrir(intent.get("programa"))

        if kind == "FECHAR":
            return self.fechar(intent.get("programa"))

        if kind == "ABRIR_ARQUIVO":
            return self.abrir_arquivo(intent.get("nome"))

        if kind == "ABRIR_PASTA":
            return self.abrir_pasta(intent.get("nome"))

        if kind == "PRESSIONAR_TECLA":
            return self.pressionar_tecla(intent.get("tecla"))

        if kind == "ATALHO":
            return self.atalho(intent.get("teclas"))

        if kind == "PREENCHER_CAMPO":
            return self._delegar_form_filler(
                "preencher_texto", intent.get("campo"), intent.get("valor")
            )

        if kind == "CLICAR_ELEMENTO":
            return self._delegar_form_filler("clicar_botao", intent.get("nome"))

        if kind == "MARCAR_CAIXA":
            return self._delegar_form_filler(
                "marcar_checkbox", intent.get("campo"), intent.get("marcar", True)
            )

        if kind == "SELECIONAR_OPCAO":
            return self._delegar_form_filler(
                "selecionar_opcao", intent.get("campo"), intent.get("opcao")
            )

        if kind == "LOCALIZAR":
            return self._delegar_form_filler("localizar", intent.get("alvo"))

        return "Comando não reconhecido."
