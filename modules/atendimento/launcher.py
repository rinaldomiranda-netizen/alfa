"""Entrada simples do RMD Atendimento no ALPHA."""


def abrir():
    from ui.atendimento_app import main
    return main()


if __name__ == "__main__":
    abrir()
