"""Plataforma Sobrou+ — junta todas as partes (mesmo desenho de mixins do RMD Atendimento).

A rotina automática (a cada 30 s no servidor) cuida do que depende do relógio:
reservas vencidas, fim da venda das ofertas, preço automático, pedidos não retirados, Dispatch.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contas import ContasMixin
from .db import Banco, pasta_dados
from . import rede as _rede
from .financeiro import FinanceiroDetalhadoMixin, FinanceiroMixin
from .acesso import AcessoMixin
from .extras import ExtrasMixin
from .integracoes import IntegracoesMixin
from .mapas import MapasMixin
from .logistica import LogisticaMixin
from .nucleo import SISTEMA, iso
from .ofertas import OfertasMixin
from .pedidos import PedidosMixin

VERSAO = "0.3.0"


class Plataforma(ContasMixin, OfertasMixin, PedidosMixin, LogisticaMixin, FinanceiroMixin, IntegracoesMixin, MapasMixin, ExtrasMixin, AcessoMixin, FinanceiroDetalhadoMixin):
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
        # 7. WhatsApp (só se ativado em Integrações)
        r["whatsapp"] = self.enviar_fila_whatsapp()
        # 8. aviso no celular (push), mensalidades do mês e backup diário
        r["push"] = self.enviar_fila_push()
        r["faturas"] = self.gerar_faturas()
        r["backup"] = self.backup_se_preciso()
        return r

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
