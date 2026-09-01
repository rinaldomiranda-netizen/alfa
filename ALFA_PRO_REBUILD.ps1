$ErrorActionPreference = "Stop"

Write-Host "ALFA PRO - preparando a nova arquitetura..." -ForegroundColor Cyan

$root = Get-Location
$venv = Join-Path $root ".venv311"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Nao encontrei .venv311. Execute este arquivo dentro da pasta ALFA que ja possui .venv311."
}

# Backup do que existe sem apagar o projeto
$backup = Join-Path $root ("backup_alfa_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $backup -Force | Out-Null

foreach ($name in @("alfa_pro.py","core\alfa_nlu.py","core\semantic_router.py")) {
    $src = Join-Path $root $name
    if (Test-Path $src) {
        $dst = Join-Path $backup $name
        New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
        Copy-Item $src $dst -Force
    }
}

& $python -m pip install -U pip
& $python -m pip install -U faster-whisper sounddevice numpy scipy sentence-transformers spacy rapidfuzz

try {
    & $python -m spacy download pt_core_news_sm
} catch {
    Write-Host "Aviso: modelo spaCy nao foi baixado; o ALFA continua usando o motor semantico." -ForegroundColor Yellow
}

$core = Join-Path $root "core"
New-Item -ItemType Directory -Path $core -Force | Out-Null

$py = @'
import os
import re
import json
import time
import subprocess
import unicodedata
from pathlib import Path

import numpy as np
import sounddevice as sd
import pyautogui

from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer, util

try:
    import spacy
except Exception:
    spacy = None


ROOT = Path(__file__).resolve().parent.parent
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


class ALFAIntent:
    def __init__(self):
        self.encoder = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.intents = {
            "MOVER_MOUSE": [
                "mova o mouse para esquerda",
                "mexa o mouse para esquerda",
                "leve o mouse para esquerda",
                "desloque o mouse para esquerda",
                "mude o mouse para esquerda",
                "jogue o mouse para esquerda",
                "mova o cursor para esquerda",
                "mexa o cursor para esquerda",
                "mova o mouse para direita",
                "mexa o mouse para direita",
                "leve o mouse para direita",
                "mova o cursor para direita",
                "mova o mouse para cima",
                "mexa o mouse para cima",
                "suba o mouse",
                "eleve o mouse",
                "mova o cursor para cima",
                "mova o mouse para baixo",
                "mexa o mouse para baixo",
                "desca o mouse",
                "baixe o mouse",
                "mova o cursor para baixo",
                "coloque o mouse no centro",
                "coloque o cursor no centro",
            ],
            "POSICAO_MOUSE": [
                "qual e a posicao do mouse",
                "onde esta o mouse",
                "onde fica o cursor",
                "qual a posicao do cursor",
            ],
            "CLIQUE": [
                "clique",
                "clique esquerdo",
                "clique direito",
                "duplo clique",
                "clique duas vezes",
            ],
            "COPIAR": ["copiar", "copie isso", "copie o texto"],
            "COLAR": ["colar", "cole isso", "cole o texto"],
            "DESFAZER": ["desfazer", "desfaça", "volte atras"],
            "SELECIONAR_TUDO": [
                "selecionar tudo",
                "selecione tudo",
                "marcar tudo",
            ],
            "ENTER": ["pressione enter", "aperte enter", "tecle enter"],
            "ESC": ["pressione esc", "aperte esc", "escape"],
            "ABRIR": [
                "abra a calculadora",
                "inicie a calculadora",
                "abra o navegador",
                "abra o chrome",
                "abra o edge",
                "abra o explorador",
                "abra o bloco de notas",
                "abra o paint",
            ],
            "FECHAR": [
                "feche a calculadora",
                "encerre a calculadora",
                "feche o navegador",
                "feche o chrome",
                "feche o edge",
                "feche o explorador",
                "feche o bloco de notas",
                "feche o paint",
            ],
            "VISUALIZAR": [
                "olhe minha tela",
                "veja minha tela",
                "analise minha tela",
                "o que tem na minha tela",
                "o que esta acontecendo na tela",
            ],
            "CAMERA": [
                "veja pela camera",
                "olhe pela camera",
                "veja o ambiente",
                "observe o ambiente pela camera",
            ],
            "SAIR": [
                "saia",
                "encerre o alfa",
                "feche o alfa",
                "pare o alfa",
            ],
        }

        self.examples = []
        self.labels = []

        for label, examples in self.intents.items():
            for ex in examples:
                self.examples.append(self.normalize(ex))
                self.labels.append(label)

        self.vectors = self.encoder.encode(
            self.examples,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        self.last_target = None

    def normalize(self, text):
        text = text.lower().strip()
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def direction(self, text):
        c = self.normalize(text)

        if any(x in c for x in ["esquerda", "lado esquerdo"]):
            return "esquerda"
        if any(x in c for x in ["direita", "lado direito"]):
            return "direita"
        if any(x in c for x in ["cima", "acima", "topo", "suba", "elevar"]):
            return "cima"
        if any(x in c for x in ["baixo", "abaixo", "fundo", "desca", "baixe"]):
            return "baixo"
        if any(x in c for x in ["centro", "meio"]):
            return "centro"
        return None

    def program(self, text):
        c = self.normalize(text)
        for p in [
            "calculadora", "chrome", "edge", "navegador",
            "explorador", "bloco de notas", "notepad", "paint"
        ]:
            if p in c:
                return p
        return None

    def parse(self, text):
        c = self.normalize(text)

        # Contexto: "mova mais para esquerda" depois de falar de mouse.
        if self.last_target == "MOUSE":
            d = self.direction(c)
            if d and any(x in c for x in [
                "mova", "move", "mover", "mexa", "mexe",
                "leve", "levar", "mais", "desloque", "puxe"
            ]):
                return {
                    "intent": "MOVER_MOUSE",
                    "confidence": 1.0,
                    "direction": d,
                    "context": True,
                }

        # Comando de mouse inequívoco: não depende do LLM.
        mouse_words = [
            "mouse", "mause", "maus", "cursor",
            "mou", "malwe", "malve"
        ]
        move_words = [
            "mover", "mova", "move", "mexa", "mexe", "mecho",
            "mexo", "mover", "leve", "levar", "desloque",
            "deslocar", "arraste", "arrastar", "suba", "desca",
            "baixe", "eleve", "joga", "jogue", "jogar", "macho"
        ]

        if (
            any(w in c for w in mouse_words)
            and any(w in c for w in move_words)
        ):
            self.last_target = "MOUSE"
            return {
                "intent": "MOVER_MOUSE",
                "confidence": 1.0,
                "direction": self.direction(c),
            }

        # Embedding semântico.
        v = self.encoder.encode(
            c,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores = util.cos_sim(v, self.vectors)[0].cpu().numpy()
        idx = int(np.argmax(scores))
        score = float(scores[idx])
        label = self.labels[idx]

        if score < 0.52:
            return {
                "intent": "DESCONHECIDO",
                "confidence": round(score, 3),
            }

        if label == "MOVER_MOUSE":
            self.last_target = "MOUSE"

        result = {
            "intent": label,
            "confidence": round(score, 3),
        }

        if label == "MOVER_MOUSE":
            result["direction"] = self.direction(c)

        if label in ("ABRIR", "FECHAR"):
            result["program"] = self.program(c)

        if label == "CLIQUE":
            result["button"] = (
                "direito" if "direito" in c
                else "duplo" if "duplo" in c or "duas vezes" in c
                else "esquerdo"
            )

        return result


class FastVoice:
    def __init__(self):
        print("ALFA VOZ: carregando Whisper local...")

        self.model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8",
            cpu_threads=max(2, (os.cpu_count() or 4) - 1),
        )

        self.sample_rate = 16000
        self.block = 320
        self.max_seconds = 6
        self.silence_seconds = 0.7

    def _rms(self, block):
        if block.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(block))))

    def listen(self):
        print("\n🎙️ ALFA: Estou ouvindo...")

        frames = []
        speaking = False
        silence = 0.0
        start = time.monotonic()

        # Threshold adaptativo simples.
        calibration = []

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.block,
        ) as stream:

            while time.monotonic() - start < self.max_seconds:

                data, _ = stream.read(self.block)
                block = data[:, 0].copy()
                rms = self._rms(block)

                if len(calibration) < 12:
                    calibration.append(rms)
                    continue

                noise = max(0.004, float(np.median(calibration)))
                threshold = max(0.015, noise * 3.0)

                if not speaking:
                    if rms > threshold:
                        speaking = True
                        frames.append(block)
                else:
                    frames.append(block)

                    if rms < threshold:
                        silence += self.block / self.sample_rate
                    else:
                        silence = 0.0

                    if silence >= self.silence_seconds:
                        break

        if not frames:
            return ""

        audio = np.concatenate(frames)

        segments, _ = self.model.transcribe(
            audio,
            language="pt",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 350,
            },
        )

        text = " ".join(
            seg.text.strip()
            for seg in segments
            if seg.text.strip()
        ).strip()

        print("VOCÊ:", text)

        return text


def move_mouse(direction):
    width, height = pyautogui.size()
    x, y = pyautogui.position()
    distance = 300

    if direction == "esquerda":
        pyautogui.moveTo(max(0, x - distance), y, duration=0.02)
    elif direction == "direita":
        pyautogui.moveTo(min(width - 1, x + distance), y, duration=0.02)
    elif direction == "cima":
        pyautogui.moveTo(x, max(0, y - distance), duration=0.02)
    elif direction == "baixo":
        pyautogui.moveTo(x, min(height - 1, y + distance), duration=0.02)
    elif direction == "centro":
        pyautogui.moveTo(width // 2, height // 2, duration=0.02)
    else:
        return False

    return True


def open_program(name):
    aliases = {
        "calculadora": "calc.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "navegador": "msedge.exe",
        "explorador": "explorer.exe",
        "bloco de notas": "notepad.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
    }

    exe = aliases.get(name)
    if not exe:
        return False

    try:
        subprocess.Popen(exe)
        return True
    except Exception:
        return False


def close_program(name):
    aliases = {
        "calculadora": "CalculatorApp.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "navegador": "msedge.exe",
        "bloco de notas": "notepad.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
    }

    proc = aliases.get(name)
    if not proc:
        return False

    result = subprocess.run(
        ["taskkill", "/F", "/IM", proc],
        capture_output=True,
        text=True,
    )

    return result.returncode == 0


def camera_or_screen_not_implemented_here():
    return False


def brain_fallback(text):
    # Só para perguntas abertas. Nunca para comandos básicos.
    import urllib.request

    payload = {
        "model": "llama3:8b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é o cérebro conversacional do ALFA. "
                    "Responda em português do Brasil, de forma curta, "
                    "natural, objetiva e coerente. "
                    "Você NÃO controla mouse, teclado ou programas. "
                    "Comandos de computador são executados pelo ALFA."
                ),
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.2,
            "num_predict": 160,
        },
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["message"]["content"].strip()
    except Exception:
        return "Não consegui processar isso agora."


def execute(intent, voice):
    kind = intent["intent"]

    if kind == "SAIR":
        voice.speak("Encerrando o ALFA.")
        return "SAIR"

    if kind == "MOVER_MOUSE":
        direction = intent.get("direction")
        if move_mouse(direction):
            voice.speak(f"Mouse movido para {direction}.")
        else:
            voice.speak(
                "Entendi que você quer mover o mouse. "
                "Para qual lado?"
            )
        return True

    if kind == "POSICAO_MOUSE":
        x, y = pyautogui.position()
        voice.speak(f"O mouse está em {x} por {y}.")
        return True

    if kind == "CLIQUE":
        button = intent.get("button", "esquerdo")
        if button == "direito":
            pyautogui.rightClick()
        elif button == "duplo":
            pyautogui.doubleClick()
        else:
            pyautogui.click()
        voice.speak("Clique realizado.")
        return True

    if kind == "COPIAR":
        pyautogui.hotkey("ctrl", "c")
        voice.speak("Copiado.")
        return True

    if kind == "COLAR":
        pyautogui.hotkey("ctrl", "v")
        voice.speak("Colado.")
        return True

    if kind == "DESFAZER":
        pyautogui.hotkey("ctrl", "z")
        voice.speak("Desfeito.")
        return True

    if kind == "SELECIONAR_TUDO":
        pyautogui.hotkey("ctrl", "a")
        voice.speak("Tudo selecionado.")
        return True

    if kind == "ENTER":
        pyautogui.press("enter")
        voice.speak("Enter pressionado.")
        return True

    if kind == "ESC":
        pyautogui.press("esc")
        voice.speak("Escape pressionado.")
        return True

    if kind == "ABRIR":
        program = intent.get("program")
        if program and open_program(program):
            voice.speak(f"{program} aberto.")
        else:
            voice.speak("Não consegui abrir esse programa.")
        return True

    if kind == "FECHAR":
        program = intent.get("program")
        if program and close_program(program):
            voice.speak(f"{program} fechado.")
        else:
            voice.speak(f"{program or 'Esse programa'} não está aberto.")
        return True

    return False


class VoiceOutput:
    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 195)
        self.engine.setProperty("volume", 1.0)

    def speak(self, text):
        print("ALFA:", text)
        self.engine.say(text)
        self.engine.runAndWait()


def main():
    print("=" * 65)
    print("                         ALFA PRO")
    print("             VOZ + NLU SEMÂNTICO + AÇÃO LOCAL")
    print("=" * 65)

    nlu = ALFAIntent()
    stt = FastVoice()
    voice = VoiceOutput()

    voice.speak("ALFA iniciado. Estou pronto.")

    while True:
        try:
            text = stt.listen()

            if not text:
                continue

            if re.search(
                r"\b(sair|saia|encerre o alfa|pare o alfa)\b",
                nlu.normalize(text),
            ):
                voice.speak("Encerrando o ALFA.")
                break

            intent = nlu.parse(text)

            print("INTENÇÃO:", intent)

            if execute(intent, voice):
                continue

            # Somente aqui entra o cérebro conversacional.
            print("ALFA: consulta complexa...")
            answer = brain_fallback(text)
            voice.speak(answer[:500])

        except KeyboardInterrupt:
            print("\nALFA encerrado.")
            break

        except Exception as exc:
            print("ERRO:", exc)
            try:
                voice.speak("Ocorreu um erro.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
'@

Set-Content -Path (Join-Path $core "alfa_pro.py") -Value $py -Encoding UTF8

# Dependência de voz
& $python -m pip install -U pyttsx3

& $python -m py_compile (Join-Path $core "alfa_pro.py")

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao compilar core\alfa_pro.py"
}

Write-Host ""
Write-Host "ALFA PRO instalado e compilado." -ForegroundColor Green
Write-Host "Backup criado em: $backup" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Para iniciar:" -ForegroundColor Cyan
Write-Host ".\.venv311\Scripts\python.exe .\core\alfa_pro.py" -ForegroundColor Yellow
