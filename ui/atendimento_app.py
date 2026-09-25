"""Interface visual do RMD Atendimento integrada ao ALFA.

A aparência deste módulo segue a linguagem visual do ALFA sem alterar
qualquer janela, fluxo ou layout do ALFA principal.
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.atendimento.service import AtendimentoService
from core.roteiro_pesquisa import roteiro_nova_entrevista
from agente.skill_registry import SkillRegistry


# Identidade visual alinhada ao indicador BETA já usado pelo ALFA.
BG = "#0b1220"
PANEL = "#111827"
PANEL_2 = "#172033"
BORDER = "#273449"
TEXT = "#f9fafb"
MUTED = "#9ca3af"
ACCENT = "#22c55e"
BLUE = "#3b82f6"
YELLOW = "#f59e0b"
RED = "#ef4444"
FONT = "Segoe UI"


class AtendimentoApp:
    """Tela operacional do módulo RMD Atendimento.

    O módulo pode ser aberto pelo ALFA ou executado isoladamente.
    Nenhuma regra do atendimento é duplicada nesta camada.
    """

    def __init__(self, master, empresa_id="alpha-demo"):
        self.master = master
        self.empresa_id = empresa_id or "alpha-demo"
        self.master.title("ALFA — RMD Atendimento")
        self.master.geometry("1180x760")
        self.master.minsize(900, 620)
        self.master.configure(bg=BG)

        self.service = AtendimentoService()
        self.modulo = self.service.modulo

        self.status_var = tk.StringVar(value=f"Pronto · empresa: {self.empresa_id}")
        self.msg_var = tk.StringVar(value="")
        self.id_var = tk.StringVar(value="ID: —")
        self.modulos_var = tk.StringVar(value="Carregando módulos…")

        self._configurar_estilos()
        self._montar_shell()
        self._montar_cabecalho()
        self._montar_corpo()
        self._montar_rodape()

        self.atualizar_modulos()
        self.atualizar_historico()

    def _configurar_estilos(self):
        style = ttk.Style(self.master)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "ALFA.TFrame",
            background=BG,
        )
        style.configure(
            "Panel.TFrame",
            background=PANEL,
        )
        style.configure(
            "Sidebar.TFrame",
            background=PANEL,
        )
        style.configure(
            "ALFA.TLabel",
            background=BG,
            foreground=TEXT,
            font=(FONT, 10),
        )
        style.configure(
            "Title.TLabel",
            background=BG,
            foreground=TEXT,
            font=(FONT, 23, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=BG,
            foreground=MUTED,
            font=(FONT, 10),
        )
        style.configure(
            "PanelTitle.TLabel",
            background=PANEL,
            foreground=TEXT,
            font=(FONT, 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=PANEL,
            foreground=MUTED,
            font=(FONT, 9),
        )
        style.configure(
            "Module.TButton",
            background=PANEL_2,
            foreground=TEXT,
            borderwidth=0,
            padding=(10, 8),
            font=(FONT, 10, "bold"),
        )
        style.map(
            "Module.TButton",
            background=[("active", "#20304a")],
            foreground=[("active", TEXT)],
        )

    def _montar_shell(self):
        self.shell = tk.Frame(self.master, bg=BG)
        self.shell.pack(fill="both", expand=True, padx=16, pady=16)

        self.top = tk.Frame(self.shell, bg=BG)
        self.top.pack(fill="x")

        self.body = tk.Frame(self.shell, bg=BG)
        self.body.pack(fill="both", expand=True, pady=(14, 0))

        self.footer = tk.Frame(self.shell, bg=BG)
        self.footer.pack(fill="x", pady=(12, 0))

    def _montar_cabecalho(self):
        cab = tk.Frame(self.top, bg=BG)
        cab.pack(fill="x")

        marca = tk.Frame(cab, bg=BG)
        marca.pack(side="left", fill="x", expand=True)

        tk.Label(
            marca,
            text="RMD",
            bg=BG,
            fg=ACCENT,
            font=(FONT, 10, "bold"),
        ).pack(anchor="w")

        tk.Label(
            marca,
            text="Atendimento",
            bg=BG,
            fg=TEXT,
            font=(FONT, 24, "bold"),
        ).pack(anchor="w")

        tk.Label(
            marca,
            text="Módulo do ALFA · versão 5.1.1",
            bg=BG,
            fg=MUTED,
            font=(FONT, 10),
        ).pack(anchor="w")

        estado = tk.Frame(cab, bg=PANEL, padx=14, pady=9)
        estado.pack(side="right")

        tk.Label(
            estado,
            text="●",
            bg=PANEL,
            fg=ACCENT,
            font=(FONT, 14, "bold"),
        ).pack(side="left")

        tk.Label(
            estado,
            text=" MÓDULO ATIVO",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 9, "bold"),
        ).pack(side="left")

        tk.Label(
            self.top,
            textvariable=self.status_var,
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            padx=12,
            pady=8,
            font=(FONT, 9),
        ).pack(fill="x", pady=(12, 0))

    def _montar_corpo(self):
        sidebar = tk.Frame(self.body, bg=PANEL, width=230, padx=12, pady=14)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        content = tk.Frame(self.body, bg=BG)
        content.pack(side="left", fill="both", expand=True, padx=(14, 0))

        tk.Label(
            sidebar,
            text="MÓDULOS DO ALFA",
            bg=PANEL,
            fg=MUTED,
            font=(FONT, 9, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        self.lista_modulos = tk.Frame(sidebar, bg=PANEL)
        self.lista_modulos.pack(fill="x")

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", pady=14)

        tk.Label(
            sidebar,
            text="Contexto",
            bg=PANEL,
            fg=MUTED,
            font=(FONT, 9, "bold"),
        ).pack(anchor="w")

        tk.Label(
            sidebar,
            text="RMD Atendimento\nIntegrado ao ALFA\nTambém disponível\nem modo standalone",
            bg=PANEL,
            fg=TEXT,
            justify="left",
            font=(FONT, 10),
        ).pack(anchor="w", pady=(6, 0))

        # Área principal
        resumo = tk.Frame(content, bg=BG)
        resumo.pack(fill="x")

        self.card_status = self._card(resumo, "STATUS", "Pronto", ACCENT)
        self.card_status.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.card_id = self._card(resumo, "ATENDIMENTO", "—", BLUE)
        self.card_id.pack(side="left", fill="x", expand=True, padx=8)

        self.card_empresa = self._card(resumo, "EMPRESA", self.empresa_id, YELLOW)
        self.card_empresa.pack(side="left", fill="x", expand=True, padx=(8, 0))

        painel = tk.Frame(content, bg=PANEL, padx=14, pady=14)
        painel.pack(fill="both", expand=True, pady=(14, 0))

        conversa_col = tk.Frame(painel, bg=PANEL)
        conversa_col.pack(side="left", fill="both", expand=True)

        tk.Label(
            conversa_col,
            text="Conversa",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 12, "bold"),
        ).pack(anchor="w")

        tk.Label(
            conversa_col,
            text="Atendimento em execução pelo núcleo do ALFA",
            bg=PANEL,
            fg=MUTED,
            font=(FONT, 9),
        ).pack(anchor="w", pady=(2, 8))

        texto_frame = tk.Frame(conversa_col, bg=PANEL_2)
        texto_frame.pack(fill="both", expand=True)

        self.conversa = tk.Text(
            texto_frame,
            wrap="word",
            state="disabled",
            bg=PANEL_2,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#29456b",
            relief="flat",
            borderwidth=0,
            font=(FONT, 11),
            padx=14,
            pady=14,
        )
        self.conversa.pack(fill="both", expand=True)

        entrada = tk.Frame(conversa_col, bg=PANEL, pady=10)
        entrada.pack(fill="x")

        self.input = tk.Entry(
            entrada,
            bg="#0f172a",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=(FONT, 11),
        )
        self.input.pack(side="left", fill="x", expand=True, ipady=9)

        tk.Button(
            entrada,
            text="Enviar",
            command=self.enviar,
            bg=BLUE,
            fg="white",
            activebackground="#2563eb",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            font=(FONT, 10, "bold"),
            padx=18,
            pady=8,
        ).pack(side="left", padx=(8, 0))

        lateral = tk.Frame(painel, bg=PANEL, width=245, padx=(14, 0))
        lateral.pack(side="right", fill="y")
        lateral.pack_propagate(False)

        tk.Label(
            lateral,
            text="Histórico",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 12, "bold"),
        ).pack(anchor="w")

        tk.Label(
            lateral,
            text="Registros desta empresa",
            bg=PANEL,
            fg=MUTED,
            font=(FONT, 9),
        ).pack(anchor="w", pady=(2, 8))

        hist_frame = tk.Frame(lateral, bg=PANEL_2)
        hist_frame.pack(fill="both", expand=True)

        self.historico = tk.Listbox(
            hist_frame,
            activestyle="none",
            bg=PANEL_2,
            fg=TEXT,
            selectbackground="#29456b",
            selectforeground=TEXT,
            relief="flat",
            borderwidth=0,
            font=(FONT, 9),
        )
        self.historico.pack(fill="both", expand=True)
        self.historico.bind("<Double-Button-1>", self.abrir_historico)

        tk.Button(
            lateral,
            text="Atualizar histórico",
            command=self.atualizar_historico,
            bg=PANEL_2,
            fg=TEXT,
            activebackground="#20304a",
            activeforeground=TEXT,
            relief="flat",
            borderwidth=0,
            font=(FONT, 9, "bold"),
            pady=7,
        ).pack(fill="x", pady=(8, 0))

    def _card(self, parent, titulo, valor, acento):
        card = tk.Frame(parent, bg=PANEL, padx=12, pady=10, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(
            card,
            text=titulo,
            bg=PANEL,
            fg=MUTED,
            font=(FONT, 8, "bold"),
        ).pack(anchor="w")
        label = tk.Label(
            card,
            text=valor,
            bg=PANEL,
            fg=acento,
            font=(FONT, 12, "bold"),
        )
        label.pack(anchor="w", pady=(3, 0))
        card.value_label = label
        return card

    def _montar_rodape(self):
        botoes = tk.Frame(self.footer, bg=BG)
        botoes.pack(fill="x")

        self._botao_footer(botoes, "Novo atendimento", self.novo, ACCENT).pack(side="left")
        self._botao_footer(botoes, "Finalizar", self.finalizar, BLUE).pack(side="left", padx=(8, 0))
        self._botao_footer(botoes, "Limpar sessão", self.limpar, PANEL_2).pack(side="left", padx=(8, 0))
        self._botao_footer(botoes, "Status", self.mostrar_status, PANEL_2).pack(side="right")

        tk.Label(
            self.footer,
            textvariable=self.msg_var,
            bg=BG,
            fg=MUTED,
            font=(FONT, 8),
        ).pack(anchor="w", pady=(6, 0))

    def _botao_footer(self, parent, texto, comando, cor):
        return tk.Button(
            parent,
            text=texto,
            command=comando,
            bg=cor,
            fg="white",
            activebackground=cor,
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            font=(FONT, 9, "bold"),
            padx=14,
            pady=8,
        )

    def atualizar_modulos(self):
        for widget in self.lista_modulos.winfo_children():
            widget.destroy()

        try:
            registry = SkillRegistry()
            modulos = registry.listar()
        except Exception:
            modulos = []

        if not modulos:
            tk.Label(
                self.lista_modulos,
                text="Nenhum módulo registrado",
                bg=PANEL,
                fg=MUTED,
                justify="left",
                font=(FONT, 9),
            ).pack(anchor="w", pady=4)
            return

        for manifesto in modulos:
            ativo = "●" if registry.esta_ativa(manifesto.nome) else "○"
            texto = f"{ativo}  {manifesto.nome}"
            botao = tk.Button(
                self.lista_modulos,
                text=texto,
                command=lambda m=manifesto: self._mostrar_modulo(m),
                bg=PANEL if manifesto.nome != self.modulo.module_id else PANEL_2,
                fg=ACCENT if manifesto.nome == self.modulo.module_id else TEXT,
                activebackground=PANEL_2,
                activeforeground=TEXT,
                relief="flat",
                borderwidth=0,
                anchor="w",
                padx=8,
                pady=8,
                font=(FONT, 9, "bold" if manifesto.nome == self.modulo.module_id else "normal"),
            )
            botao.pack(fill="x", pady=2)

    def _mostrar_modulo(self, manifesto):
        self.msg_var.set(
            f"{manifesto.nome} · v{manifesto.versao} · {manifesto.autor} · "
            f"{'offline' if manifesto.offline else 'online'}"
        )

    def escrever(self, autor, texto):
        self.conversa.configure(state="normal")
        self.conversa.insert("end", f"{autor}: {texto}\n\n")
        self.conversa.see("end")
        self.conversa.configure(state="disabled")

    def novo(self):
        if self.modulo.ativo:
            return
        resposta = self.service.iniciar(self.empresa_id, roteiro_nova_entrevista())
        self.conversa.configure(state="normal")
        self.conversa.delete("1.0", "end")
        self.conversa.configure(state="disabled")
        self.escrever("BETA", resposta)
        status = self.modulo.status()
        self.id_var.set(f"ID: {status['atendimento_id'] or '—'}")
        self.status_var.set(f"Atendimento em andamento · empresa: {self.empresa_id}")
        self.card_status.value_label.config(text="Em andamento", fg=ACCENT)
        self.card_id.value_label.config(text=status["atendimento_id"] or "—")
        self.input.focus_set()
        self.atualizar_historico()

    def enviar(self):
        texto = self.input.get().strip()
        if not texto:
            return
        if not self.modulo.ativo:
            self.novo()
        self.input.delete(0, "end")
        self.escrever("Você", texto)

        try:
            resultado = self.service.responder(self.empresa_id, texto)
        except Exception as erro:
            self.escrever("BETA", "Não consegui continuar este atendimento. A sessão foi preservada para diagnóstico.")
            self.status_var.set(f"Erro controlado: {erro}")
            self.card_status.value_label.config(text="Erro controlado", fg=RED)
            return

        mensagem = resultado.get("mensagem", "") if isinstance(resultado, dict) else str(resultado)
        if mensagem:
            self.escrever("BETA", mensagem)

        if not self.modulo.ativo:
            self.status_var.set("Atendimento concluído — pronto para o próximo")
            self.card_status.value_label.config(text="Concluído", fg=ACCENT)
            self.atualizar_historico()

    def finalizar(self):
        if not self.modulo.ativo:
            self.status_var.set("Nenhum atendimento ativo")
            self.card_status.value_label.config(text="Pronto", fg=ACCENT)
            return
        try:
            respostas = self.service.finalizar(self.empresa_id)
        except Exception as erro:
            messagebox.showerror("Atendimento", f"Não foi possível finalizar: {erro}")
            return

        self.escrever("SISTEMA", "Atendimento finalizado e salvo no histórico da empresa.")
        self.id_var.set("ID: —")
        self.status_var.set(f"Atendimento concluído · empresa: {self.empresa_id}")
        self.card_status.value_label.config(text="Concluído", fg=ACCENT)
        self.card_id.value_label.config(text="—")
        self.atualizar_historico()
        messagebox.showinfo("Atendimento", f"Atendimento concluído com {len(respostas or {})} dado(s) registrado(s).")

    def limpar(self):
        self.modulo.limpar()
        self.status_var.set("Sessão limpa — histórico preservado")
        self.id_var.set("ID: —")
        self.card_status.value_label.config(text="Pronto", fg=ACCENT)
        self.card_id.value_label.config(text="—")
        self.escrever("SISTEMA", "Sessão limpa. O histórico persistido não foi apagado.")

    def mostrar_status(self):
        dados = self.modulo.status()
        self.status_var.set(
            f"{dados['id']} · {dados['estado']} · ativo={dados['ativo']} · empresa={self.empresa_id}"
        )

    def atualizar_historico(self):
        self.historico.delete(0, "end")
        registros = self.service.store.listar(self.empresa_id)
        for registro in reversed(registros[-50:]):
            atendimento_id = registro.get("atendimento_id", "—")
            estado = registro.get("estado", "—")
            nome = registro.get("nome_pessoa") or "Sem nome"
            self.historico.insert("end", f"{atendimento_id} · {nome} · {estado}")

    def abrir_historico(self, _event=None):
        indice = self.historico.curselection()
        if not indice:
            return
        registros = list(reversed(self.service.store.listar(self.empresa_id)[-50:]))
        if indice[0] >= len(registros):
            return
        registro = registros[indice[0]]
        texto = (
            f"ID: {registro.get('atendimento_id', '—')}\n"
            f"Empresa: {registro.get('empresa_id', '—')}\n"
            f"Nome: {registro.get('nome_pessoa') or '—'}\n"
            f"Estado: {registro.get('estado', '—')}\n\n"
            f"Respostas: {registro.get('respostas') or '—'}"
        )
        messagebox.showinfo("Histórico do atendimento", texto)


def main(empresa_id="alpha-demo"):
    root = tk.Tk()
    AtendimentoApp(root, empresa_id=empresa_id)
    root.mainloop()


if __name__ == "__main__":
    main()
