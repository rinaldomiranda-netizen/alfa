"""Tela operacional do RMD Atendimento dentro do ALPHA.

Esta camada visual não duplica o protocolo: usa AtendimentoModule e o
roteiro real de core.roteiro_pesquisa. O mesmo módulo pode continuar sendo
usado sem esta tela (modo standalone).
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.atendimento import AtendimentoModule
from core.roteiro_pesquisa import roteiro_nova_entrevista


class AtendimentoApp:
    def __init__(self, master):
        self.master = master
        self.master.title("ALPHA — RMD Atendimento")
        self.master.geometry("900x650")
        self.master.minsize(720, 520)
        self.modulo = AtendimentoModule()

        self.status_var = tk.StringVar(value="Pronto para iniciar um atendimento")
        self.msg_var = tk.StringVar(value="")

        header = tk.Frame(master, padx=20, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="RMD Atendimento", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(header, text="Módulo ALPHA · V5.1.1", font=("Segoe UI", 11)).pack(anchor="w")

        status = tk.Label(master, textvariable=self.status_var, anchor="w", padx=20, pady=10)
        status.pack(fill="x")

        self.conversa = tk.Text(master, wrap="word", state="disabled", font=("Segoe UI", 12), padx=16, pady=16)
        self.conversa.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        entrada = tk.Frame(master, padx=20)
        entrada.pack(fill="x")
        self.input = tk.Entry(entrada, font=("Segoe UI", 13))
        self.input.pack(side="left", fill="x", expand=True, ipady=9)
        self.input.bind("<Return>", lambda _event: self.enviar())
        tk.Button(entrada, text="Enviar", command=self.enviar, width=12).pack(side="left", padx=(8, 0), ipady=7)

        botoes = tk.Frame(master, padx=20, pady=14)
        botoes.pack(fill="x")
        tk.Button(botoes, text="Novo atendimento", command=self.novo, width=18).pack(side="left")
        tk.Button(botoes, text="Limpar sessão", command=self.limpar, width=16).pack(side="left", padx=8)
        tk.Button(botoes, text="Status", command=self.mostrar_status, width=12).pack(side="right")

    def escrever(self, autor, texto):
        self.conversa.configure(state="normal")
        self.conversa.insert("end", f"{autor}: {texto}\n\n")
        self.conversa.see("end")
        self.conversa.configure(state="disabled")

    def novo(self):
        resposta = self.modulo.iniciar(roteiro_nova_entrevista())
        self.conversa.configure(state="normal")
        self.conversa.delete("1.0", "end")
        self.conversa.configure(state="disabled")
        self.escrever("BETA", resposta)
        self.status_var.set("Atendimento em andamento")
        self.input.focus_set()

    def enviar(self):
        texto = self.input.get().strip()
        if not texto:
            return
        if not self.modulo.ativo:
            self.novo()
        self.input.delete(0, "end")
        self.escrever("Você", texto)
        try:
            resultado = self.modulo.responder(texto)
        except Exception as erro:
            self.escrever("BETA", "Não consegui continuar este atendimento. A sessão foi preservada para diagnóstico.")
            self.status_var.set(f"Erro controlado: {erro}")
            return

        mensagem = resultado.get("mensagem", "") if isinstance(resultado, dict) else str(resultado)
        if mensagem:
            self.escrever("BETA", mensagem)

        if not self.modulo.ativo:
            self.status_var.set("Atendimento concluído — pronto para o próximo")
            if self.modulo.estado.value == "concluido":
                messagebox.showinfo("Atendimento", "Atendimento concluído. O contexto pode ser encerrado com segurança.")

    def limpar(self):
        self.modulo.limpar()
        self.status_var.set("Sessão limpa")
        self.escrever("SISTEMA", "Sessão limpa. Nenhum contexto do atendimento anterior é mantido pelo módulo.")

    def mostrar_status(self):
        dados = self.modulo.status()
        self.status_var.set(f"{dados['id']} · {dados['estado']} · ativo={dados['ativo']}")


def main():
    root = tk.Tk()
    AtendimentoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
