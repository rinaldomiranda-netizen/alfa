"""
Captura de câmera com fluxo de consentimento obrigatório.

Usada para associar uma foto a um atendimento (ex.: registro de
comparecimento) — nunca para reconhecimento facial ou identificação
automática de pessoas.

Fluxo obrigatório (nenhuma etapa pode ser pulada):

    detectar câmera -> solicitar consentimento -> capturar foto
    -> mostrar prévia -> confirmar -> associar ao atendimento

Nenhuma foto é persistida em `memory/atendimentos/` antes do
consentimento explícito E da confirmação da prévia pela pessoa
fotografada (ver associar_ao_atendimento).
"""

import os
import time
import uuid

import cv2

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TEMP = os.path.join(BASE, "memory", "_temp_fotos")
PASTA_ATENDIMENTOS = os.path.join(BASE, "memory", "atendimentos")


def detectar_camera(indice=0):
    camera = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    disponivel = camera.isOpened()
    camera.release()
    return disponivel


class SessaoCamera:
    """
    Uma sessão de captura de foto vinculada a UM consentimento
    explícito. Crie uma nova instância para cada nova tentativa de
    foto — não reutilize uma sessão já confirmada ou recusada.
    """

    def __init__(self, indice_camera=0):
        self.indice_camera = indice_camera
        self.consentimento_dado = False
        self.caminho_preview = None
        self.confirmado = None  # None = ainda não decidido

    def solicitar_consentimento_texto(self):
        """Texto que a BETA deve falar antes de capturar a foto."""
        return (
            "Preciso da sua permissão para tirar uma foto para o "
            "atendimento. Posso tirar a foto agora?"
        )

    def registrar_consentimento(self, concedido):
        self.consentimento_dado = bool(concedido)
        return self.consentimento_dado

    def capturar_foto(self):
        if not self.consentimento_dado:
            raise PermissionError(
                "Não é permitido capturar uma foto sem consentimento explícito."
            )

        if not detectar_camera(self.indice_camera):
            raise RuntimeError("Nenhuma câmera disponível.")

        camera = cv2.VideoCapture(self.indice_camera, cv2.CAP_DSHOW)
        try:
            time.sleep(0.5)  # deixa a câmera estabilizar a exposição
            ok, frame = camera.read()
        finally:
            camera.release()

        if not ok:
            raise RuntimeError("Falha ao capturar imagem da câmera.")

        os.makedirs(PASTA_TEMP, exist_ok=True)
        self.caminho_preview = os.path.join(PASTA_TEMP, f"preview_{uuid.uuid4().hex}.jpg")
        cv2.imwrite(self.caminho_preview, frame)
        return self.caminho_preview

    def mostrar_previa(self):
        """Abre a prévia no visualizador padrão do Windows para a pessoa ver."""
        if not self.caminho_preview or not os.path.exists(self.caminho_preview):
            raise RuntimeError("Nenhuma prévia disponível para mostrar.")
        os.startfile(self.caminho_preview)
        return self.caminho_preview

    def confirmar(self, aceitar=True):
        self.confirmado = bool(aceitar)
        if not aceitar and self.caminho_preview and os.path.exists(self.caminho_preview):
            os.remove(self.caminho_preview)
            self.caminho_preview = None
        return self.confirmado

    def descartar_se_pendente(self):
        """
        Remove a prévia se a sessão for abandonada sem uma decisão
        final (nem confirmada, nem recusada) — ex.: o atendimento foi
        encerrado no meio do fluxo de foto. Nunca deixa uma imagem de
        uma sessão anterior disponível para a próxima (privacidade).
        """
        if self.confirmado is None and self.caminho_preview and os.path.exists(self.caminho_preview):
            os.remove(self.caminho_preview)
            self.caminho_preview = None

    def associar_ao_atendimento(self, atendimento_id):
        """
        Move a foto da pasta temporária para o armazenamento
        definitivo do atendimento. Só funciona se houve consentimento
        E confirmação explícita da prévia — qualquer outra condição
        levanta PermissionError, nunca persiste silenciosamente.
        """
        if not (self.consentimento_dado and self.confirmado):
            raise PermissionError(
                "Só é possível associar a foto após consentimento e "
                "confirmação da prévia pela pessoa fotografada."
            )
        if not self.caminho_preview or not os.path.exists(self.caminho_preview):
            raise RuntimeError("Nenhuma foto capturada para associar.")

        os.makedirs(PASTA_ATENDIMENTOS, exist_ok=True)
        destino = os.path.join(PASTA_ATENDIMENTOS, f"{atendimento_id}_foto.jpg")
        os.replace(self.caminho_preview, destino)
        self.caminho_preview = destino
        return destino
