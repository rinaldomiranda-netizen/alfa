"""Empresa de demonstração usada pelo Laboratório de Módulos do ALFA.

Tudo aqui fica numa empresa marcada como DEMONSTRAÇÃO (aparece na tela
com essa etiqueta). As empresas reais começam vazias — nada daqui é
misturado com dados de clientes.
"""
from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timedelta, timezone

SLUG_DEMO = "demonstracao"
EMAIL_OWNER = "owner@alfa.local"
EMAILS_DEMO = {
    "admin": "admin@demonstracao.local",
    "supervisor": "supervisor@demonstracao.local",
    "atendente": "atendente@demonstracao.local",
    "cliente": "cliente@demonstracao.local",
}


def _senha_aleatoria() -> str:
    return "Demo" + secrets.token_urlsafe(12) + "9"


def garantir_owner(plataforma, nome: str = "ALFA Owner") -> dict:
    if os.getenv("RMD_EDICAO") == "church":
        nome = "RMD Desenvolvedor"  # na igreja, o dono do sistema aparece como RMD Desenvolvedor
    usuario = plataforma.banco.um("SELECT * FROM usuarios WHERE email=?", (EMAIL_OWNER,))
    if usuario:
        if os.getenv("RMD_EDICAO") == "church" and usuario["nome"] != nome:
            plataforma.banco.executar("UPDATE usuarios SET nome=? WHERE id=?", (nome, usuario["id"]))
            usuario = plataforma.banco.um("SELECT * FROM usuarios WHERE id=?", (usuario["id"],))
        return usuario
    plataforma.criar_usuario(None, nome, EMAIL_OWNER, "owner", senha=_senha_aleatoria())
    return plataforma.banco.um("SELECT * FROM usuarios WHERE email=?", (EMAIL_OWNER,))


def garantir_demonstracao(plataforma) -> dict:
    """Cria (uma única vez) a empresa de demonstração. Devolve
    {"empresa_id", "usuarios": {perfil: usuario_id}}."""
    owner = garantir_owner(plataforma)
    empresa = plataforma.empresa_por_slug(SLUG_DEMO)
    if not empresa:
        empresa = plataforma.criar_empresa("RMD Atendimento Demo", plano="business", demonstracao=True, slug=SLUG_DEMO)
        _povoar(plataforma, empresa["id"])
        if os.getenv("RMD_EDICAO", "").strip().lower() == "church":
            from .igreja import povoar_demo_igreja
            povoar_demo_igreja(plataforma, empresa["id"])
    usuarios = {"owner": owner["id"]}
    for perfil, email in EMAILS_DEMO.items():
        linha = plataforma.banco.um("SELECT id FROM usuarios WHERE email=?", (email,))
        if linha:
            usuarios[perfil] = linha["id"]
    return {"empresa_id": empresa["id"], "usuarios": usuarios}


def _povoar(p, empresa_id: str) -> None:
    from .nucleo import Ator

    sistema = Ator("sistema", "Sistema", "", "admin", empresa_id)
    b = p.banco
    geral = b.um("SELECT id FROM filas WHERE empresa_id=?", (empresa_id,))
    b.executar("UPDATE filas SET nome='Comercial', sla_minutos=10 WHERE id=?", (geral["id"],))
    comercial = geral["id"]
    suporte = p.salvar_fila(sistema, {"nome": "Suporte", "sla_minutos": 15})["id"]
    financeiro = p.salvar_fila(sistema, {"nome": "Financeiro", "sla_minutos": 20})["id"]

    maria = p._criar_contato(empresa_id, {"nome": "Maria Santos", "telefone": "79999991111", "email": "maria@exemplo.com", "tags": ["VIP", "orçamento"]})
    jose = p._criar_contato(empresa_id, {"nome": "José Almeida", "telefone": "79988882222", "tags": ["suporte"]})
    ana = p._criar_contato(empresa_id, {"nome": "Ana Paula", "telefone": "79977773333", "tags": ["novo"]})
    pedro = p._criar_contato(empresa_id, {"nome": "Pedro Lima", "telefone": "79966664444", "tags": ["financeiro"]})

    senha = _senha_aleatoria
    p.criar_usuario(None, "Rinaldo (Admin demo)", EMAILS_DEMO["admin"], "admin", senha(), comercial, empresa_id=empresa_id)
    p.criar_usuario(None, "João Wesley", EMAILS_DEMO["supervisor"], "supervisor", senha(), comercial, empresa_id=empresa_id)
    p.criar_usuario(None, "Carla Souza", EMAILS_DEMO["atendente"], "atendente", senha(), comercial, empresa_id=empresa_id)
    p.criar_usuario(None, "Maria Santos (cliente)", EMAILS_DEMO["cliente"], "cliente", senha(), contato_id=maria["id"], empresa_id=empresa_id)
    carla = b.um("SELECT id FROM usuarios WHERE email=?", (EMAILS_DEMO["atendente"],))["id"]
    joao = b.um("SELECT id FROM usuarios WHERE email=?", (EMAILS_DEMO["supervisor"],))["id"]
    b.executar("UPDATE usuarios SET presenca='online' WHERE id IN (?,?)", (carla, joao))

    visita = p.salvar_servico(sistema, {"nome": "Visita técnica", "categoria": "Comercial", "preco": "180,00", "sla_horas": 24})
    p.salvar_servico(sistema, {"nome": "Manutenção", "categoria": "Suporte", "preco": "350,00", "sla_horas": 8})
    consultoria = p.salvar_servico(sistema, {"nome": "Consultoria", "categoria": "Especial", "preco": "450,00", "sla_horas": 48})

    p.salvar_fluxo(sistema, {
        "nome": "Boas-vindas", "gatilho_tipo": "sempre",
        "etapas": [
            {"tipo": "mensagem", "texto": "Olá, {{nome}}! Bem-vindo à {{empresa}}."},
            {"tipo": "pergunta", "texto": "Como podemos ajudar?", "variavel": "assunto", "opcoes": ["Orçamento", "Suporte", "Financeiro"]},
            {"tipo": "condicao", "variavel": "assunto", "operador": "igual", "valor": "Orçamento", "ir_para": 5, "senao_ir_para": 7},
            {"tipo": "encerrar", "texto": ""},
            {"tipo": "tag", "tag": "orçamento"},
            {"tipo": "handoff", "fila": comercial, "texto": "Certo! Um consultor do Comercial vai te atender."},
            {"tipo": "condicao", "variavel": "assunto", "operador": "igual", "valor": "Suporte", "ir_para": 8, "senao_ir_para": 9},
            {"tipo": "handoff", "fila": suporte, "texto": "Vou te passar para o Suporte."},
            {"tipo": "handoff", "fila": financeiro, "texto": "Vou te passar para o Financeiro."},
        ],
    })
    fluxo = b.um("SELECT id FROM fluxos WHERE empresa_id=?", (empresa_id,))
    p.simular_fluxo(sistema, fluxo["id"], None, ["Orçamento"])
    p.publicar_fluxo(sistema, fluxo["id"])

    agora_dt = datetime.now(timezone.utc)
    # Conversas de exemplo (sem mandar nada para fora: canal "web").
    for contato, texto, fila, responsavel, status in (
        (maria, "Bom dia! Preciso de um orçamento para o serviço.", comercial, carla, "em_atendimento"),
        (jose, "Pode verificar meu pedido?", suporte, None, "aguardando"),
        (ana, "Olá, gostaria de saber os preços.", comercial, None, "aguardando"),
        (pedro, "Recebi a nota fiscal, obrigado.", financeiro, joao, "resolvido"),
    ):
        conversa = p._nova_conversa(empresa_id, contato["id"], "web", fila_id=fila)
        p._gravar_mensagem(conversa, "entrada", "contato", texto, autor_id=contato["id"])
        campos = {"status": status, "responsavel": responsavel}
        if responsavel:
            p._gravar_mensagem(conversa, "saida", "usuario", "Olá! Já estou vendo isso para você.", autor_id=responsavel)
            b.executar("UPDATE conversas SET primeira_resposta_em=? WHERE id=?", (agora_dt.isoformat(timespec="seconds"), conversa["id"]))
        b.executar(
            "UPDATE conversas SET status=:status, responsavel_id=:responsavel, resolvida_em=CASE WHEN :status='resolvido' THEN :agora END, "
            "avaliacao=CASE WHEN :status='resolvido' THEN 5 END WHERE id=:id",
            {**campos, "agora": agora_dt.isoformat(timespec="seconds"), "id": conversa["id"]},
        )

    atendente = p._ator(b.um("SELECT * FROM usuarios WHERE id=?", (carla,)), empresa_id)
    orc = p.salvar_orcamento(atendente, {
        "contato_id": maria["id"], "descricao": "Visita técnica e execução do serviço solicitado.",
        "validade": (date.today() + timedelta(days=5)).isoformat(),
        "itens": [{"servico_id": visita["id"], "quantidade": 1}, {"descricao": "Execução do serviço", "quantidade": 1, "valor_unit": "600,00"}],
    })
    p._aplicar_status_orcamento(orc, "enviado")
    p.salvar_orcamento(atendente, {"contato_id": ana["id"], "itens": [{"servico_id": consultoria["id"], "quantidade": 1}]})

    amanha = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0).astimezone(timezone.utc)
    p.salvar_agendamento(atendente, {"titulo": "Visita técnica", "inicio": amanha.isoformat(), "duracao_minutos": 60,
                                    "contato_id": maria["id"], "fila_id": comercial, "responsavel_id": carla, "status": "confirmado"})
