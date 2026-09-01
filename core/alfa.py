import sys
import os

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from voice.alfa_voice import ALFA
from computer.computer import ComputadorALFA


def main():

    alfa = ALFA()
    computador = ComputadorALFA()

    print("=" * 60)
    print("                         ALFA")
    print("              ASSISTENTE PESSOAL")
    print("=" * 60)

    alfa.falar(
        "Sistema ALFA iniciado. "
        "Estou pronto para controlar o computador."
    )

    while True:

        try:

            comando = alfa.ouvir()

            if not comando:
                continue

            comando = comando.lower().strip()

            # Remove o nome do assistente
            comando = comando.replace("alfa", "").strip()

            # -------------------------
            # ENCERRAR
            # -------------------------

            if any(
                palavra in comando
                for palavra in [
                    "encerrar alfa",
                    "desligar alfa",
                    "sair",
                    "encerrar"
                ]
            ):
                alfa.falar("Encerrando o ALFA.")
                break

            # -------------------------
            # SAUDAÇÃO
            # -------------------------

            if (
                "olá" in comando
                or "ola" in comando
                or "bom dia" in comando
                or "boa tarde" in comando
                or "boa noite" in comando
            ):
                alfa.falar(
                    "Olá, senhor. Estou pronto."
                )
                continue

            # -------------------------
            # EXECUÇÃO
            # -------------------------

            resultado = computador.executar(comando)

            if resultado:

                alfa.falar(resultado)

            else:

                alfa.falar(
                    "Entendi o que você falou, "
                    "mas essa ação ainda não está cadastrada."
                )

        except KeyboardInterrupt:

            print("\nALFA encerrado pelo usuário.")
            break

        except Exception as erro:

            print(f"ERRO CONTROLADO: {erro}")

            alfa.falar(
                "Encontrei um problema ao executar essa ação."
            )


if __name__ == "__main__":
    main()
