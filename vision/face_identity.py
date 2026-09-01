"""
Reconhecimento facial LOCAL — recurso complementar de identificação.

IDENTIDADE ≠ AUTORIZAÇÃO: reconhecer um rosto nunca substitui as
permissões existentes (ver security/permissions.py — BASIC/FILES/
SYSTEM/SENSITIVE continuam exigindo confirmação como sempre). Um
rosto reconhecido só ajusta a SAUDAÇÃO e o contexto de quem está
falando, nunca autoriza uma ação sozinho.

Finalidade DIFERENTE da câmera de atendimento (vision/camera.py):
aquela tira UMA foto com consentimento explícito para anexar a um
atendimento; este módulo gera uma REPRESENTAÇÃO matemática do rosto
(nunca guarda a foto em si) para reconhecer quem está na frente da
câmera. Os dois fluxos, armazenamentos e propósitos nunca se
misturam — nenhuma imagem cadastrada aqui vai para
memory/atendimentos/, e nada daquele fluxo alimenta este.

100% local e privado:
  - nunca envia rosto/representação para internet;
  - nunca usa Supabase nem a BETA-CLOUD automaticamente;
  - nunca grava vídeo contínuo — só quadros isolados, sob demanda;
  - nunca guarda a foto original, só o modelo matemático treinado.

Biblioteca: OpenCV (cv2), já usado no projeto — Haar Cascade (já
embutido no pacote) para detecção e LBPH (cv2.face, requer
opencv-contrib-python) para reconhecimento. Escolha deliberada: evita
dlib/face_recognition (build pesado no Windows, CMake/Boost) e
qualquer framework de deep learning só para esta função. Sem
cv2.face instalado, reconhecimento_disponivel() volta False e a BETA
continua funcionando normalmente, só sem esse recurso (ver item 15).
"""

import json
import os
import time

import cv2
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_ROSTOS = os.path.join(BASE, "memory", "rostos")

MATCH_FORTE = "MATCH_FORTE"
MATCH_FRACO = "MATCH_FRACO"
UNKNOWN = "UNKNOWN"
NO_FACE = "NO_FACE"
MULTIPLE_FACES = "MULTIPLE_FACES"

# Distância LBPH (menor = mais parecido). Calibrado de forma
# conservadora: prefere UNKNOWN/FRACO a assumir uma identidade errada.
_LIMIAR_FORTE = 60.0
_LIMIAR_FRACO = 90.0

_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def definir_pasta_rostos(caminho):
    """
    Redireciona o armazenamento do cadastro facial — usado pelo
    launcher portátil (ver launcher/iniciar_portatil.py) para isolar o
    cadastro de cada perfil, do mesmo jeito que
    memory.definir_pasta_atendimentos isola a memória de atendimento.
    Ninguém chama isto no caminho do ALFA pessoal, então PASTA_ROSTOS
    continua sendo memory/rostos/ como sempre.
    """
    global PASTA_ROSTOS
    PASTA_ROSTOS = caminho
    os.makedirs(caminho, exist_ok=True)


def reconhecimento_disponivel():
    """False se o OpenCV instalado não tiver cv2.face (opencv-contrib)
    — a BETA continua normalmente sem reconhecimento facial nesse
    caso, sem erro fatal (ver itens 15/22)."""
    return hasattr(cv2, "face")


def camera_disponivel(indice_camera=0):
    """Reaproveita a MESMA checagem de vision/camera.py — sem
    duplicar lógica de abertura de câmera."""
    from vision.camera import detectar_camera
    return detectar_camera(indice_camera)


def _detector_rosto():
    detector = cv2.CascadeClassifier(_CASCADE_PATH)
    if detector.empty():
        raise RuntimeError("Não foi possível carregar o detector de rosto (Haar Cascade).")
    return detector


def _capturar_quadro(indice_camera=0):
    """Um único quadro da câmera — nunca vídeo contínuo (ver item 15).
    Retorna None sem levantar exceção se a câmera não puder ser usada;
    quem chama decide o que fazer sem câmera."""
    if not camera_disponivel(indice_camera):
        return None
    camera = cv2.VideoCapture(indice_camera, cv2.CAP_DSHOW)
    try:
        time.sleep(0.4)  # deixa a câmera estabilizar a exposição
        ok, frame = camera.read()
    finally:
        camera.release()
    return frame if ok else None


def _detectar_rostos(frame, detector=None):
    detector = detector or _detector_rosto()
    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cinza = cv2.equalizeHist(cinza)
    rostos = detector.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    return cinza, rostos


def _recortar_rosto(cinza, retangulo, tamanho=(200, 200)):
    x, y, w, h = retangulo
    return cv2.resize(cinza[y:y + h, x:x + w], tamanho)


def _caminho_modelo():
    return os.path.join(PASTA_ROSTOS, "modelo_lbph.yml")


def _caminho_rotulos():
    return os.path.join(PASTA_ROSTOS, "rotulos.json")


def _carregar_rotulos():
    caminho = _caminho_rotulos()
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return {int(k): v for k, v in json.load(arquivo).items()}
    except Exception:
        return {}


def _salvar_rotulos(rotulos):
    os.makedirs(PASTA_ROSTOS, exist_ok=True)
    with open(_caminho_rotulos(), "w", encoding="utf-8") as arquivo:
        json.dump({str(k): v for k, v in rotulos.items()}, arquivo, ensure_ascii=False, indent=2)


def cadastrar_rosto(nome, indice_camera=0, quadros_necessarios=5):
    """
    Captura alguns quadros isolados (nunca vídeo contínuo) e treina/
    atualiza o modelo LBPH local associando `nome` a esse rosto.

    Retorna (sucesso: bool, mensagem: str) — nunca finge sucesso sem
    ter capturado um rosto de verdade.
    """
    if not reconhecimento_disponivel():
        return False, "Reconhecimento facial não está disponível neste computador."

    if not camera_disponivel(indice_camera):
        return False, "Não encontrei nenhuma câmera disponível."

    detector = _detector_rosto()
    amostras = []
    tentativas = 0
    while len(amostras) < quadros_necessarios and tentativas < quadros_necessarios * 4:
        tentativas += 1
        frame = _capturar_quadro(indice_camera)
        if frame is None:
            continue
        cinza, rostos = _detectar_rostos(frame, detector)
        if len(rostos) != 1:
            # Sem rosto ou mais de um: descarta o quadro em vez de
            # arriscar treinar com a pessoa errada (ver item 10).
            continue
        amostras.append(_recortar_rosto(cinza, rostos[0]))
        time.sleep(0.3)

    if not amostras:
        return False, "Não consegui ver seu rosto com clareza para cadastrar. Tente em um local mais iluminado, olhando para a câmera."

    rotulos = _carregar_rotulos()
    nome_para_id = {v: k for k, v in rotulos.items()}
    rotulo_id = nome_para_id.get(nome, max(rotulos.keys(), default=-1) + 1)
    rotulos[rotulo_id] = nome

    reconhecedor = cv2.face.LBPHFaceRecognizer_create()
    caminho_modelo = _caminho_modelo()

    rotulos_array = np.array([rotulo_id] * len(amostras))
    if os.path.exists(caminho_modelo):
        # update() é incremental — preserva identidades já cadastradas
        # de outras pessoas sem precisar guardar as fotos delas.
        try:
            reconhecedor.read(caminho_modelo)
            reconhecedor.update(amostras, rotulos_array)
        except Exception:
            reconhecedor.train(amostras, rotulos_array)
    else:
        reconhecedor.train(amostras, rotulos_array)

    os.makedirs(PASTA_ROSTOS, exist_ok=True)
    reconhecedor.write(caminho_modelo)
    _salvar_rotulos(rotulos)

    return True, f"Identificação facial cadastrada para {nome}."


def remover_identidade(nome):
    """
    Remove `nome` do cadastro. O LBPH não permite excluir um rótulo
    sem retreinar do zero, e como nenhuma foto original é guardada
    (privacidade, ver item 18), remover uma identidade apaga o modelo
    inteiro — os demais nomes cadastrados precisam ser refeitos. Menos
    conveniente, mas evita manter imagens de rosto em disco só para
    permitir isso.
    """
    rotulos = _carregar_rotulos()
    ids_a_remover = [k for k, v in rotulos.items() if v == nome]
    if not ids_a_remover:
        return False, f"Não encontrei {nome} no cadastro."

    for caminho in (_caminho_modelo(), _caminho_rotulos()):
        if os.path.exists(caminho):
            os.remove(caminho)

    restantes = {k: v for k, v in rotulos.items() if k not in ids_a_remover}
    if restantes:
        _salvar_rotulos(restantes)
        return True, f"Removi {nome}. Como não guardo fotos, as outras identidades cadastradas precisam ser refeitas."
    return True, f"Removi {nome} do cadastro."


def identificar(indice_camera=0):
    """
    Captura UM quadro e tenta identificar quem está na câmera.

    Retorna {"estado": ..., "nome": str|None, "confianca": float|None}.
    Nunca escolhe arbitrariamente entre vários rostos (MULTIPLE_FACES)
    e nunca assume identidade com confiança fraca (ver item 10).
    """
    if not reconhecimento_disponivel() or not camera_disponivel(indice_camera):
        return {"estado": NO_FACE, "nome": None, "confianca": None}

    frame = _capturar_quadro(indice_camera)
    if frame is None:
        return {"estado": NO_FACE, "nome": None, "confianca": None}

    cinza, rostos = _detectar_rostos(frame)
    if len(rostos) == 0:
        return {"estado": NO_FACE, "nome": None, "confianca": None}
    if len(rostos) > 1:
        return {"estado": MULTIPLE_FACES, "nome": None, "confianca": None}

    caminho_modelo = _caminho_modelo()
    if not os.path.exists(caminho_modelo):
        return {"estado": UNKNOWN, "nome": None, "confianca": None}

    reconhecedor = cv2.face.LBPHFaceRecognizer_create()
    reconhecedor.read(caminho_modelo)
    rotulos = _carregar_rotulos()

    recorte = _recortar_rosto(cinza, rostos[0])
    rotulo_id, distancia = reconhecedor.predict(recorte)
    nome = rotulos.get(rotulo_id)

    if nome is None:
        return {"estado": UNKNOWN, "nome": None, "confianca": distancia}
    if distancia <= _LIMIAR_FORTE:
        return {"estado": MATCH_FORTE, "nome": nome, "confianca": distancia}
    if distancia <= _LIMIAR_FRACO:
        return {"estado": MATCH_FRACO, "nome": nome, "confianca": distancia}
    return {"estado": UNKNOWN, "nome": None, "confianca": distancia}
