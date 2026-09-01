"""
Interface de TOTEM da BETA — FASE 1 da expansão de plataforma. Mesma
AlfaCore/BETA Core de sempre (voz, intents, skills, permissões,
Planner, Verifier) — nenhum cérebro duplicado; este módulo só
acrescenta uma camada visual em tela cheia pensada para atendimento a
visitantes num quiosque/recepção.

    tela inicial (parada, esperando "Beta" ou toque no botão)
        -> sessão (indicadores grandes: ouvindo/processando/falando)
        -> encerra sessão (timeout de inatividade)
        -> limpa contexto temporário (agente/contexto.py -> resetar_sessao)
        -> volta pra tela inicial

Roda a MESMA AlfaCore numa thread de fundo (core.run(), o laço de voz
de sempre) — a interface gráfica fica na thread principal, que é a
única forma segura de rodar Tkinter. Só reflete o estado real já
publicado em ui/estado_beta.py (o mesmo barramento que
ui/status_widget.py já usa) — nunca inventa uma animação
desconectada do que está de fato acontecendo.

Privacidade: nada do que um visitante diz fica retido depois da sessão
— o contexto temporário é limpo a cada timeout (ver
agente/contexto.py -> resetar_sessao). A identidade configurada
(nome da organização dona do totem) não é apagada: é dado de
configuração do terminal, não do visitante.

Sair do modo totem: Ctrl+Alt+Q (gesto deliberado — Esc sozinho não
sai, para não encerrar por engano).
"""

import os
import sys
import threading
import time
import tkinter as tk

BASE_PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_PROJETO not in sys.path:
    sys.path.insert(0, BASE_PROJETO)

from ui.estado_beta import EstadoBeta, estado_beta

CORES = {
    EstadoBeta.IDLE: "#374151",
    EstadoBeta.STANDBY: "#1f2937",
    EstadoBeta.ATIVANDO: "#eab308",
    EstadoBeta.LISTENING: "#22c55e",
    EstadoBeta.PROCESSING: "#f59e0b",
    EstadoBeta.SPEAKING: "#3b82f6",
    EstadoBeta.WORKING: "#a855f7",
    EstadoBeta.ERROR: "#ef4444",
    EstadoBeta.PLANNING: "#f59e0b",
    EstadoBeta.EXECUTING: "#a855f7",
}

ROTULOS = {
    EstadoBeta.IDLE: 'Toque no botão ou diga "Beta" para começar',
    EstadoBeta.STANDBY: 'Diga "Beta" para começar',
    EstadoBeta.ATIVANDO: "Já vou te ouvir...",
    EstadoBeta.LISTENING: "Estou ouvindo...",
    EstadoBeta.PROCESSING: "Um instante...",
    EstadoBeta.SPEAKING: "",
    EstadoBeta.WORKING: "Trabalhando nisso...",
    EstadoBeta.ERROR: "Algo deu errado, pode tentar de novo",
    EstadoBeta.PLANNING: "Pensando...",
    EstadoBeta.EXECUTING: "Executando...",
}

TIMEOUT_SESSAO_SEGUNDOS = 45
INTERVALO_TICK_MS = 100


class TotemApp:
    def __init__(self, core, titulo="BETA"):
        """`core` é uma instância JÁ CONSTRUÍDA de core.alfa_core.AlfaCore
        — nunca cria um motor de voz/intenção próprio."""
        self.core = core
        self.titulo = titulo
        self._alto_contraste = True
        self._escala_fonte = 1.0
        self._em_sessao = False
        self._ultima_atividade = time.monotonic()
        self._thread_voz = None

        self.raiz = tk.Tk()
        self.raiz.title(titulo)
        try:
            self.raiz.attributes("-fullscreen", True)
        except Exception:
            self.raiz.geometry("1024x768")
        self.raiz.configure(bg="#000000")
        self.raiz.bind("<Control-Alt-KeyPress-q>", lambda _evt: self._sair())

        self.canvas = tk.Canvas(self.raiz, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._ao_tocar_na_tela)

        barra = tk.Frame(self.raiz, bg="#000000")
        barra.place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=20)
        tk.Button(barra, text="A+", command=self._aumentar_fonte, font=("Segoe UI", 16, "bold"), width=3).pack(side="left", padx=4)
        tk.Button(barra, text="A-", command=self._diminuir_fonte, font=("Segoe UI", 16, "bold"), width=3).pack(side="left", padx=4)
        tk.Button(barra, text="Contraste", command=self._alternar_contraste, font=("Segoe UI", 12)).pack(side="left", padx=4)

        self._tick()

    # ------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------

    def iniciar_voz_em_thread(self):
        """Roda o laço de voz de sempre (core.run()) numa thread de
        fundo — Tkinter precisa ficar na thread principal."""
        def _executar():
            try:
                self.core.run()
            except Exception as erro:
                print(f"[TOTEM] Laço de voz encerrado: {erro}")

        self._thread_voz = threading.Thread(target=_executar, name="TotemVoz", daemon=True)
        self._thread_voz.start()

    def _ao_tocar_na_tela(self, _evento):
        """Botão/toque alternativo à voz para começar uma sessão (item
        do pedido: "botão/controle de início") — só ativa quando ainda
        está no repouso (não interrompe uma sessão em andamento nem
        interfere com o barge-in, que já cobre "falar por cima")."""
        estado, _nivel, _detalhe, _t = estado_beta.obter()
        if estado in (EstadoBeta.IDLE, EstadoBeta.STANDBY):
            self.core._modo_escuta = "active"

    def _sair(self):
        print("[TOTEM] Saindo do modo totem (Ctrl+Alt+Q).")
        try:
            self.raiz.destroy()
        except Exception:
            pass

    def run(self):
        self.raiz.mainloop()

    # ------------------------------------------------------------
    # Acessibilidade
    # ------------------------------------------------------------

    def _aumentar_fonte(self):
        self._escala_fonte = min(2.0, self._escala_fonte + 0.15)

    def _diminuir_fonte(self):
        self._escala_fonte = max(0.7, self._escala_fonte - 0.15)

    def _alternar_contraste(self):
        self._alto_contraste = not self._alto_contraste

    # ------------------------------------------------------------
    # Sessão / privacidade
    # ------------------------------------------------------------

    def _tick(self):
        estado, nivel_mic, detalhe, _atualizado_em = estado_beta.obter()

        em_sessao_agora = estado not in (EstadoBeta.IDLE, EstadoBeta.STANDBY)
        if em_sessao_agora:
            self._em_sessao = True
            self._ultima_atividade = time.monotonic()
        elif self._em_sessao and (time.monotonic() - self._ultima_atividade) > TIMEOUT_SESSAO_SEGUNDOS:
            self._encerrar_sessao()

        try:
            self._desenhar(estado, nivel_mic, detalhe)
        except tk.TclError:
            return  # janela foi fechada
        self.raiz.after(INTERVALO_TICK_MS, self._tick)

    def _encerrar_sessao(self):
        print("[TOTEM] Sessão encerrada por inatividade — limpando contexto temporário.")
        self._em_sessao = False
        try:
            self.core.contexto.resetar_sessao()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Desenho
    # ------------------------------------------------------------

    def _desenhar(self, estado, nivel_mic, detalhe):
        self.canvas.delete("all")
        largura = self.raiz.winfo_width() or self.raiz.winfo_screenwidth()
        altura = self.raiz.winfo_height() or self.raiz.winfo_screenheight()
        cx, cy = largura // 2, altura // 2

        fundo = "#000000" if self._alto_contraste else "#0f172a"
        cor_texto = "#ffffff" if self._alto_contraste else "#e5e7eb"
        cor_estado = CORES.get(estado, CORES[EstadoBeta.IDLE])
        self.canvas.configure(bg=fundo)

        tamanho_titulo = int(48 * self._escala_fonte)
        tamanho_status = int(28 * self._escala_fonte)

        self.canvas.create_text(
            cx, cy - 160, text=self.titulo, fill=cor_texto,
            font=("Segoe UI", tamanho_titulo, "bold"),
        )

        raio = 80 if estado in (EstadoBeta.LISTENING, EstadoBeta.SPEAKING) else 60
        self.canvas.create_oval(cx - raio, cy - raio, cx + raio, cy + raio, outline=cor_estado, width=6)

        rotulo = ROTULOS.get(estado, "")
        if detalhe:
            rotulo = f"{rotulo} ({detalhe})" if rotulo else detalhe
        if rotulo:
            self.canvas.create_text(
                cx, cy + 130, text=rotulo, fill=cor_estado,
                font=("Segoe UI", tamanho_status), width=largura - 100,
            )

        if estado == EstadoBeta.LISTENING:
            largura_barra = 340
            y0, y1 = cy + 180, cy + 202
            self.canvas.create_rectangle(cx - largura_barra // 2, y0, cx + largura_barra // 2, y1, outline=cor_texto)
            preenchido = max(0, min(largura_barra, int(largura_barra * nivel_mic)))
            if preenchido > 0:
                self.canvas.create_rectangle(cx - largura_barra // 2, y0, cx - largura_barra // 2 + preenchido, y1, fill=cor_estado, outline=cor_estado)

        if estado in (EstadoBeta.IDLE, EstadoBeta.STANDBY):
            botao_raio = 100
            self.canvas.create_oval(
                cx - botao_raio, cy + 240 - botao_raio, cx + botao_raio, cy + 240 + botao_raio,
                outline=cor_texto, width=3,
            )
            self.canvas.create_text(cx, cy + 240, text="TOQUE\nAQUI", fill=cor_texto, font=("Segoe UI", 18, "bold"), justify="center")

        self.canvas.create_text(cx, altura - 30, text="Modo Totem — Ctrl+Alt+Q para sair", fill="#6b7280", font=("Segoe UI", 12))


def _construir_config_totem(nome_organizacao=None):
    """Config genérico para o totem — reconhecimento facial desligado
    por padrão (é opcional, ver item do pedido), nunca herda nada do
    ALFA pessoal de Rinaldo nem de nenhum perfil portátil já salvo."""
    import copy

    from core.alfa_core import CONFIG_PADRAO
    from core.perfil import construir_perfil

    config = copy.deepcopy(CONFIG_PADRAO)
    nome = nome_organizacao or "Totem"
    config["personalidade"]["nome_usuario"] = nome
    config["personalidade"]["nome_assistente"] = "Beta"
    config["perfil"] = construir_perfil("organizacao", nome, terminal="totem")
    config["reconhecimento_facial"] = {"enabled": False, "indice_camera": 0}
    config["cloud"] = {"enabled": False, "project_url": None, "publishable_key": None}
    config["sync"] = {"enabled": False}
    return config


def main(nome_organizacao=None):
    from core.alfa_core import AlfaCore

    config = _construir_config_totem(nome_organizacao)
    core = AlfaCore(config=config)

    app = TotemApp(core, titulo=config["personalidade"]["nome_assistente"])
    app.iniciar_voz_em_thread()
    app.run()


if __name__ == "__main__":
    nome_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(nome_arg)
