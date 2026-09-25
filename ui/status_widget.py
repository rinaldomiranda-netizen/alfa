"""
Indicador visual permanente e discreto do estado da BETA.

A interface usa itens persistentes do Canvas: ela nunca apaga e recria
a tela a cada ciclo. Isso evita o efeito de "lanterna" / piscada causado
por apagar o Canvas inteiro a cada 50 ms.
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
        self.raiz.overrideredirect(True)
        self.raiz.attributes("-topmost", True)
        try:
            self.raiz.attributes("-alpha", 0.92)
        except Exception:
            pass

        largura_tela = self.raiz.winfo_screenwidth()
        altura_tela = self.raiz.winfo_screenheight()
        x = largura_tela - LARGURA - 24
        y = altura_tela - ALTURA - 90
        self.raiz.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")
        self.raiz.configure(bg="#111827")

        self.canvas = tk.Canvas(
            self.raiz,
            width=LARGURA,
            height=ALTURA,
            bg="#111827",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._t0 = time.monotonic()
        self._itens = self._criar_itens()
        self._ultimo_estado = None
        self._ultimo_detalhe = None

        self.raiz.after(0, self._impedir_roubo_de_foco)
        self._tick()

    def _criar_itens(self):
        cx, cy, raio = 27, 30, 12

        return {
            "outer": self.canvas.create_oval(
                cx - raio, cy - raio, cx + raio, cy + raio,
                outline="#6b7280", width=2,
            ),
            "inner": self.canvas.create_oval(
                cx - raio, cy - raio, cx + raio, cy + raio,
                outline="#6b7280", width=2,
            ),
            "arc": self.canvas.create_arc(
                cx - raio, cy - raio, cx + raio, cy + raio,
                start=0, extent=0, style="arc", outline="#f59e0b", width=3,
            ),
            "fill_circle": self.canvas.create_oval(
                cx - raio, cy - raio, cx + raio, cy + raio,
                fill="#3b82f6", outline="#3b82f6",
            ),
            "error": self.canvas.create_text(
                cx, cy, text="!", fill="white",
                font=("Segoe UI", 10, "bold"),
            ),
            "title": self.canvas.create_text(
                58, 16, anchor="w", text="BETA",
                fill="#f9fafb", font=("Segoe UI", 10, "bold"),
            ),
            "label": self.canvas.create_text(
                58, 34, anchor="w", text="aguardando",
                fill="#6b7280", font=("Segoe UI", 9),
            ),
            "bar_outline": self.canvas.create_rectangle(
                52, 54, 144, 62, outline="#374151",
            ),
            "bar_fill": self.canvas.create_rectangle(
                52, 54, 52, 62, fill="#22c55e", outline="#22c55e",
            ),
            "spokes": [
                self.canvas.create_line(
                    cx, cy, cx, cy, fill="#a855f7", width=2
                )
                for _ in range(6)
            ],
        }

    def _set_visible(self, item_id, visible):
        self.canvas.itemconfigure(
            item_id,
            state=tk.NORMAL if visible else tk.HIDDEN,
        )

    def _impedir_roubo_de_foco(self):
        if not _WIN32_OK:
            return
        try:
            hwnd = self.raiz.winfo_id()
            estilo_atual = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            novo_estilo = (
                estilo_atual
                | win32con.WS_EX_NOACTIVATE
                | win32con.WS_EX_TOOLWINDOW
            )
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, novo_estilo)
        except Exception:
            pass

    def _tick(self):
        estado, nivel_mic, detalhe, _ = estado_beta.obter()
        try:
            self._desenhar(estado, nivel_mic, detalhe)
        except tk.TclError:
            return
        self.raiz.after(INTERVALO_TICK_MS, self._tick)

    def _desenhar(self, estado, nivel_mic, detalhe=""):
        cor = CORES.get(estado, CORES[EstadoBeta.IDLE])
        rotulo = ROTULOS.get(estado, "")
        if detalhe:
            rotulo = f"{rotulo} ({detalhe})" if rotulo else detalhe

        cx, cy, raio_base = 27, 30, 12
        t = time.monotonic() - self._t0
        itens = self._itens

        # Texto/cores são atualizados sem destruir nenhum item.
        self.canvas.itemconfigure(itens["label"], text=rotulo, fill=cor)

        for nome in ("outer", "inner", "arc", "fill_circle", "error", "bar_outline", "bar_fill"):
            self._set_visible(itens[nome], False)
        for linha in itens["spokes"]:
            self._set_visible(linha, False)

        # Estado parado / espera.
        if estado in (EstadoBeta.IDLE, EstadoBeta.STANDBY):
            self.canvas.itemconfigure(itens["inner"], outline=cor, width=2)
            self._set_visible(itens["inner"], True)

        elif estado == EstadoBeta.LISTENING:
            pulso = (math.sin(t * 4.0) + 1) / 2
            raio_externo = raio_base + 4 * pulso

            self.canvas.coords(
                itens["outer"],
                cx - raio_externo, cy - raio_externo,
                cx + raio_externo, cy + raio_externo,
            )
            self.canvas.itemconfigure(itens["outer"], outline=cor, width=2)
            self.canvas.itemconfigure(itens["inner"], outline=cor, width=2)
            self._set_visible(itens["outer"], True)
            self._set_visible(itens["inner"], True)

            largura_barra = 92
            preenchido = max(
                0,
                min(largura_barra, int(largura_barra * nivel_mic)),
            )
            self.canvas.coords(
                itens["bar_fill"],
                52, 54, 52 + preenchido, 62,
            )
            self.canvas.itemconfigure(
                itens["bar_fill"], fill=cor, outline=cor,
            )
            self._set_visible(itens["bar_outline"], True)
            self._set_visible(itens["bar_fill"], preenchido > 0)

        elif estado in (EstadoBeta.PROCESSING, EstadoBeta.PLANNING):
            angulo = (t * 220) % 360
            self.canvas.itemconfigure(
                itens["inner"], outline="#374151", width=2
            )
            self.canvas.itemconfigure(
                itens["arc"],
                start=angulo,
                extent=100,
                outline=cor,
                width=3,
            )
            self._set_visible(itens["inner"], True)
            self._set_visible(itens["arc"], True)

        elif estado == EstadoBeta.SPEAKING:
            self.canvas.itemconfigure(
                itens["fill_circle"], fill=cor, outline=cor
            )
            self._set_visible(itens["fill_circle"], True)

        elif estado in (EstadoBeta.WORKING, EstadoBeta.EXECUTING):
            angulo_base = (t * 140) % 360
            for i, linha in enumerate(itens["spokes"]):
                a = math.radians(angulo_base + i * 60)
                x1 = cx + 6 * math.cos(a)
                y1 = cy + 6 * math.sin(a)
                x2 = cx + raio_base * math.cos(a)
                y2 = cy + raio_base * math.sin(a)
                self.canvas.coords(linha, x1, y1, x2, y2)
                self.canvas.itemconfigure(linha, fill=cor, width=2)
                self._set_visible(linha, True)

        elif estado == EstadoBeta.ATIVANDO:
            # Estado de ativação fica estável: sem "flash" intencional.
            self.canvas.itemconfigure(itens["inner"], outline=cor, width=3)
            self._set_visible(itens["inner"], True)

        elif estado == EstadoBeta.ERROR:
            self.canvas.itemconfigure(
                itens["fill_circle"], fill=cor, outline=cor
            )
            self.canvas.itemconfigure(itens["error"], fill="white", text="!")
            self._set_visible(itens["fill_circle"], True)
            self._set_visible(itens["error"], True)

        self._ultimo_estado = estado
        self._ultimo_detalhe = detalhe

    def run(self):
        self.raiz.mainloop()


def iniciar_em_thread():
    """Inicia o indicador numa thread daemon sem bloquear o ALFA."""

    def _executar():
        try:
            widget = StatusWidget()
            widget.run()
        except Exception as erro:
            print(f"[BETA UI] Indicador visual indisponível: {erro}")

    thread = threading.Thread(
        target=_executar,
        name="BetaStatusWidget",
        daemon=True,
    )
    thread.start()
    return thread
