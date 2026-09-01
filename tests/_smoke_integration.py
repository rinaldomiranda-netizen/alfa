"""
Smoke test manual (não faz parte da suíte automatizada): inicializa
de verdade os componentes reais do ALFA neste Windows (SAPI, pyttsx3,
pyautogui) para detectar erros de ambiente que os testes com mock não
pegam. Não entra no loop de escuta contínua.
"""

import sys
import traceback

sys.path.insert(0, ".")


def testar_windows_speech():
    from voice.voice_engine import WindowsSpeechRecognizer, WindowsSpeechUnavailable

    try:
        WindowsSpeechRecognizer(timeout_segundos=1)
        print("[OK] SAPI/Windows Speech pôde ser instanciado neste Windows.")
    except WindowsSpeechUnavailable as erro:
        print(f"[AVISO] Windows Speech indisponível neste ambiente: {erro}")


def testar_tts():
    from voice.voice_output import VoiceOutput

    # Sem AZURE_SPEECH_KEY/REGION configuradas neste ambiente, o
    # VoiceOutput deve cair sozinho para o motor offline (pyttsx3) em
    # vez de travar o ALFA.
    voice_output = VoiceOutput(motor="azure", motor_fallback="pyttsx3")
    print(f"[OK] VoiceOutput inicializado. Motor ativo: {voice_output.motor_ativo}")
    return voice_output


def testar_personalidade():
    from core.personality import Personality

    personality = Personality(nome_usuario="Rinaldo")
    saudacao, estilo = personality.saudacao_inicial()
    print(f"[OK] Personalidade: ({estilo!r}) {saudacao!r}")

    texto, estilo = personality.compor(
        {"intent": "MOVER_MOUSE"}, "Mouse movido para a direita."
    )
    print(f"[OK] Personalidade (comando local): ({estilo!r}) {texto!r}")


def testar_executor_real():
    import pyautogui
    from computer.executor import Executor

    executor = Executor(passo_pixels=5, duracao=0.01)
    x, y = pyautogui.position()
    resultado = executor.mover_mouse("direita")
    x2, y2 = pyautogui.position()
    assert (x2, y2) != (x, y) or x2 == pyautogui.size()[0] - 1, "mouse não se moveu"
    executor.mover_mouse("esquerda")
    print(f"[OK] Executor moveu o mouse de verdade: ({x},{y}) -> ({x2},{y2})")


def testar_intent_router():
    from core.intent_engine import IntentEngine
    from core.router import Router
    from computer.executor import Executor

    engine = IntentEngine()
    executor = Executor()
    router = Router(engine, executor, brain_fallback=None)
    resultado, intent = router.handle("qual a posição do mouse")
    print(f"[OK] Router: intent={intent} resultado={resultado!r}")


def main():
    falhas = []

    for nome, fn in [
        ("windows_speech", testar_windows_speech),
        ("tts", testar_tts),
        ("personalidade", testar_personalidade),
        ("executor_real", testar_executor_real),
        ("intent_router", testar_intent_router),
    ]:
        try:
            fn()
        except Exception:
            falhas.append(nome)
            print(f"[FALHA] {nome}")
            traceback.print_exc()

    print("\n--- RESUMO ---")
    print(f"Falhas: {falhas if falhas else 'nenhuma'}")


if __name__ == "__main__":
    main()
