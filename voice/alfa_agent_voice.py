import os
import sys

BASE = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

VOICE_DIR = os.path.join(BASE, "voice")

if VOICE_DIR not in sys.path:
    sys.path.insert(0, VOICE_DIR)

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from alfa_voice import ALFA
from core.alfa_agent import responder


def main():

    alfa = ALFA()

    print("=" * 65)
    print("                         ALFA")
    print("              ASSISTENTE PESSOAL")
    print("                  MODO VOZ + IA")
    print("=" * 65)

    alfa.falar(
        "ALFA iniciado. Estou ouvindo e pronto para controlar o computador."
    )

    while True:

        try:

            comando = alfa.ouvir()

            if not comando:
                continue

            comando = comando.strip()

            print(f"\nVOCÊ: {comando}")

            if comando.lower() in [
                "sair",
                "encerrar",
                "fechar alfa",
                "desligar alfa"
            ]:
                alfa.falar("Encerrando o ALFA.")
                break

            print("ALFA: Estou processando...")

            resultado = responder(comando)

            print(f"\nALFA: {resultado}")

            fala = str(resultado)

            if len(fala) > 700:
                fala = fala[:700] + ". O restante está disponível no terminal."

            alfa.falar(fala)

        except KeyboardInterrupt:

            print("\nALFA encerrado pelo usuário.")
            break

        except Exception as erro:

            print(f"\nERRO: {erro}")

            try:
                alfa.falar(
                    "Encontrei um problema durante a execução."
                )
            except:
                pass


if __name__ == "__main__":
    main()
