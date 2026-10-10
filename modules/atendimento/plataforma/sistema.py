"""Área do RMD Desenvolvedor — funcionamento da plataforma, SEM acesso aos dados das igrejas.

- Painel: versão, tempo no ar, tamanho do banco, último backup, erros recentes.
- Erros: o servidor registra cada falha (rota, tipo e hora) — sem guardar o conteúdo enviado pelas pessoas.
- Por igreja (Sede): liberar/bloquear o acesso, plano e quais funções ficam ligadas.
- Cria a conta da Administração da Sede (senha inicial 1234, troca obrigatória).
Só números agregados (quantos usuários, quantas igrejas) — nunca nomes, conversas, visitantes ou orações.
"""
from __future__ import annotations

import os
import time

from . import seguranca
from .db import agora
from .nucleo import Ator, ErroNegocio, NaoEncontrado, novo_id

INICIO = time.time()

# Funções que o RMD Desenvolvedor pode ligar/desligar por igreja (recurso da tabela de permissões → nome na tela).
RECURSOS_LIGAVEIS = (
    ("conversas", "Atendimento (chat)"),
    ("visitantes", "Visitantes & Consolidação"),
    ("oracoes", "Pedidos de oração"),
    ("organizacao", "Organização (setores, campos e igrejas)"),
    ("agenda", "Agenda"),
    ("orcamentos", "Solicitações"),
    ("servicos", "Tipos de solicitação / serviços"),
    ("valores", "Valores em dinheiro (preços, totais e descontos)"),
    ("alertas", "Alertas"),
    ("fluxos", "Fluxos (robô de atendimento)"),
    ("whatsapp", "WhatsApp"),
    ("api", "API & Webhooks"),
    ("relatorios", "Relatórios"),
)
CHAVES_RECURSOS = tuple(r for r, _ in RECURSOS_LIGAVEIS)


def desligados_por_padrao() -> set[str]:
    """Funções que começam DESLIGADAS até o RMD Desenvolvedor ligar. Na igreja não há valores em dinheiro."""
    return {"valores"} if os.getenv("RMD_EDICAO", "").strip().lower() == "church" else set()


def _limpar_mensagem(texto: str) -> str:
    """Guarda só o começo da mensagem técnica do erro, sem quebras de linha."""
    return " ".join(str(texto or "").split())[:240]


class SistemaMixin:
    # ================================================================ RECURSOS POR IGREJA
    def recursos_desligados(self, empresa_id: str | None) -> set[str]:
        if not empresa_id:
            return set()
        try:
            linhas = self.banco.todos("SELECT recurso, ligado FROM empresa_recursos WHERE empresa_id=?", (empresa_id,))
        except Exception:  # noqa: BLE001 - banco antigo sem a tabela ainda
            return desligados_por_padrao()
        escolhidos = {l["recurso"]: l["ligado"] for l in linhas}
        return ({r for r, ligado in escolhidos.items() if not ligado}
                | {r for r in desligados_por_padrao() if r not in escolhidos})

    def salvar_recursos(self, ator: Ator, empresa_id: str, ligados: dict) -> dict:
        ator.exigir("empresas", "editar")
        self.obter_empresa(empresa_id)
        for recurso in CHAVES_RECURSOS:
            if recurso not in ligados:
                continue
            ligado = 1 if ligados[recurso] in (True, 1, "1", "true", "on") else 0
            self.banco.executar(
                """INSERT INTO empresa_recursos(empresa_id, recurso, ligado, atualizado_em) VALUES (?,?,?,?)
                   ON CONFLICT(empresa_id, recurso) DO UPDATE SET ligado=excluded.ligado, atualizado_em=excluded.atualizado_em""",
                (empresa_id, recurso, ligado, agora()))
        self.auditar(ator, "sistema.recursos", empresa_id, {"desligados": sorted(self.recursos_desligados(empresa_id))})
        return {"desligados": sorted(self.recursos_desligados(empresa_id))}

    # ================================================================ ERROS
    def registrar_erro(self, rota: str, metodo: str, erro: BaseException, empresa_id: str | None = None) -> None:
        try:
            self.banco.executar(
                "INSERT INTO erros_sistema(id, quando, rota, metodo, tipo, mensagem, empresa_id) VALUES (?,?,?,?,?,?,?)",
                (novo_id(), agora(), (rota or "")[:120], (metodo or "")[:10], type(erro).__name__[:80], _limpar_mensagem(erro), empresa_id))
            self.banco.executar("DELETE FROM erros_sistema WHERE id NOT IN (SELECT id FROM erros_sistema ORDER BY quando DESC LIMIT 500)")
        except Exception:  # noqa: BLE001 - registrar erro nunca pode derrubar o servidor
            pass

    def marcar_erros_vistos(self, ator: Ator) -> dict:
        ator.exigir("empresas", "ver")
        self.banco.executar("UPDATE erros_sistema SET visto=1 WHERE visto=0")
        return {"ok": True}

    # ================================================================ PAINEL DO RMD DESENVOLVEDOR
    def painel_sistema(self, ator: Ator) -> dict:
        ator.exigir("empresas", "ver")
        b = self.banco
        tamanho = 0
        try:
            caminho = b.caminho
            tamanho = sum(p.stat().st_size for p in caminho.parent.glob(caminho.name + "*") if p.is_file())
        except Exception:  # noqa: BLE001
            pass
        igrejas = []
        for e in b.todos("""SELECT e.id, e.nome, e.slug, e.ativa, e.plano, e.demonstracao, e.criada_em,
                                   (SELECT COUNT(*) FROM usuarios u WHERE u.empresa_id=e.id AND u.ativo=1 AND u.perfil<>'cliente') AS usuarios,
                                   (SELECT MAX(u.ultimo_acesso) FROM usuarios u WHERE u.empresa_id=e.id) AS ultimo_uso,
                                   (SELECT COUNT(*) FROM usuarios u WHERE u.empresa_id=e.id AND u.perfil='admin' AND u.ativo=1) AS admins,
                                   (SELECT MAX(criado_em) FROM backups k WHERE k.empresa_id=e.id) AS ultimo_backup,
                                   (SELECT COUNT(*) FROM erros_sistema x WHERE x.empresa_id=e.id AND x.visto=0) AS erros
                            FROM empresas e ORDER BY e.demonstracao, e.nome"""):
            desligados = self.recursos_desligados(e["id"])
            igrejas.append({**e, "ativa": bool(e["ativa"]), "demonstracao": bool(e["demonstracao"]),
                            "recursos": [{"recurso": r, "nome": n, "ligado": r not in desligados} for r, n in RECURSOS_LIGAVEIS]})
        erros = b.todos("SELECT x.*, e.nome AS igreja FROM erros_sistema x LEFT JOIN empresas e ON e.id=x.empresa_id ORDER BY x.quando DESC LIMIT 50")
        return {
            "versao": getattr(self, "VERSAO", None),
            "no_ar_desde": int(INICIO), "no_ar_segundos": int(time.time() - INICIO),
            "banco_bytes": tamanho,
            "erros_nao_vistos": (b.um("SELECT COUNT(*) AS n FROM erros_sistema WHERE visto=0") or {}).get("n", 0),
            "erros": erros, "igrejas": igrejas,
        }

    def criar_admin_da_sede(self, ator: Ator, empresa_id: str, nome: str, email: str) -> dict:
        """Cria a conta da Administração da Sede. Senha inicial padrão (1234) com troca obrigatória — nunca é mostrada."""
        ator.exigir("empresas", "editar")
        self.obter_empresa(empresa_id)
        if not (email or "").strip():
            raise ErroNegocio("Informe o e-mail da Administração da Sede.")
        if ator.perfil == "owner" and self.banco.um(
                "SELECT 1 AS x FROM usuarios WHERE empresa_id=? AND perfil='admin' AND ativo=1 LIMIT 1", (empresa_id,)):
            # Proteção de dados: o RMD Desenvolvedor só abre a PRIMEIRA conta da Sede. Depois disso, novas contas
            # são criadas pela própria Administração da Sede (senão ele poderia criar uma conta e entrar nos dados).
            raise ErroNegocio("Esta Sede já tem Administração. Novas contas são criadas pela própria Administração da Sede.")
        usuario, _temporaria = self.criar_usuario(None, nome or "Administração da Sede", email, "admin", empresa_id=empresa_id)
        salt = seguranca.gerar_salt()
        self.banco.executar("UPDATE usuarios SET senha_hash=?, senha_salt=?, trocar_senha=1 WHERE id=?",
                            (seguranca.hash_senha("1234", salt), salt, usuario["id"]))
        self.auditar(ator, "usuario.criar", usuario["id"], {"perfil": "admin"}, empresa_id=empresa_id)
        return {"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"]}

    def obter_empresa_ou_erro(self, empresa_id: str) -> dict:
        empresa = self.banco.um("SELECT * FROM empresas WHERE id=?", (empresa_id,))
        if not empresa:
            raise NaoEncontrado("Igreja não encontrada.")
        return empresa
