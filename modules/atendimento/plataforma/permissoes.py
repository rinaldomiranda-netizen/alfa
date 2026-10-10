"""Perfis e permissões do RMD Atendimento.

Uma tabela única (recurso x ação -> perfis). O servidor confere TODA
chamada por aqui — esconder um botão na tela nunca é a proteção.

Perfis (do mais amplo ao mais restrito):
- owner       — ALFA OWNER/ADMIN: administra a plataforma e todas as empresas.
- admin       — Administrador do cliente: administra a própria empresa.
- supervisor  — Funcionário com gestão de equipe.
- atendente   — Funcionário que atende as conversas.
- cliente     — Cliente/usuário final: só vê as próprias conversas,
                orçamentos e agendamentos (portal do cliente).
"""
from __future__ import annotations

PERFIS = ("owner", "admin", "supervisor", "atendente", "cliente")

NOMES_PERFIS = {
    "owner": "ALFA Owner / Admin",
    "admin": "Administrador do cliente",
    "supervisor": "Supervisor",
    "atendente": "Atendente",
    "cliente": "Cliente",
}

# Perfis do Laboratório de Módulos do ALFA -> perfil real do Atendimento.
PERFIS_LABORATORIO = {
    "owner": "owner",
    "cliente_admin": "admin",
    "funcionario": "atendente",
    "cliente": "cliente",
}

EQUIPE = ("owner", "admin", "supervisor", "atendente")
GESTAO = ("owner", "admin", "supervisor")
ADMINS = ("owner", "admin")

MATRIZ: dict[str, dict[str, tuple[str, ...]]] = {
    "dashboard": {"ver": EQUIPE},
    "conversas": {"ver": EQUIPE, "responder": EQUIPE, "atribuir": GESTAO, "encerrar": EQUIPE},
    "contatos": {"ver": EQUIPE, "criar": EQUIPE, "editar": EQUIPE, "excluir": ADMINS},
    "filas": {"ver": EQUIPE, "criar": ADMINS, "editar": ADMINS},
    "orcamentos": {"ver": EQUIPE, "criar": EQUIPE, "editar": EQUIPE, "enviar": EQUIPE},
    "servicos": {"ver": EQUIPE, "criar": ADMINS, "editar": ADMINS},
    "fluxos": {"ver": GESTAO, "criar": ADMINS, "editar": ADMINS, "publicar": ADMINS, "simular": GESTAO},
    "agenda": {"ver": EQUIPE, "criar": EQUIPE, "editar": EQUIPE},
    "whatsapp": {"ver": ADMINS, "configurar": ADMINS, "testar": ADMINS},
    "api": {"ver": ADMINS, "configurar": ADMINS},
    "alertas": {"ver": EQUIPE, "marcar": EQUIPE},
    "relatorios": {"ver": GESTAO, "exportar": GESTAO},
    "usuarios": {"ver": ADMINS, "criar": ADMINS, "editar": ADMINS},
    "backup": {"ver": ADMINS, "criar": ADMINS, "restaurar": ADMINS},
    "plano": {"ver": ADMINS, "alterar": ("owner",)},
    "seguranca": {"ver": EQUIPE, "auditoria": ADMINS},
    "config": {"ver": ADMINS, "editar": ADMINS},
    "empresas": {"ver": ("owner",), "criar": ("owner",), "editar": ("owner",)},
    "portal": {"ver": ("cliente",), "decidir_orcamento": ("cliente",), "mensagem": ("cliente",)},
    "recepcao": {"usar": EQUIPE},
    # Valores em dinheiro (preços, totais, descontos) — a função pode ser desligada por igreja pelo RMD Desenvolvedor.
    "valores": {"ver": EQUIPE + ("cliente",)},
    # RMD Atendimento Church
    "visitantes": {"ver": EQUIPE, "criar": EQUIPE, "editar": EQUIPE},
    "oracoes": {"ver": EQUIPE, "criar": EQUIPE, "editar": EQUIPE, "pastoral": GESTAO},
    # Organização da igreja: Sede (a empresa) → setores / campos → igrejas / congregações.
    # Quem está lotado numa parte só enxerga essa parte e o que fica abaixo dela.
    "organizacao": {"ver": EQUIPE, "editar": ADMINS},
}

# Telas que só existem na edição Church.
TELAS_CHURCH = ("guests", "prayers", "org")

# Telas do menu, na ordem do protótipo aprovado. (chave, recurso exigido)
TELAS = (
    ("dash", "dashboard"), ("chat", "conversas"), ("names", "contatos"), ("queues", "filas"),
    ("quotes", "orcamentos"), ("services", "servicos"), ("flows", "fluxos"), ("agenda", "agenda"),
    ("whatsapp", "whatsapp"), ("api", "api"), ("alerts", "alertas"),
    ("reports", "relatorios"), ("users", "usuarios"), ("backup", "backup"), ("plan", "plano"),
    ("security", "seguranca"), ("settings", "config"), ("companies", "empresas"),
    ("portal", "portal"), ("guests", "visitantes"), ("prayers", "oracoes"), ("org", "organizacao"),
)


class SemPermissao(Exception):
    """Levantada quando o perfil não pode executar a ação."""


def pode(perfil: str | None, recurso: str, acao: str = "ver") -> bool:
    return bool(perfil) and perfil in MATRIZ.get(recurso, {}).get(acao, ())


def exigir(perfil: str | None, recurso: str, acao: str = "ver") -> None:
    if not pode(perfil, recurso, acao):
        raise SemPermissao(f"O perfil '{NOMES_PERFIS.get(perfil or '', perfil)}' não pode '{acao}' em '{recurso}'.")


def telas_do_perfil(perfil: str, church: bool = False) -> list[str]:
    return [tela for tela, recurso in TELAS
            if (pode(perfil, recurso, "ver") or (recurso == "portal" and perfil == "cliente")) and (church or tela not in TELAS_CHURCH)]


def permissoes_do_perfil(perfil: str) -> dict[str, list[str]]:
    return {
        recurso: [acao for acao, perfis in acoes.items() if perfil in perfis]
        for recurso, acoes in MATRIZ.items()
        if any(perfil in perfis for perfis in acoes.values())
    }


def perfis_que_pode_criar(perfil: str) -> tuple[str, ...]:
    if perfil == "owner":
        return ("admin", "supervisor", "atendente", "cliente")
    if perfil == "admin":
        return ("admin", "supervisor", "atendente", "cliente")
    return ()
