"""
Visão LOCAL da tela (sem IA externa): captura + OCR.

Complementa vision/vision.py (que usa um modelo de IA multimodal via
Ollama para descrições abertas em linguagem natural) com uma via
100% local, offline e determinística — usada pela automação
orientada a elementos (computer/form_filler.py) e pelo fluxo de
atendimento (core/atendimento.py) para localizar texto na tela
quando a árvore de UI Automation não está disponível.

OCR via o motor nativo do Windows (Windows.Media.Ocr, acessado pelo
pacote `winsdk`) — roda totalmente offline, usando o pacote de
idioma já instalado no sistema, sem chave de API e sem precisar
instalar o Tesseract separadamente.
"""

import asyncio
import io

import pyautogui

_OCR_ENGINE = None
_OCR_INDISPONIVEL_MOTIVO = None


def _obter_motor_ocr():
    global _OCR_ENGINE, _OCR_INDISPONIVEL_MOTIVO

    if _OCR_ENGINE is not None or _OCR_INDISPONIVEL_MOTIVO is not None:
        return _OCR_ENGINE

    try:
        from winsdk.windows.globalization import Language
        from winsdk.windows.media.ocr import OcrEngine

        motor = None
        try:
            motor = OcrEngine.try_create_from_language(Language("pt"))
        except Exception:
            motor = None

        if motor is None:
            motor = OcrEngine.try_create_from_user_profile_languages()

        if motor is None:
            _OCR_INDISPONIVEL_MOTIVO = (
                "Nenhum idioma de OCR instalado no Windows. Instale um "
                "pacote de idioma com suporte a OCR em Configurações > "
                "Hora e idioma > Idioma e região."
            )
        else:
            _OCR_ENGINE = motor

    except Exception as erro:
        _OCR_INDISPONIVEL_MOTIVO = str(erro)

    return _OCR_ENGINE


def ocr_disponivel():
    return _obter_motor_ocr() is not None


def motivo_indisponibilidade():
    return _OCR_INDISPONIVEL_MOTIVO


def capturar_tela_pil():
    return pyautogui.screenshot()


async def _pil_para_softwarebitmap_async(imagem_pil):
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

    buffer_png = io.BytesIO()
    imagem_pil.save(buffer_png, format="PNG")
    dados = buffer_png.getvalue()

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(dados)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    return bitmap


async def _ler_texto_async(imagem_pil):
    motor = _obter_motor_ocr()
    if motor is None:
        raise RuntimeError(_OCR_INDISPONIVEL_MOTIVO or "OCR indisponível neste Windows.")

    bitmap = await _pil_para_softwarebitmap_async(imagem_pil)
    return await motor.recognize_async(bitmap)


def ler_texto_da_tela(regiao=None):
    """
    Executa OCR na tela (ou em `regiao` = (x1, y1, x2, y2)) atual.

    Retorna uma lista de linhas de texto detectadas, cada uma como:
        {"texto": str, "x": int, "y": int, "largura": int, "altura": int}
    onde (x, y) é o centro da linha em coordenadas ABSOLUTAS de tela
    (prontas para clique direto com pyautogui).
    """

    imagem = capturar_tela_pil()
    offset_x, offset_y = 0, 0

    if regiao:
        imagem = imagem.crop(regiao)
        offset_x, offset_y = regiao[0], regiao[1]

    resultado = asyncio.run(_ler_texto_async(imagem))

    linhas = []
    for linha in resultado.lines:
        palavras = list(linha.words)
        if not palavras:
            continue

        x_min = min(p.bounding_rect.x for p in palavras)
        y_min = min(p.bounding_rect.y for p in palavras)
        x_max = max(p.bounding_rect.x + p.bounding_rect.width for p in palavras)
        y_max = max(p.bounding_rect.y + p.bounding_rect.height for p in palavras)

        linhas.append({
            "texto": linha.text,
            "x": int((x_min + x_max) / 2) + offset_x,
            "y": int((y_min + y_max) / 2) + offset_y,
            "largura": int(x_max - x_min),
            "altura": int(y_max - y_min),
        })

    return linhas


def texto_da_tela_como_string(regiao=None):
    """
    Versão em texto único (linhas separadas por quebra de linha) de
    `ler_texto_da_tela()` — para quem só precisa do CONTEÚDO (ex.:
    comparar/normalizar/falar), não das coordenadas de cada linha.
    Devolve "" (nunca None) quando não há texto ou o OCR falhar, para
    nunca quebrar quem espera uma string.
    """
    try:
        linhas = ler_texto_da_tela(regiao)
    except Exception:
        return ""
    return "\n".join(linha["texto"] for linha in linhas if linha.get("texto"))


def localizar_texto(texto_procurado, regiao=None):
    """
    Procura uma linha de texto na tela cujo conteúdo contenha
    `texto_procurado` (comparação sem distinção de maiúsculas). Usado
    como plano B quando a UI Automation não encontra o elemento
    (vision/ui_automation.py é sempre tentada primeiro).

    Retorna o dict da linha encontrada ou None.
    """
    alvo = texto_procurado.strip().lower()
    if not alvo:
        return None

    for linha in ler_texto_da_tela(regiao):
        if alvo in linha["texto"].strip().lower():
            return linha

    return None
