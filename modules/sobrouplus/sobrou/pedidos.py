"""Checkout, pagamento (modo teste), pedidos com 18 estados e histórico, retirada com PIN/QR, cancelamento."""
from __future__ import annotations

import secrets
from datetime import timedelta

from .nucleo import (Ator, ErroNegocio, NaoEncontrado, SemPermissao, distancia_km, inteiro, iso, novo_id, real, texto)
from . import seguranca
from .ofertas import disponivel

ESTADOS = {
    "criado": "Criado", "aguardando_pagamento": "Aguardando pagamento", "pago": "Pago",
    "recebido": "Recebido pela empresa", "preparando": "Preparando", "pronto": "Pronto",
    "aguardando_retirada": "Aguardando retirada", "aguardando_entregador": "Aguardando entregador",
    "entregador_designado": "Entregador designado", "em_coleta": "Em coleta", "em_rota": "Em rota",
    "entregue": "Entregue", "retirado": "Retirado", "concluido": "Concluído", "cancelado": "Cancelado",
    "nao_retirado": "Não retirado", "expirado": "Expirado", "destinado": "Destinado (doação)",
}
TRANSICOES = {
    "criado": {"aguardando_pagamento", "cancelado"},
    "aguardando_pagamento": {"pago", "cancelado", "expirado"},
    "pago": {"recebido", "cancelado"},
    "recebido": {"preparando", "cancelado"},
    "preparando": {"pronto", "cancelado"},
    "pronto": {"aguardando_retirada", "aguardando_entregador"},
    "aguardando_retirada": {"retirado", "nao_retirado", "cancelado"},
    "aguardando_entregador": {"entregador_designado", "cancelado"},
    "entregador_designado": {"em_coleta", "aguardando_entregador", "cancelado"},
    "em_coleta": {"em_rota", "aguardando_entregador"},
    "em_rota": {"entregue"},
    "entregue": {"concluido"},
    "retirado": {"concluido"},
    "nao_retirado": {"destinado"},
    "concluido": set(), "cancelado": set(), "expirado": set(), "destinado": set(),
}
# Estados em que o dinheiro do cliente fica (entra no repasse ao parceiro)
ESTADOS_FATURADOS = ("concluido", "nao_retirado", "destinado")
ESTADOS_ATIVOS_EMPRESA = ("pago", "recebido", "preparando", "pronto", "aguardando_retirada", "aguardando_entregador",
                          "entregador_designado", "em_coleta", "em_rota", "entregue")


class PedidosMixin:
    # ================================================================ CHECKOUT
    def _proximo_numero(self, c) -> int:
        c.execute("INSERT INTO contadores(nome, valor) VALUES ('pedido', 1000) ON CONFLICT(nome) DO UPDATE SET valor=valor+1")
        return c.execute("SELECT valor FROM contadores WHERE nome='pedido'").fetchone()["valor"]

    def cotar(self, ator: Ator, dados: dict) -> dict:
        """Calcula o total sem reservar nada (passo 6 do checkout)."""
        return self._montar(ator, dados, None)

    def _montar(self, ator: Ator, dados: dict, c) -> dict:
        if ator.papel != "cliente":
            raise SemPermissao("Só clientes fazem pedidos. Entre com uma conta de cliente.")
        itens = dados.get("itens") or []
        if not itens:
            raise ErroNegocio("Escolha pelo menos uma oferta.")
        consulta = (lambda sql, p=(): self._uma(c, sql, p)) if c is not None else self.banco.um
        ofertas, empresa_id, unidade_id = [], None, None
        for it in itens:
            o = consulta("SELECT * FROM ofertas WHERE id=?", (it.get("oferta_id"),))
            if not o or o["status"] != "ativa" or o["fim"] <= self.agora() or o["inicio"] > self.agora():
                raise ErroNegocio("Uma das ofertas não está mais disponível.")
            emp = consulta("SELECT aprovada, ativa FROM empresas WHERE id=?", (o["empresa_id"],))
            if not emp["aprovada"] or not emp["ativa"]:
                raise ErroNegocio("Uma das ofertas não está mais disponível.")
            if empresa_id and (o["empresa_id"] != empresa_id or o["unidade_id"] != unidade_id):
                raise ErroNegocio("Um pedido só pode ter ofertas da mesma loja. Faça um pedido para cada loja.")
            empresa_id, unidade_id = o["empresa_id"], o["unidade_id"]
            q = inteiro(it.get("quantidade"), "a quantidade", 1, 100)
            ja = consulta("""SELECT COALESCE(SUM(i.quantidade),0) AS n FROM pedido_itens i JOIN pedidos p ON p.id=i.pedido_id
                             WHERE i.oferta_id=? AND p.cliente_id=? AND p.status NOT IN ('cancelado','expirado')""",
                          (o["id"], ator.usuario_id))["n"]
            if q + ja > o["limite_por_cliente"]:
                raise ErroNegocio(f"Limite de {o['limite_por_cliente']} por cliente em \"{o['nome']}\".")
            if q > disponivel(o):
                raise ErroNegocio(f"Só restam {disponivel(o)} de \"{o['nome']}\".")
            ofertas.append((o, q))
        modo = dados.get("modo") or "retirada"
        cfg = consulta("SELECT * FROM config_empresa WHERE empresa_id=?", (empresa_id,)) or {}
        unidade = consulta("SELECT * FROM unidades WHERE id=?", (unidade_id,))
        entrega, lat, lng, endereco, distancia, r = 0, None, None, None, None, None
        if modo == "retirada":
            if not all(o["permite_retirada"] for o, _ in ofertas):
                raise ErroNegocio("Uma das ofertas não aceita retirada.")
        elif modo == "entrega":
            if not cfg.get("aceita_entrega") or not all(o["permite_entrega"] for o, _ in ofertas):
                raise ErroNegocio("Esta loja não faz entrega para estas ofertas.")
            endereco = texto(dados.get("endereco"), 250, True, "o endereço de entrega")
            lat, lng = real(dados.get("lat"), "a latitude", -90, 90), real(dados.get("lng"), "a longitude", -180, 180)
            r = self.rota(unidade["lat"], unidade["lng"], lat, lng, so_cache=c is not None) if lat is not None and unidade["lat"] is not None else None
            distancia = r["km"] if r else None
            if distancia is not None and distancia > cfg.get("raio_entrega_km", 5):
                raise ErroNegocio(f"Endereço fora da área de entrega da loja ({cfg.get('raio_entrega_km', 5):g} km).")
            entrega = cfg.get("taxa_entrega_centavos", 0)
        else:
            raise ErroNegocio("Escolha retirada ou entrega.")
        subtotal = sum(o["preco_centavos"] * q for o, q in ofertas)
        normal = sum(o["preco_normal_centavos"] * q for o, q in ofertas)
        emp = consulta("SELECT * FROM empresas WHERE id=?", (empresa_id,))
        pct = self.taxa_da_empresa(emp)
        taxa = round(subtotal * pct / 100)
        janelas_ini = [o["retirada_inicio"] for o, _ in ofertas if o["retirada_inicio"]]
        janelas_fim = [o["retirada_fim"] for o, _ in ofertas if o["retirada_fim"]]
        return {"empresa_id": empresa_id, "empresa": emp["nome"], "unidade_id": unidade_id, "unidade": unidade["nome"],
                "modo": modo, "ofertas": ofertas, "itens": [{"oferta_id": o["id"], "nome": o["nome"], "quantidade": q,
                "preco_centavos": o["preco_centavos"], "preco_normal_centavos": o["preco_normal_centavos"]} for o, q in ofertas],
                "subtotal_centavos": subtotal, "normal_centavos": normal, "economia_centavos": normal - subtotal,
                "entrega_centavos": entrega, "total_centavos": subtotal + entrega, "taxa_percentual": pct,
                "taxa_centavos": taxa, "repasse_centavos": subtotal - taxa, "endereco": endereco, "lat": lat, "lng": lng,
                "distancia_km": distancia, "distancia_fonte": r["fonte"] if modo == "entrega" and r else None,
                "tempo_min": r["minutos"] if modo == "entrega" and r else None, "janela_inicio": max(janelas_ini) if janelas_ini else None,
                "janela_fim": min(janelas_fim) if janelas_fim else None,
                "peso_kg": round(sum(o["peso_kg_unidade"] * q for o, q in ofertas), 3)}

    def criar_pedido(self, ator: Ator, dados: dict) -> dict:
        """Passos 3–8 do checkout: revalida estoque DENTRO da transação e reserva (nunca vende acima do estoque real)."""
        minutos = self.config_plataforma()["minutos_reserva"]
        pre = self._montar(ator, dados, None)  # confere tudo e já calcula a rota fora da transação (internet)
        if not self.recurso_habilitado(pre["empresa_id"], "pedidos"):
            raise ErroNegocio("Esta empresa não está recebendo pedidos pelo Sobrou+.")
        if not self.recurso_habilitado(pre["empresa_id"], "pagamentos"):
            raise ErroNegocio("O checkout não está disponível para esta empresa neste momento.")
        if pre["modo"] == "retirada" and not self.recurso_habilitado(pre["empresa_id"], "retirada"):
            raise ErroNegocio("A retirada no balcão está indisponível para esta empresa.")
        if pre["modo"] == "entrega" and not self.recurso_habilitado(pre["empresa_id"], "entrega"):
            raise ErroNegocio("A entrega está indisponível para esta empresa.")
        with self.banco.transacao() as c:
            m = self._montar(ator, dados, c)
            if not self.recurso_habilitado(m["empresa_id"], "pedidos"):
                raise ErroNegocio("Esta empresa não está recebendo pedidos pelo Sobrou+.")
            if not self.recurso_habilitado(m["empresa_id"], "pagamentos"):
                raise ErroNegocio("O checkout não está disponível para esta empresa neste momento.")
            if m["modo"] == "retirada" and not self.recurso_habilitado(m["empresa_id"], "retirada"):
                raise ErroNegocio("A retirada no balcão está indisponível para esta empresa.")
            if m["modo"] == "entrega" and not self.recurso_habilitado(m["empresa_id"], "entrega"):
                raise ErroNegocio("A entrega está indisponível para esta empresa.")
            pid, numero = novo_id(), self._proximo_numero(c)
            pin = f"{secrets.randbelow(10000):04d}"
            agora = self.agora()
            c.execute("""INSERT INTO pedidos(id, numero, empresa_id, unidade_id, cliente_id, modo, status, subtotal_centavos,
                         normal_centavos, entrega_centavos, total_centavos, taxa_percentual, taxa_centavos, repasse_centavos,
                         endereco_entrega, entrega_lat, entrega_lng, codigo_retirada, token_retirada, reserva_expira_em,
                         janela_inicio, janela_fim, peso_kg, observacao, criado_em, atualizado_em)
                         VALUES (?,?,?,?,?,?,'criado',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (pid, numero, m["empresa_id"], m["unidade_id"], ator.usuario_id, m["modo"], m["subtotal_centavos"],
                       m["normal_centavos"], m["entrega_centavos"], m["total_centavos"], m["taxa_percentual"],
                       m["taxa_centavos"], m["repasse_centavos"], m["endereco"], m["lat"], m["lng"], pin,
                       secrets.token_urlsafe(18), iso(self.agora_dt() + timedelta(minutes=minutos)),
                       m["janela_inicio"], m["janela_fim"], m["peso_kg"], texto(dados.get("observacao"), 300), agora, agora))
            for o, q in m["ofertas"]:
                n = c.execute("""UPDATE ofertas SET reservada=reservada+?
                                 WHERE id=? AND status='ativa' AND quantidade_total-reservada-vendida-expirada-destinada>=?""",
                              (q, o["id"], q)).rowcount
                if n != 1:
                    raise ErroNegocio(f"\"{o['nome']}\" acabou de esgotar. Tente uma quantidade menor.")
                c.execute("""INSERT INTO pedido_itens(id, pedido_id, oferta_id, nome, quantidade, preco_centavos, preco_normal_centavos, peso_kg)
                             VALUES (?,?,?,?,?,?,?,?)""", (novo_id(), pid, o["id"], o["nome"], q, o["preco_centavos"],
                                                          o["preco_normal_centavos"], o["peso_kg_unidade"] * q))
                self._movimento(c, o["id"], o["empresa_id"], "reserva", q, ator, pid)
                self._atualizar_esgotada(c, o["id"])
            self._historico(c, pid, None, "criado", ator, "pedido criado")
            self._historico(c, pid, "criado", "aguardando_pagamento", None, f"reserva por {minutos} min")
            c.execute("UPDATE pedidos SET status='aguardando_pagamento' WHERE id=?", (pid,))
        self.auditar(ator, "pedido.criar", pid, {"total": m["total_centavos"]}, empresa_id=m["empresa_id"])
        return self.obter_pedido(ator, pid)

    # ================================================================ PAGAMENTO ONLINE
    def pagar(self, ator: Ator, pedido_id: str, meio: str = "", base_url: str | None = None) -> dict:
        """Cria somente uma cobrança pelo checkout real do gateway configurado."""
        if meio != "checkout":
            raise ErroNegocio("Meio de pagamento inválido. Escolha o checkout online.")
        p = self.banco.um("SELECT empresa_id FROM pedidos WHERE id=?", (pedido_id,))
        if p and not self.recurso_habilitado(p["empresa_id"], "pagamentos"):
            raise ErroNegocio("O pagamento online está desativado para esta empresa.")
        pag = self.iniciar_pagamento_real(ator, pedido_id, meio, base_url)
        return {**self.obter_pedido(ator, pedido_id), "pagamento_iniciado": pag}

    def _efetivar_pagamento(self, c, p: dict, ator, nota: str) -> None:
        """Pagamento aprovado: reserva vira venda no estoque, pedido vai para 'pago' e a loja é avisada."""
        for it in c.execute("SELECT * FROM pedido_itens WHERE pedido_id=?", (p["id"],)).fetchall():
            c.execute("UPDATE ofertas SET reservada=reservada-?, vendida=vendida+? WHERE id=?", (it["quantidade"], it["quantidade"], it["oferta_id"]))
            self._movimento(c, it["oferta_id"], p["empresa_id"], "venda", it["quantidade"], ator, p["id"])
        self._mudar(c, p, "pago", ator, nota)
        self.avisar(f"Novo pedido #{p['numero']} pago — confirme o recebimento.", empresa_id=p["empresa_id"], conn=c)

    # ================================================================ ESTADOS
    def _historico(self, c, pedido_id, de, para, ator: Ator | None, nota=None):
        c.execute("INSERT INTO pedido_historico(id, pedido_id, de_status, para_status, usuario_id, nota, quando) VALUES (?,?,?,?,?,?,?)",
                  (novo_id(), pedido_id, de, para, ator.usuario_id if ator else None, nota, self.agora()))

    def _mudar(self, c, p: dict, novo: str, ator: Ator | None, nota=None) -> dict:
        if novo not in TRANSICOES.get(p["status"], set()):
            raise ErroNegocio(f"O pedido está \"{ESTADOS.get(p['status'])}\" e não pode ir para \"{ESTADOS.get(novo)}\".")
        concluido = self.agora() if novo in ("concluido", "cancelado", "expirado", "nao_retirado", "destinado") else None
        c.execute("UPDATE pedidos SET status=?, atualizado_em=?, concluido_em=COALESCE(?, concluido_em) WHERE id=?",
                  (novo, self.agora(), concluido, p["id"]))
        self._historico(c, p["id"], p["status"], novo, ator, nota)
        if novo == "concluido":
            # Um ponto por real gasto; gravado na mesma transação e único por pedido.
            pontos = int(p["subtotal_centavos"]) // 100
            if pontos:
                c.execute("INSERT OR IGNORE INTO pontos_fidelidade(pedido_id, cliente_id, pontos, criada_em) VALUES (?,?,?,?)",
                          (p["id"], p["cliente_id"], pontos, self.agora()))
        if novo in ("pronto", "aguardando_retirada", "aguardando_entregador", "entregador_designado", "em_rota", "entregue", "cancelado", "expirado", "nao_retirado"):
            self.avisar(f"Pedido #{p['numero']}: {ESTADOS[novo]}.", usuario_id=p["cliente_id"], link=f"/#pedido/{p['id']}", conn=c)
        p = {**p, "status": novo}
        return p

    def avancar_pedido(self, ator: Ator, pedido_id: str, acao: str) -> dict:
        """Ações da empresa: receber → preparar → pronto. 'Pronto' leva para retirada ou para o Dispatch."""
        ator.exigir("pedidos", "operar")
        destino = {"receber": "recebido", "preparar": "preparando", "pronto": "pronto"}.get(acao)
        if not destino:
            raise ErroNegocio("Ação inválida.")
        if destino == "pronto":  # rota loja → cliente calculada fora da transação
            pp = self.banco.um("SELECT p.entrega_lat, p.entrega_lng, u.lat, u.lng FROM pedidos p JOIN unidades u ON u.id=p.unidade_id WHERE p.id=?", (pedido_id,))
            if pp and None not in (pp["entrega_lat"], pp["lat"]):
                self.rota(pp["lat"], pp["lng"], pp["entrega_lat"], pp["entrega_lng"])
        with self.banco.transacao() as c:
            p = ator.conferir_empresa(self._uma(c, "SELECT * FROM pedidos WHERE id=?", (pedido_id,)), "Pedido")
            p = self._mudar(c, p, destino, ator)
            if destino == "pronto":
                if p["modo"] == "retirada":
                    self._mudar(c, p, "aguardando_retirada", None, "aguardando o cliente na janela de retirada")
                else:
                    self._mudar(c, p, "aguardando_entregador", None, "enviado ao Dispatch")
                    self._criar_entrega(c, p)
        self.auditar(ator, f"pedido.{acao}", pedido_id, empresa_id=p["empresa_id"])
        if destino == "pronto" and p["modo"] == "entrega":
            self.despachar()
        return self.obter_pedido(ator, pedido_id)

    def validar_retirada(self, ator: Ator, codigo: str, empresa_id: str | None = None) -> dict:
        """Na chegada do cliente: PIN de 4 dígitos + nº do pedido, ou o QR (token). Não deixa retirar duas vezes."""
        ator.exigir("retirada", "validar")
        eid = ator.empresa_alvo(empresa_id)
        cod = (codigo or "").strip()
        chave = "retirada:" + str(eid)
        if seguranca.FALHAS_RETIRADA.bloqueado(chave):
            raise ErroNegocio("Muitos códigos errados seguidos. Aguarde alguns minutos e confira o código com o cliente.")
        with self.banco.transacao() as c:
            if "-" in cod and cod.split("-")[0].isdigit():
                numero, pin = cod.split("-", 1)
                p = self._uma(c, "SELECT * FROM pedidos WHERE numero=? AND codigo_retirada=? AND empresa_id=?", (int(numero), pin, eid))
            else:
                p = self._uma(c, "SELECT * FROM pedidos WHERE token_retirada=? AND empresa_id=?", (cod, eid))
            if not p:
                seguranca.FALHAS_RETIRADA.falhou(chave)
                raise NaoEncontrado("Código não confere com nenhum pedido desta empresa.")
            if p["status"] in ("retirado", "concluido"):
                raise ErroNegocio(f"O pedido #{p['numero']} JÁ FOI RETIRADO. Não entregue de novo.")
            if p["modo"] != "retirada":
                raise ErroNegocio("Este pedido é de entrega, não de retirada.")
            if p["status"] != "aguardando_retirada":
                raise ErroNegocio(f"O pedido ainda está \"{ESTADOS.get(p['status'])}\". Marque como pronto antes.")
            p = self._mudar(c, p, "retirado", ator, "código validado na loja")
            for it in c.execute("SELECT * FROM pedido_itens WHERE pedido_id=?", (p["id"],)).fetchall():
                self._movimento(c, it["oferta_id"], eid, "retirada", it["quantidade"], ator, p["id"])
            self._mudar(c, p, "concluido", None, "retirada registrada")
        self.auditar(ator, "pedido.retirada", p["id"], empresa_id=eid)
        return self.obter_pedido(ator, p["id"])

    def confirmar_recebimento(self, ator: Ator, pedido_id: str) -> dict:
        with self.banco.transacao() as c:
            p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (pedido_id,))
            if not p or p["cliente_id"] != ator.usuario_id:
                raise NaoEncontrado("Pedido não encontrado.")
            self._mudar(c, p, "concluido", ator, "cliente confirmou o recebimento")
        return self.obter_pedido(ator, pedido_id)

    def cancelar_pedido(self, ator: Ator, pedido_id: str, motivo: str | None = None) -> dict:
        """Cliente cancela antes da loja receber; empresa (admin) cancela até ficar pronto. Estoque volta; pagamento de teste é estornado."""
        with self.banco.transacao() as c:
            p = self._uma(c, "SELECT * FROM pedidos WHERE id=?", (pedido_id,))
            if not p:
                raise NaoEncontrado("Pedido não encontrado.")
            if ator.papel == "cliente":
                if p["cliente_id"] != ator.usuario_id:
                    raise NaoEncontrado("Pedido não encontrado.")
                if p["status"] not in ("criado", "aguardando_pagamento", "pago"):
                    raise ErroNegocio("A loja já recebeu o pedido. Fale com a loja para cancelar.")
            else:
                ator.exigir("pedidos", "cancelar")
                ator.conferir_empresa(p, "Pedido")
                if p["status"] in ("em_coleta", "em_rota", "entregue", "retirado", "concluido"):
                    raise ErroNegocio("Pedido já saiu da loja; não dá para cancelar.")
                motivo = texto(motivo, 200, True, "o motivo do cancelamento")
            self._devolver_estoque(c, p, ator, "cancelamento")
            reais = [dict(g) for g in c.execute("SELECT id FROM pagamentos WHERE pedido_id=? AND status='aprovado' AND meio<>'teste'", (p["id"],)).fetchall()]
            pendentes_gateway = [dict(g) for g in c.execute("SELECT id FROM pagamentos WHERE pedido_id=? AND status IN ('pendente','em_analise') AND externo_id IS NOT NULL", (p["id"],)).fetchall()]
            self._estornar(c, p)
            c.execute("UPDATE entregas SET status='falhou', atualizada_em=? WHERE pedido_id=? AND status NOT IN ('entregue','falhou')",
                      (self.agora(), pedido_id))
            self._mudar(c, p, "cancelado", ator, motivo or "cancelado pelo cliente")
        for g in reais:
            self.estornar_externo(g["id"])
        for g in pendentes_gateway:
            self.cancelar_externo(g["id"])
        self.auditar(ator, "pedido.cancelar", pedido_id, {"motivo": motivo}, empresa_id=p["empresa_id"])
        return self.obter_pedido(ator, pedido_id)

    def _devolver_estoque(self, c, p, ator, tipo):
        pago = p["status"] not in ("criado", "aguardando_pagamento")
        for it in c.execute("SELECT * FROM pedido_itens WHERE pedido_id=?", (p["id"],)).fetchall():
            campo = "vendida" if pago else "reservada"
            c.execute(f"UPDATE ofertas SET {campo}={campo}-? WHERE id=?", (it["quantidade"], it["oferta_id"]))
            o = self._uma(c, "SELECT * FROM ofertas WHERE id=?", (it["oferta_id"],))
            if o["status"] == "encerrada":   # a venda já acabou: o que voltou vira sobra (pode ser doado)
                c.execute("UPDATE ofertas SET expirada=expirada+? WHERE id=?", (it["quantidade"], it["oferta_id"]))
            self._movimento(c, it["oferta_id"], p["empresa_id"], "liberacao" if not pago else tipo, it["quantidade"], ator, p["id"])
            self._atualizar_esgotada(c, it["oferta_id"])

    def _estornar(self, c, p):
        """Pagamento de teste: marca estornado na hora. Real: estornar_externo() pede o estorno ao Mercado Pago."""
        c.execute("UPDATE pagamentos SET status='estornado', atualizado_em=? WHERE pedido_id=? AND status='aprovado' AND meio='teste'", (self.agora(), p["id"]))
        c.execute("UPDATE pagamentos SET status='cancelado', atualizado_em=? WHERE pedido_id=? AND status IN ('pendente','em_analise')", (self.agora(), p["id"]))

    # ================================================================ CONSULTAS
    def _pedido_completo(self, p: dict, ver_cliente: bool, incluir_avaliacao_cliente: bool = False) -> dict:
        p = dict(p)
        p["status_nome"] = ESTADOS.get(p["status"])
        p["itens"] = self.banco.todos("SELECT * FROM pedido_itens WHERE pedido_id=?", (p["id"],))
        p["historico"] = self.banco.todos("""SELECT h.*, u.nome AS usuario FROM pedido_historico h LEFT JOIN usuarios u ON u.id=h.usuario_id
                                             WHERE h.pedido_id=? ORDER BY h.quando, h.rowid""", (p["id"],))
        p["pagamentos"] = self.banco.todos("SELECT meio, valor_centavos, status, criado_em, qr_code, qr_base64, link_pagamento, expira_em FROM pagamentos WHERE pedido_id=? ORDER BY criado_em", (p["id"],))
        p["entrega"] = self.banco.um("""SELECT en.*, u.nome AS entregador, er.lat AS entregador_lat, er.lng AS entregador_lng, er.posicao_em
                                        FROM entregas en LEFT JOIN entregadores er ON er.id=en.entregador_id
                                        LEFT JOIN usuarios u ON u.id=er.usuario_id WHERE en.pedido_id=?""", (p["id"],))
        uni = self.banco.um("SELECT nome, endereco, bairro, cidade, lat, lng, telefone, instrucoes_retirada FROM unidades WHERE id=?", (p["unidade_id"],))
        p["unidade"] = uni
        p["empresa"] = (self.banco.um("SELECT nome FROM empresas WHERE id=?", (p["empresa_id"],)) or {}).get("nome")
        p["economia_centavos"] = p["normal_centavos"] - p["subtotal_centavos"]
        if not ver_cliente:
            # a loja nunca vê o PIN nem o token: quem tem o código é o cliente
            p.pop("codigo_retirada", None)
            p.pop("token_retirada", None)
            cli = self.banco.um("SELECT nome, telefone FROM usuarios WHERE id=?", (p["cliente_id"],)) or {}
            p["cliente"] = cli.get("nome")
            p["cliente_telefone"] = cli.get("telefone")
        p["avaliacao"] = self.banco.um("SELECT nota, comentario, resposta FROM avaliacoes WHERE pedido_id=?", (p["id"],))
        if incluir_avaliacao_cliente:
            p["avaliacao_cliente"] = self.banco.um("SELECT nota, comentario FROM avaliacoes_clientes WHERE pedido_id=?", (p["id"],))
        return p

    def obter_pedido(self, ator: Ator, pedido_id: str) -> dict:
        p = self.banco.um("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if not p:
            raise NaoEncontrado("Pedido não encontrado.")
        if ator.papel == "cliente":
            if p["cliente_id"] != ator.usuario_id:
                raise NaoEncontrado("Pedido não encontrado.")
            return self._pedido_completo(p, True)
        if ator.papel == "entregador":
            e = self.banco.um("""SELECT en.id FROM entregas en JOIN entregadores er ON er.id=en.entregador_id
                                 WHERE en.pedido_id=? AND er.usuario_id=?""", (pedido_id, ator.usuario_id))
            if not e:
                raise NaoEncontrado("Pedido não encontrado.")
            return self._pedido_completo(p, False)
        ator.exigir("pedidos", "ver")
        return self._pedido_completo(ator.conferir_empresa(p, "Pedido"), False, True)

    def listar_pedidos(self, ator: Ator, empresa_id: str | None = None, status: str | None = None, limite: int = 200) -> list[dict]:
        cond, par = [], []
        if ator.papel == "cliente":
            cond.append("p.cliente_id=?")
            par.append(ator.usuario_id)
        else:
            ator.exigir("pedidos", "ver")
            if not (ator.plataforma and not empresa_id):
                cond.append("p.empresa_id=?")
                par.append(ator.empresa_alvo(empresa_id))
        if status == "ativos":
            cond.append(f"p.status IN ({','.join('?' * len(ESTADOS_ATIVOS_EMPRESA))})")
            par += list(ESTADOS_ATIVOS_EMPRESA)
        elif status:
            cond.append("p.status=?")
            par.append(status)
        where = ("WHERE " + " AND ".join(cond)) if cond else ""
        linhas = self.banco.todos(f"""SELECT p.*, e.nome AS empresa, un.nome AS unidade, cl.nome AS cliente,
                                             (SELECT GROUP_CONCAT(i.quantidade || 'x ' || i.nome, ', ') FROM pedido_itens i WHERE i.pedido_id=p.id) AS resumo
                                      FROM pedidos p JOIN empresas e ON e.id=p.empresa_id JOIN unidades un ON un.id=p.unidade_id
                                      JOIN usuarios cl ON cl.id=p.cliente_id {where} ORDER BY p.criado_em DESC LIMIT ?""", (*par, limite))
        for p in linhas:
            p["status_nome"] = ESTADOS.get(p["status"])
            if ator.papel != "cliente":
                p.pop("codigo_retirada", None)
                p.pop("token_retirada", None)
            else:
                p.pop("cliente", None)
        return linhas
