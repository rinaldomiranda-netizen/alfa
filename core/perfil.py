"""
Estrutura de perfil organizacional — FASE B da expansão de plataforma
(skills / marketplace / perfis empresariais / integrações / totem /
devices / cloud admin / updater / mobile).

    Empresa -> Filial -> Departamento -> Usuário -> Cargo -> Terminal -> BETA

Compatível com o perfil simples já existente em
launcher/iniciar_portatil.py (config["perfil"] = {"tipo": "pessoa" |
"organizacao", "nome": ...}) — os campos novos são todos OPCIONAIS,
com default None/vazio, então um perfil antigo (só tipo+nome)
continua funcionando sem nenhuma mudança.

Nunca contém dado de uma empresa real dentro do código: tudo vem de
configuração (perfil.json de cada perfil local, ver
launcher/iniciar_portatil.py -> preparar_config_portatil).
"""

CAMPOS_OPCIONAIS = ("filial", "departamento", "cargo", "terminal", "usuario_id")


def construir_perfil(tipo, nome, **extras):
    """
    Monta um dict de perfil compatível com o formato já usado em
    config["perfil"] — acrescenta campos organizacionais só quando
    informados; nunca inventa valor para um campo não fornecido.
    """
    perfil = {"tipo": tipo, "nome": nome}
    for campo in CAMPOS_OPCIONAIS:
        perfil[campo] = extras.get(campo)
    perfil["habilidades_habilitadas"] = extras.get("habilidades_habilitadas") or []
    perfil["configuracoes"] = extras.get("configuracoes") or {}
    return perfil


def descricao_hierarquica(perfil):
    """
    Texto legível "Empresa > Filial > Departamento (Cargo, terminal:
    X)" — só com os campos que existirem de verdade, nunca inventa
    nenhum nível que não foi configurado.
    """
    if not perfil:
        return ""

    partes = [perfil.get("nome")]
    for campo in ("filial", "departamento"):
        valor = perfil.get(campo)
        if valor:
            partes.append(valor)
    linha = " > ".join(p for p in partes if p)

    extra = []
    if perfil.get("cargo"):
        extra.append(perfil["cargo"])
    if perfil.get("terminal"):
        extra.append(f"terminal: {perfil['terminal']}")
    if extra:
        linha += f" ({', '.join(extra)})"

    return linha
