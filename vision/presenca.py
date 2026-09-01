"""
Detecção de presença por câmera — usada só no MODO ATENDIMENTO (ver
core/alfa_core.py) para decidir quando iniciar uma saudação.

NÃO é reconhecimento facial: só confirma que existe uma região com
formato de rosto na imagem, usando o classificador Haar cascade que já
vem embutido na instalação do OpenCV (nenhum modelo novo, nenhum dado
enviado para fora). Não identifica quem é a pessoa, não salva nem
envia a imagem a lugar nenhum — o frame é descartado assim que a
checagem termina.

Fluxo correto (ver especificação): presença -> saudação -> conversa ->
consentimento -> só então fotografar (a fotografia, quando necessária,
continua sendo responsabilidade de vision/vision.py e do fluxo de
atendimento existente, não deste módulo).
"""

_cascade = None


def _carregar_cascade():
    global _cascade
    if _cascade is None:
        import cv2
        caminho = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(caminho)
    return _cascade


def alguem_presente(indice_camera=0):
    """
    Abre a câmera por um instante, verifica se há um rosto na imagem e
    fecha a câmera imediatamente. Retorna False (nunca levanta
    exceção) se a câmera não estiver disponível — a Beta simplesmente
    não terá o gatilho de presença, sem quebrar o resto do programa.
    """
    try:
        import cv2

        cascade = _carregar_cascade()
        camera = cv2.VideoCapture(indice_camera, cv2.CAP_DSHOW)
        try:
            if not camera.isOpened():
                return False

            # Descarta o primeiro frame (alguns webcams entregam um
            # quadro preto/incompleto logo na abertura) e usa o
            # segundo para a checagem de verdade.
            camera.read()
            ok, frame = camera.read()
            if not ok or frame is None:
                return False

            cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rostos = cascade.detectMultiScale(
                cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
            )
            return len(rostos) > 0
        finally:
            camera.release()
    except Exception:
        return False
