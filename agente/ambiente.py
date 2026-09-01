"""
Descoberta de ambiente — a BETA verifica o computador em que está
rodando em vez de assumir hardware/software fixos (base para a futura
versão portátil, ver relatório de auditoria arquitetural).

`detectar_ambiente()` nunca lança exceção: cada checagem é isolada, e
uma falha numa delas (ex.: sem câmera) só significa aquele campo vir
como None/False, nunca derruba o restante da descoberta.
"""

import os
import shutil
import socket
import time
import urllib.request

OLLAMA_URL_PADRAO = "http://127.0.0.1:11434/api/tags"

# Perfis de hardware (fase final) — só uma CLASSIFICAÇÃO informativa
# do que a máquina aguenta, nunca uma exigência: nenhum perfil requer
# GPU nem modelo pesado, e o comportamento atual (Whisper small,
# modelo pequeno no planejador) não muda sozinho por causa disto.
NIVEL_ECO = "eco"
NIVEL_BALANCEADO = "balanceado"
NIVEL_AVANCADO = "avancado"
NIVEL_GPU = "gpu"


def classificar_hardware(ambiente):
    """Classifica com base só no que detectar_ambiente() já mediu."""
    if ambiente.get("gpu_cuda_disponivel"):
        return NIVEL_GPU
    ram = ambiente.get("ram_total_gb") or 0
    cpus = ambiente.get("cpus_logicos") or 0
    if ram >= 16 and cpus >= 8:
        return NIVEL_AVANCADO
    if ram >= 8 and cpus >= 4:
        return NIVEL_BALANCEADO
    return NIVEL_ECO


def _cpu_ram():
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "cpus_logicos": os.cpu_count(),
            "ram_total_gb": round(mem.total / (1024 ** 3), 1),
            "ram_disponivel_gb": round(mem.available / (1024 ** 3), 1),
        }
    except Exception:
        return {"cpus_logicos": os.cpu_count(), "ram_total_gb": None, "ram_disponivel_gb": None}


def _gpu():
    try:
        import ctranslate2
        tem_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        tem_cuda = False
    return {"gpu_cuda_disponivel": tem_cuda}


def _microfone():
    try:
        import sounddevice as sd
        dispositivo = sd.query_devices(kind="input")
        return {"microfone_padrao": dispositivo.get("name"), "microfone_disponivel": True}
    except Exception:
        return {"microfone_padrao": None, "microfone_disponivel": False}


def _camera():
    try:
        import cv2
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        disponivel = cam.isOpened()
        cam.release()
        return {"camera_disponivel": disponivel}
    except Exception:
        return {"camera_disponivel": False}


def _armazenamento():
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uso = shutil.disk_usage(base)
        return {"disco_livre_gb": round(uso.free / (1024 ** 3), 1)}
    except Exception:
        return {"disco_livre_gb": None}


def _internet(timeout_segundos=1.5):
    try:
        socket.setdefaulttimeout(timeout_segundos)
        socket.create_connection(("1.1.1.1", 53))
        return {"internet_disponivel": True}
    except Exception:
        return {"internet_disponivel": False}


def _aplicativos_conhecidos():
    from agente import descoberta_apps
    encontrados = {}
    for nome in sorted(set(descoberta_apps.NOMES_EXECUTAVEL.keys())):
        caminho = descoberta_apps.localizar_executavel(nome)
        if caminho:
            encontrados[nome] = caminho
    return {"aplicativos_encontrados": encontrados}


def _modelos_locais(url=OLLAMA_URL_PADRAO, timeout_segundos=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout_segundos) as resposta:
            import json
            dados = json.loads(resposta.read().decode("utf-8"))
            modelos = [m.get("name") for m in dados.get("models", [])]
            return {"ollama_disponivel": True, "ollama_modelos": modelos}
    except Exception:
        return {"ollama_disponivel": False, "ollama_modelos": []}


def detectar_ambiente():
    """
    Roda todas as checagens (rápidas, best-effort) e devolve um dict
    único. Pensado para rodar UMA VEZ na inicialização (ver
    core/alfa_core.py) — nunca em loop, nunca bloqueando o assistente.
    """
    inicio = time.monotonic()
    ambiente = {}
    for checagem in (
        _cpu_ram, _gpu, _microfone, _camera, _armazenamento,
        _internet, _aplicativos_conhecidos, _modelos_locais,
    ):
        try:
            ambiente.update(checagem())
        except Exception as erro:
            ambiente[f"erro_{checagem.__name__}"] = str(erro)

    ambiente["_tempo_deteccao_segundos"] = round(time.monotonic() - inicio, 2)
    return ambiente


def salvar_ambiente(ambiente, caminho=None):
    """Persiste o resultado em memory/ambiente.json — só dados de
    configuração local (nenhum dado pessoal de atendimento)."""
    import json

    if caminho is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        caminho = os.path.join(base, "memory", "ambiente.json")

    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(ambiente, arquivo, ensure_ascii=False, indent=2)
        return caminho
    except Exception:
        return None
