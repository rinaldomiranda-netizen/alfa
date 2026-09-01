"""
Motor de voz neural da Azure AI Speech (Microsoft) — MOTOR ALTERNATIVO
do ALFA (o motor principal é edge_tts.py, que usa a mesma família de
vozes neurais sem exigir chave paga; ver voice/tts/edge_tts_engine.py).

Vale a pena migrar para este motor se, no futuro, for preciso de SLA
comercial, maior estabilidade de infraestrutura, ou os estilos de voz
via SSML nativos que o endpoint gratuito do Edge não expõe.

Por quê Azure e não Google Cloud Chirp 3 HD ou ElevenLabs (pesquisa
comparativa feita antes de implementar):

  - Vozes nativas em português do Brasil (pt-BR-ThalitaMultilingualNeural,
    pt-BR-FranciscaNeural), treinadas especificamente para o idioma,
    não apenas um modelo multilíngue genérico aplicado ao português.
  - Suporte nativo a ESTILOS de fala via SSML (`<mstts:express-as>`)
    — é literalmente o mecanismo que permite a personalidade
    controlar a entonação (alegre, calma, empática...) sem precisar
    reescrever o texto. Nem Chirp 3 HD nem a API bruta de outros
    provedores oferecem esse controle discreto e nomeado.
  - Menor custo entre as três opções neurais avaliadas: US$ 15 por
    milhão de caracteres (voz neural padrão) ou US$ 22/milhão (HD),
    contra US$ 30/milhão do Chirp 3 HD e ~US$ 100/milhão da
    ElevenLabs — com tier gratuito mensal que cobre uso pessoal
    diário confortavelmente.
  - Integração mais simples: só uma chave de API + região; sem
    projeto de nuvem, IAM ou service account (como o Google exige).
  - Latência baixa em streaming, adequada para um assistente de voz
    conversacional.

ElevenLabs continua sendo a opção de maior expressividade emocional
"crua" (ver voice/tts/elevenlabs_tts.py) e está pronta para uso —
basta mudar `voz_saida.motor` em config/alfa.json.

Requer:
    pip install azure-cognitiveservices-speech   (já instalado no venv)
    variáveis de ambiente AZURE_SPEECH_KEY e AZURE_SPEECH_REGION
"""

import os

try:
    import azure.cognitiveservices.speech as speechsdk
except Exception:
    speechsdk = None

from voice.tts.base import TTSEngine

# Estilos de fala suportados via SSML <mstts:express-as>. Nem toda
# voz suporta todo estilo listado aqui — mas a Azure ignora
# silenciosamente estilos não suportados pela voz escolhida (cai
# para o estilo neutro em vez de dar erro), então é seguro mapear de
# forma generosa.
MAPA_ESTILO = {
    "saudacao": "friendly",
    "confirmacao": "friendly",
    "descontraida": "cheerful",
    "engracada": "cheerful",
    "seria": "calm",
    "empatica": "empathetic",
    "neutra": None,
}

VOZ_PADRAO = "pt-BR-ThalitaMultilingualNeural"


def _escapar_ssml(texto):
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class AzureTTSEngine(TTSEngine):
    nome = "azure"

    def __init__(
        self,
        voz=VOZ_PADRAO,
        chave_env="AZURE_SPEECH_KEY",
        regiao_env="AZURE_SPEECH_REGION",
    ):
        if speechsdk is None:
            raise RuntimeError(
                "azure-cognitiveservices-speech não está instalado. "
                "Rode: pip install azure-cognitiveservices-speech"
            )

        chave = os.environ.get(chave_env)
        regiao = os.environ.get(regiao_env)

        if not chave or not regiao:
            raise RuntimeError(
                f"Configure as variáveis de ambiente {chave_env} e {regiao_env} "
                "com sua chave e região do Azure AI Speech (portal.azure.com "
                "-> Azure AI services -> Speech)."
            )

        self._speechsdk = speechsdk
        self.voz = voz

        speech_config = speechsdk.SpeechConfig(subscription=chave, region=regiao)
        speech_config.speech_synthesis_voice_name = voz

        # Reproduz direto no alto-falante padrão do Windows: o SDK
        # cuida da fila de áudio, não precisamos de sounddevice aqui.
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

        self.synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

    def _montar_ssml(self, texto, estilo_azure):
        texto_escapado = _escapar_ssml(texto)

        if not estilo_azure:
            corpo = texto_escapado
        else:
            corpo = f'<mstts:express-as style="{estilo_azure}">{texto_escapado}</mstts:express-as>'

        return (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="pt-BR">'
            f'<voice name="{self.voz}">{corpo}</voice>'
            "</speak>"
        )

    def falar(self, texto, estilo=None):
        estilo_azure = MAPA_ESTILO.get(estilo)
        ssml = self._montar_ssml(texto, estilo_azure)

        resultado = self.synthesizer.speak_ssml_async(ssml).get()

        if resultado.reason != self._speechsdk.ResultReason.SynthesizingAudioCompleted:
            detalhes = resultado.cancellation_details
            motivo = detalhes.error_details if detalhes else resultado.reason
            raise RuntimeError(f"Falha na síntese Azure TTS: {motivo}")
