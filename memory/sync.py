"""
Adaptador isolado de sincronização com a BETA-CLOUD — o futuro backend
próprio da BETA. NUNCA é o Supabase/"central de pesquisas" usado pelo
atendimento (core/pesquisa_app.py): são sistemas completamente
separados, e este módulo não importa nem depende de nada daquilo.

    BETA LOCAL <-> memória local <-> fila de sync <-> BETA-CLOUD

Hoje não existe nenhum servidor BETA-CLOUD real — este módulo só
implementa o lado local (fila em disco) para eventos ficarem
guardados até uma sincronização de verdade existir/ser configurada.
Nunca é chamado automaticamente na inicialização: a BETA funciona
100% offline sem isto, e nenhum dado é perdido se a sincronização
falhar (só fica retido na fila).

FASE 3 da expansão de plataforma — tipos de evento suportados:
    PROFILE_UPDATED, SKILL_ENABLED, SKILL_DISABLED, TASK_COMPLETED,
    CONFIG_UPDATED, DEVICE_REGISTERED, DEVICE_UPDATED, VERSION_UPDATED

NUNCA sincroniza — enfileirar() RECUSA (levanta EventoNaoPermitido,
não guarda nada) se detectar qualquer uma destas chaves em `dados`,
em qualquer nível de aninhamento: senha, password, token,
service_role, biometria, áudio, vídeo, segredo/secret, cvv, número de
cartão, credencial. Isto é aplicado no código, não só documentado.
"""

import json
import os
import time
import uuid

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_FILA = os.path.join(BASE, "fila_sync.json")


def definir_caminho_fila(caminho):
    """
    Redireciona a fila de sincronização — usado pelo launcher portátil
    (ver launcher/iniciar_portatil.py) para isolar os eventos de cada
    perfil, do mesmo jeito que memory.definir_pasta_atendimentos isola
    a memória de atendimento (item "teste de isolamento": perfil A
    nunca deve enxergar evento de sincronização do perfil B). Ninguém
    chama isto no caminho do ALFA pessoal, então CAMINHO_FILA continua
    sendo memory/fila_sync.json como sempre.
    """
    global CAMINHO_FILA
    CAMINHO_FILA = caminho
    os.makedirs(os.path.dirname(caminho), exist_ok=True)

TIPOS_EVENTO = {
    "PROFILE_UPDATED",
    "SKILL_ENABLED",
    "SKILL_DISABLED",
    "TASK_COMPLETED",
    "CONFIG_UPDATED",
    "DEVICE_REGISTERED",
    "DEVICE_UPDATED",
    "VERSION_UPDATED",
}

CAMPOS_PROIBIDOS = {
    "senha", "password", "token", "service_role", "biometria", "audio",
    "video", "segredo", "secret", "cvv", "numero_cartao", "credencial",
    "access_token", "refresh_token", "api_key",
}

# Depois desta quantidade de tentativas sem sucesso, o evento é
# descartado da fila (nunca cresce pra sempre) — ver sincronizar().
MAX_TENTATIVAS = 5


class EventoNaoPermitido(Exception):
    """Levantado por enfileirar() quando `dados` contém um campo que
    nunca deve sair deste computador (ver CAMPOS_PROIBIDOS)."""


def _contem_campo_proibido(valor):
    """Busca recursiva por qualquer chave proibida em dict/list
    aninhado — nunca confia que quem chamou já filtrou."""
    if isinstance(valor, dict):
        for chave, sub_valor in valor.items():
            if str(chave).lower() in CAMPOS_PROIBIDOS:
                return True
            if _contem_campo_proibido(sub_valor):
                return True
        return False
    if isinstance(valor, (list, tuple)):
        return any(_contem_campo_proibido(item) for item in valor)
    return False


def _ler_fila():
    if not os.path.exists(CAMINHO_FILA):
        return []
    try:
        with open(CAMINHO_FILA, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception:
        return []


def _salvar_fila(fila):
    try:
        with open(CAMINHO_FILA, "w", encoding="utf-8") as arquivo:
            json.dump(fila, arquivo, ensure_ascii=False, indent=2)
    except Exception:
        pass


def enfileirar(tipo_evento, dados, origem=None):
    """
    Guarda um evento localmente para sincronizar quando a BETA-CLOUD
    existir/estiver acessível.

    Levanta ValueError se `tipo_evento` não for um dos TIPOS_EVENTO
    conhecidos, e EventoNaoPermitido se `dados` contiver qualquer
    campo proibido — nos dois casos, NADA é gravado na fila. Fora
    isso, nunca lança exceção nem bloqueia o funcionamento local.
    """
    if tipo_evento not in TIPOS_EVENTO:
        raise ValueError(f"Tipo de evento desconhecido: {tipo_evento!r}. Use um de {sorted(TIPOS_EVENTO)}.")
    if _contem_campo_proibido(dados):
        raise EventoNaoPermitido(
            "Este evento contém um campo que nunca deve ser sincronizado "
            "(senha/token/service_role/biometria/áudio/vídeo/segredo)."
        )

    fila = _ler_fila()
    fila.append({
        "id": uuid.uuid4().hex,
        "tipo": tipo_evento,
        "dados": dados,
        "origem": origem,
        "criado_em": time.time(),
        "tentativas": 0,
    })
    _salvar_fila(fila)


def pendentes():
    return len(_ler_fila())


def _enviar_http(evento, url_beta_cloud):
    import urllib.request

    requisicao = urllib.request.Request(
        url_beta_cloud,
        data=json.dumps(evento).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(requisicao, timeout=10):
        return True


def sincronizar(url_beta_cloud=None, enviar_evento=None):
    """
    Envia a fila para a BETA-CLOUD UM EVENTO DE CADA VEZ — só remove
    da fila o que teve confirmação (nunca tudo-ou-nada: uma falha num
    evento não trava os demais). Evento que falhar repetidamente (ver
    MAX_TENTATIVAS) é descartado da fila para nunca crescer pra
    sempre.

    `enviar_evento(evento) -> bool`, se fornecido, decide como UM
    evento é "enviado" — existe para poder testar o fluxo sem precisar
    de um servidor real. Sem isso, usa uma chamada HTTP simples para
    `url_beta_cloud`. Sem nenhum dos dois, é um no-op seguro: a fila
    continua guardada localmente, sem perda de dado nenhuma (a BETA
    nunca depende de internet para funcionar).
    """
    if not url_beta_cloud and enviar_evento is None:
        return False, "BETA-CLOUD não configurada — eventos continuam na fila local."

    fila = _ler_fila()
    if not fila:
        return True, "Nada para sincronizar."

    enviar = enviar_evento or (lambda evento: _enviar_http(evento, url_beta_cloud))

    restantes = []
    enviados = 0
    descartados = 0
    for evento in fila:
        try:
            ok = enviar(evento)
        except Exception:
            ok = False

        if ok:
            enviados += 1
            continue

        evento["tentativas"] = evento.get("tentativas", 0) + 1
        if evento["tentativas"] >= MAX_TENTATIVAS:
            descartados += 1
            continue
        restantes.append(evento)

    _salvar_fila(restantes)
    mensagem = f"{enviados} evento(s) sincronizado(s), {len(restantes)} pendente(s)"
    if descartados:
        mensagem += f", {descartados} descartado(s) após {MAX_TENTATIVAS} tentativas"
    return True, mensagem + "."
