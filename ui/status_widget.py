"""
Indicador visual permanente e discreto do estado da BETA — uma
janelinha pequena, sempre no topo, próxima ao canto da tela (perto da
bandeja do sistema), que NUNCA rouba o foco de outras janelas.

Reflete SOMENTE o estado real publicado em ui/estado_beta.py — se
ninguém atualizar o estado, o desenho simplesmente não muda. O nível
de microfone mostrado durante LISTENING vem do RMS real medido em
voice/voice_engine.py, nunca de uma animação inventada.

Roda em uma thread própria (ver iniciar_em_thread()): o laço de voz da
BETA continua ocupando a thread principal como sempre — este módulo
não altera em nada a lógica de pesquisa, câmera, atendimento ou voz,
só desenha o que já está acontecendo.
"""

import math
import threading
import time
import tkinter as tk

from ui.estado_beta import EstadoBeta, estado_beta

try:
    import win32con
    import win32gui
    _WIN32_OK = True
except Exception:
    _WIN32_OK = False

CORES = {
    EstadoBeta.IDLE: "#6b7280",
    EstadoBeta.STANDBY: "#4b5563",
    EstadoBeta.ATIVANDO: "#eab308",
    EstadoBeta.LISTENING: "#22c55e",
    EstadoBeta.PROCESSING: "#f59e0b",
    EstadoBeta.SPEAKING: "#3b82f6",
    EstadoBeta.WORKING: "#a855f7",
    EstadoBeta.ERROR: "#ef4444",
    # Agente de computador (ver agente/orquestrador.py) — PLANNING
    # reaproveita a cor/animação de PROCESSING, EXECUTING a de WORKING
    # (ver _desenhar abaixo): conceitualmente é a mesma coisa, só com
    # granularidade de etapa.
    EstadoBeta.PLANNING: "#f59e0b",
    EstadoBeta.EXECUTING: "#a855f7",
}

ROTULOS = {
    EstadoBeta.IDLE: "aguardando",
    EstadoBeta.STANDBY: "em espera (diga 'Beta')",
    EstadoBeta.ATIVANDO: "ativando...",
    EstadoBeta.LISTENING: "ouvindo...",
    EstadoBeta.PROCESSING: "processando...",
    EstadoBeta.SPEAKING: "falando...",
    EstadoBeta.WORKING: "trabalhando...",
    EstadoBeta.ERROR: "problema",
    EstadoBeta.PLANNING: "planejando...",
    EstadoBeta.EXECUTING: "executando",
}

LARGURA, ALTURA = 156, 78
INTERVALO_TICK_MS = 50


class StatusWidget:
    def __init__(self):
        self.raiz = tk.Tk()
        self.raiz.title("BETA")
        self.raiz.overrideredirect(True)  # sem borda/barra de título
        self.raiz.attributes("-topmost", True)
        try:
            self.raiz.attributes("-alpha", 0.92)
        except Exception:
            pass

        largura_tela = self.raiz.winfo_screenwidth()
        altura_tela = self.raiz.winfo_screenheight()
        x = largura_tela - LARGURA - 24
        y = altura_tela - ALTURA - 90  # acima da barra de tarefas
        self.raiz.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")
        self.raiz.configure(bg="#111827")

        self.canvas = tk.Canvas(
            self.raiz, width=LARGURA, height=ALTURA, bg="#111827",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._t0 = time.monotonic()

        # Só depois que a janela existe de verdade é que dá pra pegar
        # o HWND e aplicar o estilo "nunca ativar" do Windows.
        self.raiz.after(0, self._impedir_roubo_de_foco)
        self._tick()

    def _impedir_roubo_de_foco(self):
        """
        WS_EX_NOACTIVATE: a janela pode aparecer por cima, mas nunca
        recebe foco de teclado. WS_EX_TOOLWINDOW: some do Alt+Tab e da
        barra de tarefas. Sem isso, uma Toplevel do Tkinter, mesmo com
        overrideredirect, ainda pode roubar o foco da janela ativa ao
        ser criada/atualizada.
        """
        if not _WIN32_OK:
            return
        try:
            hwnd = self.raiz.winfo_id()
            estilo_atual = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            novo_estilo = estilo_atual | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, novo_estilo)
        except Exception:
            pass

    def _tick(self):
        estado, nivel_mic, detalhe, _ = estado_beta.obter()
        try:
            self._desenhar(estado, nivel_mic, detalhe)
        except tk.TclError:
            return  # janela foi fechada
        self.raiz.after(INTERVALO_TICK_MS, self._tick)

    def _desenhar(self, estado, nivel_mic, detalhe=""):
        self.canvas.delete("all")
        cor = CORES.get(estado, CORES[EstadoBeta.IDLE])
        rotulo = ROTULOS.get(estado, "")
        if detalhe:
            rotulo = f"{rotulo} ({detalhe})" if rotulo else detalhe

        cx, cy, raio_base = 27, 30, 12
        t = time.monotonic() - self._t0

        if estado == EstadoBeta.LISTENING:
            # Pulso suave (0..1) em torno do círculo — só aparece
            # quando a BETA está mesmo com o microfone aberto.
            pulso = (math.sin(t * 4.0) + 1) / 2
            raio_externo = raio_base + 6 * pulso
            self.canvas.create_oval(
                cx - raio_externo, cy - raio_externo,
                cx + raio_externo, cy + raio_externo,
                outline=cor, width=2,
            )
            self.canvas.create_oval(
                cx - raio_base, cy - raio_base, cx + raio_base, cy + raio_base,
                outline=cor, width=2,
            )
        elif estado in (EstadoBeta.PROCESSING, EstadoBeta.PLANNING):
            angulo = (t * 220) % 360
            self.canvas.create_oval(
                cx - raio_base, cy - raio_base, cx + raio_base, cy + raio_base,
                outline="#374151", width=2,
            )
            self.canvas.create_arc(
                cx - raio_base, cy - raio_base, cx + raio_base, cy + raio_base,
                start=angulo, extent=100, style="arc", outline=cor, width=3,
            )
        elif estado == EstadoBeta.SPEAKING:
            self.canvas.create_oval(
                cx - raio_base, cy - raio_base, cx + raio_base, cy + raio_base,
                fill=cor, outline=cor,
            )
        elif estado in (EstadoBeta.WORKING, EstadoBeta.EXECUTING):
            angulo_base = (t * 140) % 360
            for i in range(6):
                a = math.radians(angulo_base + i * 60)
                x1 = cx + 6 * math.cos(a)
                y1 = cy + 6 * math.sin(a)
                x2 = cx + raio_base * math.cos(a)
                y2 = cy + raio_base * math.sin(a)
                self.canvas.create_line(x1, y1, x2, y2, fill=cor, width=2)
        elif estado == EstadoBeta.ATIVANDO:
            # Flash breve (a palavra de ativação/presença acabou de
            # ser confirmada) — bem mais rápido que o pulso de
            # LISTENING, para não parecer a mesma animação.
            pulso = (math.sin(t * 10.0) + 1) / 2
            raio_flash = raio_base + 4 * pulso
            self.canvas.create_oval(
                cx - raio_flash, cy - raio_flash, cx + raio_flash, cy + raio_flash,
                outline=cor, width=3,
            )
        elif estado == EstadoBeta.ERROR:
            self.canvas.create_oval(
                cx - raio_base, cy - raio_base, cx + raio_base, cy + raio_base,
                fill=cor, outline=cor,
            )
            self.canvas.create_text(
                cx, cy, text="!", fill="white", font=("Segoe UI", 10, "bold"),
            )
        else:  # IDLE
            self.canvas.create_oval(
                cx - raio_base, cy - raio_base, cx + raio_base, cy + raio_base,
                outline=cor, width=2,
            )

        self.canvas.create_text(
            58, 16, anchor="w", text="BETA", fill="#f9fafb",
            font=("Segoe UI", 10, "bold"),
        )
        self.canvas.create_text(
            58, 34, anchor="w", text=rotulo, fill=cor,
            font=("Segoe UI", 9),
        )

        if estado == EstadoBeta.LISTENING:
            largura_barra = 92
            self.canvas.create_rectangle(
                52, 54, 52 + largura_barra, 62, outline="#374151",
            )
            preenchido = max(0, min(largura_barra, int(largura_barra * nivel_mic)))
            if preenchido > 0:
                self.canvas.create_rectangle(
                    52, 54, 52 + preenchido, 62, fill=cor, outline=cor,
                )

    def run(self):
        self.raiz.mainloop()


def iniciar_em_thread():
    """
    Cria e roda o indicador visual numa thread própria (daemon), sem
    bloquear o laço principal de voz da BETA. Best-effort: se não for
    possível criar a janela (ex.: ambiente sem interface gráfica), a
    BETA continua funcionando normalmente, só sem o indicador.
    """

    def _executar():
        try:
            widget = StatusWidget()
            widget.run()
        except Exception as erro:
            print(f"[BETA UI] Indicador visual indisponível: {erro}")

    thread = threading.Thread(target=_executar, name="BetaStatusWidget", daemon=True)
    thread.start()
    return thread
