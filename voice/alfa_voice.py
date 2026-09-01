import os
import wave
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

ARQUIVO_AUDIO = os.path.join(os.getcwd(), "alfa_voz.wav")
TAXA = 16000
MICROFONE = 1

class ALFA:

    def __init__(self):
        self.recognizer = sr.Recognizer()

        self.recognizer.energy_threshold = 250
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.2
        self.recognizer.non_speaking_duration = 0.5

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 175)
        self.engine.setProperty("volume", 1.0)

    def falar(self, texto):
        print(f"\nALFA: {texto}")
        self.engine.say(texto)
        self.engine.runAndWait()

    def gravar(self, segundos=7):
        print("\n🎙️ ALFA: Estou ouvindo... Fale agora.")

        audio = sd.rec(
            int(segundos * TAXA),
            samplerate=TAXA,
            channels=1,
            dtype="float32",
            device=MICROFONE
        )

        sd.wait()

        # Amplificação do sinal
        ganho = 6.0
        audio = audio * ganho
        audio = np.clip(audio, -1.0, 1.0)

        # Converte para PCM 16-bit
        audio_int16 = (audio * 32767).astype(np.int16)

        with wave.open(ARQUIVO_AUDIO, "wb") as arquivo:
            arquivo.setnchannels(1)
            arquivo.setsampwidth(2)
            arquivo.setframerate(TAXA)
            arquivo.writeframes(audio_int16.tobytes())

        volume = float(np.max(np.abs(audio)))
        print(f"ALFA: sinal capturado = {volume:.3f}")

    def ouvir(self):
        self.gravar()

        try:
            with sr.AudioFile(ARQUIVO_AUDIO) as fonte:
                audio = self.recognizer.record(fonte)

            print("🧠 ALFA: interpretando sua fala...")

            texto = self.recognizer.recognize_google(
                audio,
                language="pt-BR"
            )

            texto = texto.strip().lower()

            print(f"VOCÊ: {texto}")

            return texto

        except sr.UnknownValueError:
            print("ALFA: Não consegui compreender a fala.")
            return ""

        except sr.RequestError as erro:
            print(f"ALFA: Serviço de reconhecimento indisponível: {erro}")
            return ""

        except Exception as erro:
            print(f"ALFA: Erro de áudio: {erro}")
            return ""

    def processar(self, comando):

        if not comando:
            return True

        if "alfa" in comando:
            comando = comando.replace("alfa", "").strip()

        if comando in ["sair", "encerrar", "desligar", "fechar"]:
            self.falar("Encerrando o ALFA.")
            return False

        if "olá" in comando or "ola" in comando:
            self.falar("Olá, senhor. Estou pronto.")
            return True

        if "teste" in comando:
            self.falar("Sistema de voz funcionando perfeitamente.")
            return True

        self.falar(f"Entendi você dizer: {comando}")
        return True


def main():

    alfa = ALFA()

    print("=" * 60)
    print("                         ALFA")
    print("                  ASSISTENTE PESSOAL")
    print("=" * 60)

    alfa.falar("Sistema ALFA iniciado. Estou pronto.")

    while True:

        try:
            comando = alfa.ouvir()

            continuar = alfa.processar(comando)

            if not continuar:
                break

        except KeyboardInterrupt:
            print("\nALFA encerrado pelo usuário.")
            break


if __name__ == "__main__":
    main()
