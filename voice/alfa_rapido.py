import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from computer.computer import ComputadorALFA
from alfa_voice import ALFA


def main():

    computador = ComputadorALFA()
    alfa = ALFA()

    print("=" * 60)
    print("                         ALFA")
    print("                   MODO RÁPIDO")
    print("=" * 60)

    alfa.falar("ALFA iniciado. Estou pronto.")

    while True:

        try:

            comando = alfa.ouvir()

            if not comando:
                continue

            comando = comando.lower().strip()

            comando = comando.replace("alfa", "").strip()

            # SAÍDA
            if any(p in comando for p in [
                "sair",
                "saia",
                "encerrar",
                "encerra",
                "pare",
                "parar",
                "desligar",
                "desliga"
            ]):

                alfa.falar("Encerrando o ALFA.")
                break

            # COMANDOS DIRETOS
            resultado = computador.executar(comando)

            if resultado:

                alfa.falar(resultado)
                continue

            # COMANDO VISUAL
            if (
                "olhe minha tela" in comando
                or "veja minha tela" in comando
                or "analise minha tela" in comando
                or "olhe a tela" in comando
            ):

                alfa.falar("Vou analisar sua tela.")

                try:

                    import sys
                    sys.path.insert(0, BASE)

                    from alfa_agent import analisar_tela

                    resultado = analisar_tela()

                    print("\nALFA VISÃO:")
                    print(resultado)

                    alfa.falar(
                        str(resultado)[:700]
                    )

                except Exception as erro:

                    print("ERRO DE VISÃO:", erro)

                    alfa.falar(
                        "Não consegui analisar a tela."
                    )

                continue

            alfa.falar(
                "Ainda estou aprendendo essa ação."
            )

        except KeyboardInterrupt:

            print("\nALFA encerrado pelo teclado.")
            break

        except Exception as erro:

            print("\nERRO:", erro)

            try:
                alfa.falar(
                    "Encontrei um problema."
                )
            except:
                pass


if __name__ == "__main__":
    main()

