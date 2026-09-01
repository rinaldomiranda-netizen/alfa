from pathlib import Path

p = Path("alfa_turbo.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    "from voice.alfa_voice import ALFA",
    "from voice.alfa_voice import ALFA\nfrom core.intent_engine import IntentEngine"
)

s = s.replace(
    "OLLAMA = ",
    "intent_engine = IntentEngine()\n\nOLLAMA = ",
    1
)

marcador = "            # VISÃO"

bloco = '''            # =====================================================
            # COMANDOS INTELIGENTES LOCAIS
            # NÃO CONSULTA O CÉREBRO
            # =====================================================

            intencao = intent_engine.interpretar(comando)

            print("INTENÇÃO:", intencao)

            tipo = intencao.get("intent")

            if tipo == "MOVER_MOUSE":

                direcao = intencao.get("direcao")
                largura, altura = pyautogui.size()
                x, y = pyautogui.position()

                if direcao == "direita":
                    pyautogui.moveTo(
                        min(largura - 1, x + 300),
                        y,
                        duration=0.03
                    )
                    alfa.falar("Mouse movido para a direita.")

                elif direcao == "esquerda":
                    pyautogui.moveTo(
                        max(0, x - 300),
                        y,
                        duration=0.03
                    )
                    alfa.falar("Mouse movido para a esquerda.")

                elif direcao == "cima":
                    pyautogui.moveTo(
                        x,
                        max(0, y - 300),
                        duration=0.03
                    )
                    alfa.falar("Mouse movido para cima.")

                elif direcao == "baixo":
                    pyautogui.moveTo(
                        x,
                        min(altura - 1, y + 300),
                        duration=0.03
                    )
                    alfa.falar("Mouse movido para baixo.")

                elif direcao == "centro":
                    pyautogui.moveTo(
                        largura // 2,
                        altura // 2,
                        duration=0.03
                    )
                    alfa.falar("Mouse movido para o centro.")

                else:
                    alfa.falar(
                        "Diga para direita, esquerda, cima, baixo ou centro."
                    )

                continue

            if tipo == "CLIQUE":

                botao = intencao.get("botao")

                if botao == "direito":
                    pyautogui.rightClick()

                elif botao == "duplo":
                    pyautogui.doubleClick()

                else:
                    pyautogui.click()

                alfa.falar("Clique realizado.")
                continue

            if tipo == "COPIAR":
                pyautogui.hotkey("ctrl", "c")
                alfa.falar("Copiado.")
                continue

            if tipo == "COLAR":
                pyautogui.hotkey("ctrl", "v")
                alfa.falar("Colado.")
                continue

            if tipo == "DESFAZER":
                pyautogui.hotkey("ctrl", "z")
                alfa.falar("Desfeito.")
                continue

            if tipo == "SELECIONAR_TUDO":
                pyautogui.hotkey("ctrl", "a")
                alfa.falar("Tudo selecionado.")
                continue

            if tipo == "ENTER":
                pyautogui.press("enter")
                alfa.falar("Enter pressionado.")
                continue

            if tipo == "ESC":
                pyautogui.press("esc")
                alfa.falar("Escape pressionado.")
                continue

'''

if "COMANDOS INTELIGENTES LOCAIS" not in s:
    s = s.replace(marcador, bloco + marcador)

p.write_text(s, encoding="utf-8")

print("INTEGRAÇÃO DO MOTOR DE INTENÇÃO CONCLUÍDA.")
