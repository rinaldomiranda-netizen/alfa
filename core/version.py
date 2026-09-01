"""
Versão central da BETA (item 21 do pedido de expansão de plataforma)
— compatibilidade entre CORE/SKILLS/CLOUD/PORTÁTIL/MOBILE.

Formato major.minor.patch. Incrementar PATCH para correções, MINOR
para funcionalidade nova compatível, MAJOR para mudança que quebra
compatibilidade entre componentes.
"""

VERSAO_CORE = "1.0.0"

# Versão de cada componente — permite saber se um pacote de skill ou
# um cliente (portátil/mobile) foi feito para uma versão de CORE
# compatível antes de instalar/conectar (ver agente/skill_registry.py
# e launcher/atualizar_portatil.py).
COMPONENTES = {
    "core": VERSAO_CORE,
    "skills": "1.0.0",
    # BETA-CLOUD hoje é só a fila local de eventos (memory/sync.py) —
    # versão baixa de propósito, reflete que o backend remoto ainda
    # não existe (ver relatório da expansão de plataforma).
    "cloud": "0.1.0",
    "portatil": "1.0.0",
    "mobile": "0.0.0",  # ainda não implementado
}


def versao_completa():
    return {"core": VERSAO_CORE, "componentes": dict(COMPONENTES)}


def compativel(componente, versao_exigida_minima):
    """
    Comparação simples major.minor.patch — True se a versão instalada
    do componente for >= à mínima exigida. Usado por quem instala uma
    skill/pacote (ver agente/skill_registry.py) para recusar algo feito
    para uma versão de CORE mais nova do que a instalada, em vez de
    deixar falhar de forma confusa depois.
    """
    atual = COMPONENTES.get(componente)
    if atual is None:
        return False

    def _partes(v):
        return tuple(int(p) for p in v.split("."))

    try:
        return _partes(atual) >= _partes(versao_exigida_minima)
    except (ValueError, AttributeError):
        return False
