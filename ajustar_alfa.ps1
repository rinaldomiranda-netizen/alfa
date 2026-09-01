$p="alfa_turbo.py"
$s=Get-Content $p -Raw

$s=$s.Replace(
'if "mova o mouse" in c:
        return "Comando de movimento preparado."',
'''if "mova o mouse para o centro" in c or "mova o mouse pro centro" in c:
        largura, altura = pyautogui.size()
        pyautogui.moveTo(largura // 2, altura // 2, duration=0.05)
        return "Mouse movido para o centro da tela."

    if "mova o mouse para cima" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(x, max(0, y - 200), duration=0.05)
        return "Mouse movido para cima."

    if "mova o mouse para baixo" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(x, y + 200, duration=0.05)
        return "Mouse movido para baixo."

    if "mova o mouse para a esquerda" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(max(0, x - 200), y, duration=0.05)
        return "Mouse movido para a esquerda."

    if "mova o mouse para a direita" in c:
        x, y = pyautogui.position()
        pyautogui.moveTo(x + 200, y, duration=0.05)
        return "Mouse movido para a direita."

    if "clique" in c and "botão esquerdo" in c:
        pyautogui.click()
        return "Clique realizado."

    if "clique" in c and "botão direito" in c:
        pyautogui.rightClick()
        return "Clique direito realizado."

    if "clique" in c:
        pyautogui.click()
        return "Clique realizado."'''
)

$s=$s.Replace(
'"stream": False',
'"stream": False, "keep_alive": -1, "options": {"temperature": 0.1, "num_predict": 120}'
)

Set-Content $p $s -Encoding UTF8
