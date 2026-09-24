"""Tela operacional do RMD Atendimento dentro do ALPHA.

A interface usa AtendimentoService para manter a mesma máquina de estados
já existente no core e, ao mesmo tempo, persistir o atendimento por empresa.
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.atendimento.service import AtendimentoService
from core.roteiro_pesquisa import roteiro_nova_entrevista


class AtendimentoApp:
    """Interface desktop do módulo RMD Atendimento no ALPHA.

    ``empresa_id`` é recebido pelo shell do ALPHA quando disponível. O valor
    padrão permite executar o módulo isoladamente sem quebrar o uso local.
    """

    def __init__(self, master, empresa_id="alpha-demo"):
        self.master = master
        self.empresa_id = empresa_id or "alpha-demo"
        self.master.title("ALPHA — RMD Atendimento")
        self.master.geometry("1000x700")
        self.master.minsize(780, 560)
        self.service = AtendimentoService()
        self.modulo = self.service.modulo

        self.status_var = tk.StringVar(value=f"Pronto · empresa: {self.empresa_id}")
        self.msg_var = tk.StringVar(value="")
        self.id_var = tk.StringVar(value="ID: —")

        header = tk.Frame(master, padx=20, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="RMD Atendimento", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(header, text="Módulo ALPHA · V5.1.1", font=("Segoe UI", 11)).pack(anchor="w")
        tk.Label(header, textvariable=self.id_var, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

        status = tk.Label(master, textvariable=self.status_var, anchor="w", padx=20, pady=10)
        status.pack(fill="x")

        corpo = tk.Frame(master, padx=20)
        corpo.pack(fill="both", expand=True)

        self.conversa = tk.Text(corpo, wrap="word", state="disabled", font=("Segoe UI", 12), padx=16, pady=16)
        self.conversa.pack(side="left", fill="both", expand=True)

        lateral = tk.Frame(corpo, padx=12, width=240)
        lateral.pack(side="right", fill="y")
        lateral.pack_propagate(False)
        tk.Label(lateral, text="Histórico da empresa", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.historico = tk.Listbox(lateral, activestyle="none")
        self.historico.pack(fill="both", expand=True, pady=(8, 8))
        self.historico.bind("<Double-Button-1>", self.abrir_historico)
        tk.Button(lateral, text="Atualizar histórico", command=self.atualizar_historico).pack(fill="x")

        entrada = tk.Frame(master, padx=20, pady=10)
        entrada.pack(fill="x")
        self.input = tk.Entry(entrada, font=("Segoe UI", 13))
        self.input.pack(side="left", fill="x", expand=True, ipady=9)
        self.input.bind("<Return>", lambda _event: self.enviar())
        tk.Button(entrada, text="Enviar", command=self.enviar, width=12).pack(side="left", padx=(8, 0), ipady=7)

        botoes = tk.Frame(master, padx=20, pady=14)
        botoes.pack(fill="x")
        tk.Button(botoes, text="Novo atendimento", command=self.novo, width=18).pack(side="left")
        tk.Button(botoes, text="Finalizar", command=self.finalizar, width=14).pack(side="left", padx=8)
        tk.Button(botoes, text="Limpar sessão", command=self.limpar, width=16).pack(side="left")
        tk.Button(botoes, text="Status", command=self.mostrar_status, width=12).pack(side="right")

        self.atualizar_historico()

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
            return

        mensagem = resultado.get("mensagem", "") if isinstance(resultado, dict) else str(resultado)
        if mensagem:
            self.escrever("BETA", mensagem)

        if not self.modulo.ativo:
            self.status_var.set("Atendimento concluído — pronto para o próximo")
            self.atualizar_historico()

    def finalizar(self):
        if not self.modulo.ativo:
            self.status_var.set("Nenhum atendimento ativo")
            return
        try:
            respostas = self.service.finalizar(self.empresa_id)
        except Exception as erro:
            messagebox.showerror("Atendimento", f"Não foi possível finalizar: {erro}")
            return
        self.escrever("SISTEMA", "Atendimento finalizado e salvo no histórico da empresa.")
        self.id_var.set("ID: —")
        self.status_var.set(f"Atendimento concluído · empresa: {self.empresa_id}")
        self.atualizar_historico()
        messagebox.showinfo("Atendimento", f"Atendimento concluído com {len(respostas or {})} dado(s) registrado(s).")

    def limpar(self):
        self.modulo.limpar()
        self.status_var.set("Sessão limpa — histórico preservado")
        self.id_var.set("ID: —")
        self.escrever("SISTEMA", "Sessão limpa. O histórico persistido não foi apagado.")

    def mostrar_status(self):
        dados = self.modulo.status()
        self.status_var.set(f"{dados['id']} · {dados['estado']} · ativo={dados['ativo']} · empresa={self.empresa_id}")

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
