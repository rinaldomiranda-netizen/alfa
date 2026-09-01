import os
import re
import subprocess
import shutil
import pyautogui
import psutil
import platform
from datetime import datetime


class ComputadorALFA:

    def falar_status(self):
        cpu = psutil.cpu_percent(interval=1)
        memoria = psutil.virtual_memory()

        return (
            f"Computador {platform.node()}. "
            f"Windows {platform.release()}. "
            f"Processador em {cpu} por cento. "
            f"Memória em {memoria.percent} por cento. "
            f"Horário {datetime.now().strftime('%H:%M')}."
        )

    def abrir(self, programa):

        programa = programa.lower().strip()

        # Remove artigos que costumam aparecer na fala
        programa = re.sub(r'^(o|a|os|as)\s+', '', programa)

        aliases = {
            "calculadora": "calc.exe",
            "calculator": "calc.exe",
            "bloco de notas": "notepad.exe",
            "notepad": "notepad.exe",
            "paint": "mspaint.exe",
            "explorador": "explorer.exe",
            "explorador de arquivos": "explorer.exe",
        }

        if "vs code" in programa or "visual studio code" in programa or programa == "code":
            if shutil.which("code"):
                subprocess.Popen(["code"], shell=True)
            else:
                subprocess.Popen("code", shell=True)

            return "VS Code aberto."

        if programa in aliases:
            subprocess.Popen(aliases[programa], shell=True)
            return f"{programa} aberto."

        return f"Ainda não tenho permissão configurada para abrir {programa}."

    def fechar(self, programa):

        programa = programa.lower().strip()
        programa = re.sub(r'^(o|a|os|as)\s+', '', programa)

        processos = {
            "calculadora": ["CalculatorApp.exe"],
            "calculator": ["CalculatorApp.exe"],
            "bloco de notas": ["notepad.exe"],
            "notepad": ["notepad.exe"],
            "paint": ["mspaint.exe"],
            "vs code": ["Code.exe"],
            "visual studio code": ["Code.exe"],
        }

        if programa in processos:

            encontrados = []

            for processo in psutil.process_iter(["name"]):
                try:
                    nome = processo.info["name"]

                    if nome and nome.lower() in [
                        p.lower() for p in processos[programa]
                    ]:
                        encontrados.append(processo)

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if not encontrados:
                return f"{programa} não está aberto."

            for processo in encontrados:
                try:
                    processo.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return f"{programa} fechado."

        return f"Ainda não tenho o comando para fechar {programa}."

    def captura(self):

        arquivo = os.path.abspath("alfa_tela.png")

        pyautogui.screenshot(arquivo)

        return f"Captura da tela realizada e salva em {arquivo}."

    def mouse(self):

        x, y = pyautogui.position()

        return f"O mouse está na posição X {x}, Y {y}."

    def mover_mouse(self, x, y):

        pyautogui.moveTo(int(x), int(y), duration=0.3)

        return f"Mudei o mouse para X {x}, Y {y}."

    def executar(self, comando):

        comando = comando.lower().strip()

        # -------------------------
        # STATUS
        # -------------------------

        if "status" in comando:
            return self.falar_status()

        # -------------------------
        # CAPTURA DE TELA
        # -------------------------

        if (
            "captura" in comando
            or "capturar tela" in comando
            or "tire um print" in comando
            or "tirar um print" in comando
            or "print da tela" in comando
        ):
            return self.captura()

        # -------------------------
        # POSIÇÃO DO MOUSE
        # -------------------------

        if "posição do mouse" in comando or "posicao do mouse" in comando:
            return self.mouse()

        # -------------------------
        # FECHAR PROGRAMAS
        # -------------------------

        if (
            comando.startswith("feche ")
            or comando.startswith("fecha ")
            or comando.startswith("fechar ")
            or "feche a " in comando
            or "feche o " in comando
        ):

            programa = comando

            for palavra in [
                "feche a ",
                "feche o ",
                "feche ",
                "fecha a ",
                "fecha o ",
                "fecha ",
                "fechar a ",
                "fechar o ",
                "fechar ",
            ]:
                programa = programa.replace(palavra, "", 1)

            return self.fechar(programa)

        # -------------------------
        # ABRIR PROGRAMAS
        # -------------------------

        if (
            comando.startswith("abra ")
            or comando.startswith("abrir ")
            or comando.startswith("abre ")
        ):

            programa = comando

            for palavra in [
                "abra o ",
                "abra a ",
                "abra ",
                "abrir o ",
                "abrir a ",
                "abrir ",
                "abre o ",
                "abre a ",
                "abre ",
            ]:
                programa = programa.replace(palavra, "", 1)

            return self.abrir(programa)

        # -------------------------
        # CLIQUE
        # -------------------------

        if "clique" in comando or "clicar" in comando:
            pyautogui.click()
            return "Clique executado."

        # -------------------------
        # ENTER
        # -------------------------

        if "pressione enter" in comando or "aperte enter" in comando:
            pyautogui.press("enter")
            return "Enter pressionado."

        return None
