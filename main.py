"""
ALFA - Assistente de voz local para Windows.

Uso:
    python main.py                        inicia o assistente de voz
    python main.py --instalar-inicializacao   ativa início automático com o Windows
    python main.py --remover-inicializacao    desativa o início automático
    python main.py --status-inicializacao     mostra se está ativado

Fluxo do assistente:

    microfone
    -> reconhecimento de voz do Windows (fallback: Whisper local)
    -> texto
    -> normalização
    -> interpretação do comando (NLU local)
    -> execução local (mouse/teclado/janelas/programas)
    -> resposta falada
    -> volta a escutar automaticamente

Comandos locais reconhecidos nunca são enviados para um mecanismo de
IA externo. Só uma frase que o interpretador não reconheça (intent
DESCONHECIDO) segue para um cérebro conversacional local (Ollama), e
comandos sensíveis (fechar programa, desligar/reiniciar o computador)
só executam depois de confirmação falada.
"""

import sys

from core.alfa_core import AlfaCore


def main():
    args = sys.argv[1:]

    if "--instalar-inicializacao" in args:
        from core import startup
        caminho = startup.instalar()
        print(f"Inicialização automática ativada: {caminho}")
        return

    if "--remover-inicializacao" in args:
        from core import startup
        removido = startup.remover()
        print("Inicialização automática removida." if removido else "Não havia inicialização automática ativa.")
        return

    if "--status-inicializacao" in args:
        from core import startup
        print("ATIVADA" if startup.esta_instalado() else "DESATIVADA")
        return

    print("=" * 60)
    print("                         BETA")
    print("       ASSISTENTE DE VOZ PESSOAL DE RINALDO")
    print("            (projeto ALFA — motor interno)")
    print("=" * 60)

    AlfaCore().run()


if __name__ == "__main__":
    main()
