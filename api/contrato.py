"""
Contrato de API BETA — FASE 7 da expansão de plataforma.

APENAS CONTRATO: não há servidor rodando aqui. Documenta os
endpoints que um futuro serviço BETA-CLOUD real precisaria expor para
clientes (mobile, admin, outro desktop) — como referência para quem
for implementar o servidor de verdade (fora do escopo desta sessão:
exige escolha de hospedagem, framework web e banco de dados que não
foram definidos).

Regras que qualquer implementação real deste contrato PRECISA seguir
(ver item 7 do pedido de expansão):
  - autenticação obrigatória em todo endpoint, exceto onde marcado;
  - validar permissão no SERVIDOR, nunca confiar em flag mandada pelo
    cliente;
  - nunca devolver service_role, senha, token de terceiro ou
    biometria em nenhuma resposta.

Endpoints:
    POST /auth              autenticar (usuário/dispositivo) -> token de sessão
    GET  /profile            perfil do usuário/organização autenticado
    GET  /devices            dispositivos do perfil autenticado
    GET  /skills              habilidades disponíveis para o perfil
    POST /skills/<id>/enable  ativar uma habilidade (ADMIN)
    POST /skills/<id>/disable desativar uma habilidade (ADMIN)
    GET  /tasks               tarefas/eventos recentes (ver memory/sync.py)
    POST /sync                 enviar fila de eventos locais (ver memory/sync.py)
    GET  /version              versão do CORE/componentes compatíveis
"""

from dataclasses import dataclass, field


@dataclass
class Endpoint:
    metodo: str
    caminho: str
    descricao: str
    requer_autenticacao: bool = True
    categoria_permissao: str = None  # ver security/permissions.py


ENDPOINTS = [
    Endpoint("POST", "/auth", "Autenticar usuário/dispositivo, devolve token de sessão.", requer_autenticacao=False),
    Endpoint("GET", "/profile", "Perfil do usuário/organização autenticado."),
    Endpoint("GET", "/devices", "Dispositivos vinculados ao perfil autenticado."),
    Endpoint("GET", "/skills", "Habilidades disponíveis para o perfil."),
    Endpoint("POST", "/skills/<id>/enable", "Ativar uma habilidade.", categoria_permissao="ADMIN"),
    Endpoint("POST", "/skills/<id>/disable", "Desativar uma habilidade.", categoria_permissao="ADMIN"),
    Endpoint("GET", "/tasks", "Tarefas/eventos recentes não sensíveis."),
    Endpoint("POST", "/sync", "Recebe a fila de eventos locais (ver memory/sync.py)."),
    Endpoint("GET", "/version", "Versão do CORE e componentes compatíveis (ver core/version.py)."),
]


def listar_contrato():
    return [
        {
            "metodo": e.metodo,
            "caminho": e.caminho,
            "descricao": e.descricao,
            "requer_autenticacao": e.requer_autenticacao,
            "categoria_permissao": e.categoria_permissao,
        }
        for e in ENDPOINTS
    ]
