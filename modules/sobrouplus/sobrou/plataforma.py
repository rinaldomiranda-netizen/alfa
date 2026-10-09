"""Plataforma Sobrou+ — junta todas as partes (mesmo desenho de mixins do RMD Atendimento).

A rotina automática (a cada 30 s no servidor) cuida do que depende do relógio:
reservas vencidas, fim da venda das ofertas, preço automático, pedidos não retirados, Dispatch.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contas import ContasMixin
from .testes import TestesMixin
from .db import Banco, pasta_dados
from . import rede as _rede
from .financeiro import FinanceiroDetalhadoMixin, FinanceiroMixin
from .acesso import AcessoMixin
from .extras import ExtrasMixin
from .integracoes import IntegracoesMixin
from .mapas import MapasMixin
from .logistica import LogisticaMixin
from .nucleo import SISTEMA, iso, ler_data, ErroNegocio, SemPermissao
from .ofertas import OfertasMixin
from .pedidos import PedidosMixin

VERSAO = "0.3.0"


class Plataforma(ContasMixin, OfertasMixin, PedidosMixin, LogisticaMixin, FinanceiroMixin, IntegracoesMixin, MapasMixin, ExtrasMixin, AcessoMixin, FinanceiroDetalhadoMixin,
                 TestesMixin):
    VERSAO = VERSAO

    def __init__(self, pasta: Path | str | None = None, relogio=None):
        self.pasta = Path(pasta) if pasta else pasta_dados()
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.banco = Banco(self.pasta / "sobrou.db")
        self.pasta_fotos = self.pasta / "fotos"
        self.pasta_fotos.mkdir(exist_ok=True)
        self._relogio = relogio  # nos testes: função que devolve o "agora"
        self.rede = _rede.chamar  # nos testes: troca por uma função falsa (nenhuma chamada externa)

    def agora_dt(self) -> datetime:
        return self._relogio() if self._relogio else datetime.now(timezone.utc)

    def agora(self) -> str:
        return iso(self.agora_dt())

    # ================================================================ ROTINA
    def rotina(self) -> dict:
        r = {"reservas_vencidas": 0, "ofertas_encerradas": 0, "precos": 0, "nao_retirados": 0, "concluidos": 0, "despachados": 0}
        agora = self.agora()
        # 1. reserva vencida sem pagamento → expirado, estoque volta
        for p in self.banco.todos("SELECT * FROM pedidos WHERE status='aguardando_pagamento' AND reserva_expira_em<=?", (agora,)):
            with self.banco.transacao() as c:
                atual = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (p["id"],))
                if atual["status"] != "aguardando_pagamento":
                    continue
                self._devolver_estoque(c, atual, SISTEMA, "liberacao")
                self._mudar(c, atual, "expirado", None, "tempo de pagamento esgotado — reserva liberada")
            r["reservas_vencidas"] += 1
        # 2. fim da venda → oferta encerrada, sobra vira 'expirado' (pode ir para doação)
        for o in self.banco.todos("SELECT * FROM ofertas WHERE status IN ('ativa','esgotada','pausada') AND fim<=?", (agora,)):
            with self.banco.transacao() as c:
                self._encerrar_oferta(c, o, None, "fim do horário de venda")
            self.auditar(None, "oferta.encerrar_auto", o["id"], empresa_id=o["empresa_id"])
            r["ofertas_encerradas"] += 1
        # 3. preço automático (só ofertas com regra configurada pelo parceiro)
        for o in self.banco.todos("SELECT id, preco_centavos FROM ofertas WHERE status='ativa' AND regra_preco<>'fixo'"):
            novo = self.aplicar_preco(o["id"])
            if novo is not None and novo != o["preco_centavos"]:
                r["precos"] += 1
        # 4. janela de retirada acabou (+ tolerância) → não retirado
        tol = self.config_plataforma()["tolerancia_retirada_min"]
        limite = iso(self.agora_dt() - timedelta(minutes=tol))
        for p in self.banco.todos("SELECT * FROM pedidos WHERE status='aguardando_retirada' AND janela_fim IS NOT NULL AND janela_fim<=?", (limite,)):
            with self.banco.transacao() as c:
                self._mudar(c, p, "nao_retirado", None, f"janela de retirada encerrada (+{tol} min de tolerância)")
                self.avisar(f"Pedido #{p['numero']} não foi retirado. Você pode destiná-lo para doação.", empresa_id=p["empresa_id"], conn=c)
            r["nao_retirados"] += 1
        # 5. entregue há mais de 12 h sem o cliente confirmar → concluído
        limite = iso(self.agora_dt() - timedelta(hours=12))
        for p in self.banco.todos("SELECT * FROM pedidos WHERE status='entregue' AND atualizado_em<=?", (limite,)):
            with self.banco.transacao() as c:
                self._mudar(c, p, "concluido", None, "concluído automaticamente 12 h após a entrega")
            r["concluidos"] += 1
        # 6. Dispatch
        r["despachados"] = self.despachar()
        # Retenção definida para eventos analíticos: 90 dias.
        r["eventos_expirados"] = self.banco.executar("DELETE FROM eventos_uso WHERE criado_em < ?", (iso(self.agora_dt() - timedelta(days=90)),))
        # Sessões expiradas não precisam permanecer no banco.
        r["sessoes_expiradas"] = self.banco.executar("DELETE FROM sessoes WHERE expira_em <= ?", (agora,))
        # 7. WhatsApp (só se ativado em Integrações)
        r["whatsapp"] = self.enviar_fila_whatsapp()
        # 8. aviso no celular (push), mensalidades do mês e backup diário
        r["push"] = self.enviar_fila_push()
        r["faturas"] = self.gerar_faturas()
        r["backup"] = self.backup_se_preciso()
        return r

    # ================================================================ ANALÍTICA DE USO (somente plataforma)
    def registrar_evento_uso(self, dados: dict) -> dict:
        """Registra eventos mínimos pseudônimos, sem IP, nome, e-mail ou conteúdo livre."""
        visitante = str(dados.get("visitante") or "")
        tipo = str(dados.get("tipo") or "")
        if len(visitante) < 16 or len(visitante) > 80 or not all(c.isalnum() or c in "-_" for c in visitante):
            raise ErroNegocio("Identificador de sessão inválido.")
        if tipo not in ("visita", "loja", "oferta", "checkout", "pedido"):
            raise ErroNegocio("Tipo de evento inválido.")
        empresa_id = str(dados.get("empresa_id") or "")[:80] or None
        oferta_id = str(dados.get("oferta_id") or "")[:80] or None
        if oferta_id:
            oferta = self.banco.um("SELECT empresa_id FROM ofertas WHERE id=?", (oferta_id,))
            if not oferta:
                return {"ok": True}
            empresa_id = oferta["empresa_id"]
        if empresa_id and not self.banco.um("SELECT id FROM empresas WHERE id=?", (empresa_id,)):
            empresa_id = None
        eid = str(dados.get("evento_id") or novo_id())[:80]
        self.banco.executar("INSERT OR IGNORE INTO eventos_uso(id, visitante, tipo, empresa_id, oferta_id, criado_em) VALUES (?,?,?,?,?,?)",
                            (eid, visitante, tipo, empresa_id, oferta_id, self.agora()))
        return {"ok": True}

    def relatorio_marketing(self, ator: Ator, empresa_id: str | None = None, dias: int = 30) -> dict:
        if not ator.plataforma:
            raise SemPermissao("A análise de marketing é restrita à equipe Sobrou+.")
        ator.exigir("sistema", "ver")
        dias = max(1, min(int(dias or 30), 90))
        desde = iso(self.agora_dt() - timedelta(days=dias))
        cond, args = (" AND ev.empresa_id=?", (empresa_id,)) if empresa_id else ("", ())
        eventos = self.banco.todos(f"""SELECT ev.tipo, ev.empresa_id, COALESCE(emp.nome,'—') AS empresa,
              COUNT(*) AS eventos, COUNT(DISTINCT ev.visitante) AS visitantes
              FROM eventos_uso ev LEFT JOIN empresas emp ON emp.id=ev.empresa_id
              WHERE ev.criado_em>=?{cond} GROUP BY ev.tipo, ev.empresa_id ORDER BY visitantes DESC""", (desde, *args))
        por_empresa = self.banco.todos(f"""SELECT ev.empresa_id, COALESCE(emp.nome,'—') AS empresa,
              COUNT(DISTINCT CASE WHEN ev.tipo IN ('visita','loja','oferta') THEN ev.visitante END) AS visitas,
              COUNT(DISTINCT CASE WHEN ev.tipo='oferta' THEN ev.visitante END) AS interesse,
              COUNT(DISTINCT CASE WHEN ev.tipo='checkout' THEN ev.visitante END) AS checkouts,
              COUNT(DISTINCT CASE WHEN ev.tipo='pedido' THEN ev.visitante END) AS compradores,
              SUM(CASE WHEN ev.tipo='pedido' THEN 1 ELSE 0 END) AS pedidos
              FROM eventos_uso ev LEFT JOIN empresas emp ON emp.id=ev.empresa_id
              WHERE ev.criado_em>=? AND ev.empresa_id IS NOT NULL{cond} GROUP BY ev.empresa_id ORDER BY pedidos DESC, visitas DESC""", (desde, *args))
        serie = self.banco.todos(f"""SELECT substr(criado_em,1,10) AS dia,
              COUNT(DISTINCT visitante) AS visitantes,
              SUM(CASE WHEN tipo='oferta' THEN 1 ELSE 0 END) AS ofertas_abertas,
              SUM(CASE WHEN tipo='checkout' THEN 1 ELSE 0 END) AS checkouts,
              SUM(CASE WHEN tipo='pedido' THEN 1 ELSE 0 END) AS pedidos
              FROM eventos_uso WHERE criado_em>=?{(' AND empresa_id=?' if empresa_id else '')}
              GROUP BY substr(criado_em,1,10) ORDER BY dia""", (desde, *args))
        for x in por_empresa:
            v = x["visitas"] or 0
            x["conversao_pct"] = round(100 * (x["compradores"] or 0) / v, 1) if v else None
            x["desistencia_checkout"] = max(0, (x["checkouts"] or 0) - (x["compradores"] or 0))
        acessos_web = self.banco.um("SELECT COUNT(DISTINCT visitante) AS n FROM eventos_uso WHERE tipo='visita' AND criado_em>=?", (desde,))["n"]
        visitas = sum(x["visitas"] or 0 for x in por_empresa)
        pedidos = sum(x["pedidos"] or 0 for x in por_empresa)
        conversao = round(100 * pedidos / visitas, 1) if visitas else None
        sugestoes = ["Ainda há poucos dados reais para sugerir melhorias."] if visitas < 20 else []
        if visitas >= 20 and conversao is not None and conversao < 3:
            sugestoes.append("Muitas visitas e poucas compras: revise preço, disponibilidade, taxa de entrega e clareza do checkout.")
        if any((x["desistencia_checkout"] or 0) >= 5 for x in por_empresa):
            sugestoes.append("Há checkouts iniciados sem pedido registrado. Revise os erros de endereço, estoque e pagamento.")
        if visitas >= 20 and any((x["visitas"] or 0) >= 10 and not x["pedidos"] for x in por_empresa):
            sugestoes.append("Há empresas com tráfego e nenhuma venda no período; ofereça apoio para revisar ofertas e horários.")
        return {"dias": dias, "desde": desde, "acessos_web": acessos_web, "visitas": visitas, "pedidos": pedidos,
                "conversao_pct": conversao, "eventos": eventos, "por_empresa": por_empresa,
                "serie": serie, "sugestoes": sugestoes,
                "nota": "Dados de navegação pseudônimos e agregados; eventos sem visita não identificam cliente."}

    # ================================================================ FAVORITOS (cliente)
    def alternar_favorito(self, ator, empresa_id: str) -> dict:
        if ator.papel != "cliente":
            from .nucleo import SemPermissao
            raise SemPermissao("Só clientes têm favoritos.")
        if self.banco.um("SELECT 1 AS x FROM favoritos WHERE cliente_id=? AND empresa_id=?", (ator.usuario_id, empresa_id)):
            self.banco.executar("DELETE FROM favoritos WHERE cliente_id=? AND empresa_id=?", (ator.usuario_id, empresa_id))
            return {"favorito": False}
        if not self.banco.um("SELECT id FROM empresas WHERE id=? AND aprovada=1", (empresa_id,)):
            from .nucleo import NaoEncontrado
            raise NaoEncontrado("Loja não encontrada.")
        self.banco.executar("INSERT INTO favoritos(cliente_id, empresa_id, criado_em) VALUES (?,?,?)", (ator.usuario_id, empresa_id, self.agora()))
        return {"favorito": True}

    def listar_favoritos(self, ator) -> list[str]:
        return [r["empresa_id"] for r in self.banco.todos("SELECT empresa_id FROM favoritos WHERE cliente_id=?", (ator.usuario_id,))]

    # ================================================================ ERROS (área do sistema)
    def registrar_erro(self, rota: str, metodo: str, erro: BaseException) -> None:
        from .nucleo import novo_id
        try:
            self.banco.executar("INSERT INTO erros_sistema(id, quando, rota, metodo, tipo, mensagem) VALUES (?,?,?,?,?,?)",
                                (novo_id(), self.agora(), (rota or "")[:120], metodo, type(erro).__name__, " ".join(str(erro).split())[:240]))
        except Exception:  # noqa: BLE001
            pass

    def painel_seguranca(self, ator) -> dict:
        """Painel de segurança operacional. Exclusivo do proprietário RMD."""
        if ator.usuario_id != self.id_dono():
            raise SemPermissao("O painel de segurança é exclusivo do proprietário RMD.")
        b = self.banco
        agora = self.agora()
        sessoes = b.todos("""SELECT s.usuario_id, u.nome AS usuario, u.email, u.papel, u.empresa_id,
                                    s.criada_em, s.expira_em, s.ip
                             FROM sessoes s JOIN usuarios u ON u.id=s.usuario_id
                             WHERE s.expira_em>? ORDER BY s.criada_em DESC LIMIT 200""", (agora,))
        falhas = b.todos("""SELECT id, nome, email, papel, empresa_id, tentativas_falhas, bloqueado_ate
                            FROM usuarios WHERE tentativas_falhas>0 OR bloqueado_ate IS NOT NULL
                            ORDER BY tentativas_falhas DESC, bloqueado_ate DESC LIMIT 100""")
        auditoria = b.todos("""SELECT a.quando, a.usuario_id, u.nome AS usuario, u.email, u.papel,
                                      a.empresa_id, a.acao, a.alvo, a.detalhe, a.ip
                               FROM auditoria a LEFT JOIN usuarios u ON u.id=a.usuario_id
                               WHERE a.acao LIKE 'seguranca.%'
                                  OR a.acao LIKE 'usuario.%'
                                  OR a.acao LIKE 'lgpd.%'
                                  OR a.acao LIKE 'backup.%'
                               ORDER BY a.quando DESC LIMIT 200""")
        backup = b.um("SELECT valor FROM config WHERE chave='ultimo_backup'")
        return {
            "somente_rmd": True,
            "proprietario_id": self.id_dono(),
            "sessoes_ativas": sessoes,
            "total_sessoes_ativas": len(sessoes),
            "contas_com_falhas": falhas,
            "eventos_seguranca": auditoria,
            "ultimo_backup": backup["valor"] if backup else None,
            "backup_ok": bool(backup and (self.agora_dt() - ler_data(backup["valor"])) < timedelta(hours=24)),
            "protecao": {
                "sessao_horas": 8,
                "csrf_json": True,
                "isolamento_empresas": True,
                "auditoria": True,
                "limpeza_sessoes_expiradas": True,
                "rate_limit_login": True,
                "upload_imagens_validado": True,
                "lgpd": True,
                "backup_automatico": True,
                "totp": "adiado_pelo_projeto",
                "financeiro_producao": "adiado_pelo_projeto"
            }
        }

    def painel_sistema(self, ator) -> dict:
        ator.exigir("sistema", "ver")
        b = self.banco
        cont = lambda sql: b.um(sql)["n"]  # noqa: E731
        return {"versao": VERSAO, "erros": b.todos("SELECT * FROM erros_sistema ORDER BY quando DESC LIMIT 50"),
                "empresas": cont("SELECT COUNT(*) AS n FROM empresas"), "aguardando_aprovacao": cont("SELECT COUNT(*) AS n FROM empresas WHERE aprovada=0"),
                "clientes": cont("SELECT COUNT(*) AS n FROM usuarios WHERE papel='cliente'"),
                "entregadores_online": cont("SELECT COUNT(*) AS n FROM entregadores WHERE online=1"),
                "instituicoes_pendentes": cont("SELECT COUNT(*) AS n FROM instituicoes WHERE autorizada=0"),
                "integracoes": self._estado_integracoes(),
                "mensagens": self.resumo_mensagens(ator)["contagem"]}

    def _estado_integracoes(self) -> list[dict]:
        mp, wa, mapa = self._mp(), self._wa(), self._cfg_mapas()
        teste_mp = bool(mp and mp["access_token"].startswith("TEST-"))
        return [
            {"nome": "Pagamento Pix e cartão (Mercado Pago)",
             "estado": ("IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL" if mp else "PRONTO PARA ATIVAR"),
             "detalhe": ("Ligado com credencial de TESTE do Mercado Pago" if teste_mp else "Ligado em PRODUÇÃO") if mp else
                        "Falta: conta Mercado Pago → Credenciais → Access Token (e a chave secreta do webhook). Colocar em Integrações."},
            {"nome": "WhatsApp (API oficial da Meta)", "estado": "IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL" if wa else "PRONTO PARA ATIVAR",
             "detalhe": "Ligado: avisos de pedido vão para o celular cadastrado do cliente" if wa else
                        "Falta: conta Meta WhatsApp Business → token permanente + Phone Number ID (+ modelo de mensagem aprovado). Colocar em Integrações."},
            {"nome": "Mapa, rotas pelas ruas e busca de endereço (OpenStreetMap)",
             "estado": "IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL" if mapa["ligado"] else "DESLIGADO",
             "detalhe": f"Rotas: {mapa['rotas_url']} · Endereços: {mapa['enderecos_url']}. Sem resposta do serviço → estimativa marcada na tela."},
            {"nome": "GPS do entregador e do cliente", "estado": "IMPLEMENTADO MAS NÃO VALIDADO EM AMBIENTE REAL",
             "detalhe": "GPS do celular pelo navegador; funciona no endereço com HTTPS (versão na internet)"},
            {"nome": "Avisos dentro do sistema", "estado": "IMPLEMENTADO E VALIDADO", "detalhe": "sino no painel e no app"},
        ]
