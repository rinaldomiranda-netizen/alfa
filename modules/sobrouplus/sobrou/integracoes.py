"""Integrações prontas para ATIVAR: pagamento real (Mercado Pago: Pix e cartão) e WhatsApp (API oficial da Meta).

Ficam desligadas até a equipe Sobrou+ colocar as credenciais em Painel → Integrações. Credenciais ficam só no servidor,
nunca voltam para a tela (aparecem mascaradas). Nenhum pagamento é confirmado pelo que chega no aviso (webhook):
o sistema sempre consulta o Mercado Pago para conferir status e valor antes de liberar o pedido.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import timedelta

from .nucleo import Ator, ErroNegocio, NaoEncontrado, iso, ler_data, novo_id, texto
from .rede import ErroRede

MP_API = "https://api.mercadopago.com"
WA_API = "https://graph.facebook.com"
SEGREDOS = {"mercadopago": ("access_token", "webhook_secret"), "whatsapp": ("token",), "mapas": (), "email": ("senha",)}
CAMPOS = {
    "mercadopago": ("ligado", "access_token", "webhook_secret", "permitir_teste", "url_publica"),
    "whatsapp": ("ligado", "token", "phone_number_id", "template", "idioma", "api_versao"),
    "mapas": ("ligado", "rotas_url", "enderecos_url"),
    "email": ("ligado", "servidor", "porta", "usuario", "senha", "remetente"),
}


def _mascarar(v: str | None) -> str | None:
    if not v:
        return None
    return "••••" + v[-4:] if len(v) > 8 else "••••"


def telefone_whatsapp(tel: str | None) -> str | None:
    d = re.sub(r"\D", "", tel or "")
    if len(d) in (10, 11):
        d = "55" + d
    return d if 12 <= len(d) <= 13 else None


class IntegracoesMixin:
    # ================================================================ CONFIGURAÇÃO
    def ler_integracao(self, nome: str) -> dict:
        r = self.banco.um("SELECT valor FROM config WHERE chave=?", ("int:" + nome,))
        try:
            return json.loads(r["valor"]) if r else {}
        except ValueError:
            return {}

    def integracoes_publicas(self, ator: Ator) -> dict:
        ator.exigir("sistema", "ver")
        saida = {}
        for nome, campos in CAMPOS.items():
            c = self.ler_integracao(nome)
            saida[nome] = {k: (_mascarar(c.get(k)) if k in SEGREDOS[nome] else c.get(k)) for k in campos}
            saida[nome]["configurado"] = self._integracao_pronta(nome, c)
        saida["mapas"]["ligado"] = self._cfg_mapas()["ligado"]
        return saida

    def _integracao_pronta(self, nome: str, c: dict | None = None) -> bool:
        c = c if c is not None else self.ler_integracao(nome)
        if nome == "mercadopago":
            return bool(c.get("ligado") and c.get("access_token"))
        if nome == "whatsapp":
            return bool(c.get("ligado") and c.get("token") and c.get("phone_number_id"))
        if nome == "email":
            return bool(c.get("ligado") and c.get("servidor") and c.get("remetente"))
        return True

    def salvar_integracao(self, ator: Ator, nome: str, dados: dict) -> dict:
        ator.exigir("sistema", "ver")
        if nome not in CAMPOS:
            raise NaoEncontrado("Integração desconhecida.")
        atual = self.ler_integracao(nome)
        for k in CAMPOS[nome]:
            if k not in dados:
                continue
            v = dados[k]
            if k in SEGREDOS[nome]:
                if v in (None, "") or str(v).startswith("••••"):
                    continue  # campo em branco = manter o segredo que já existe
                atual[k] = str(v).strip()
            elif k in ("ligado", "permitir_teste"):
                atual[k] = v in (True, 1, "1", "true", "on")
            else:
                atual[k] = texto(v, 200)
        self.banco.executar("INSERT INTO config(chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                            ("int:" + nome, json.dumps(atual)))
        self.auditar(ator, "integracao.salvar", nome, {"campos": sorted(k for k in dados if k in CAMPOS[nome] and k not in SEGREDOS[nome]),
                                                         "segredo_trocado": any(dados.get(k) and not str(dados[k]).startswith("••••") for k in SEGREDOS[nome])},
                     empresa_id=None)
        return self.integracoes_publicas(ator)[nome]

    def testar_integracao(self, ator: Ator, nome: str, dados: dict | None = None) -> dict:
        ator.exigir("sistema", "ver")
        try:
            if nome == "mercadopago":
                c = self.ler_integracao("mercadopago")
                if not c.get("access_token"):
                    raise ErroNegocio("Coloque o Access Token do Mercado Pago.")
                r = self.rede("GET", f"{MP_API}/users/me", cabecalhos={"Authorization": "Bearer " + c["access_token"]})
                teste = c["access_token"].startswith("TEST-")
                return {"ok": True, "mensagem": f"Conectado à conta {r.get('nickname') or r.get('id')} ({'credencial de TESTE' if teste else 'PRODUÇÃO'})."}
            if nome == "whatsapp":
                c = self.ler_integracao("whatsapp")
                if not (c.get("token") and c.get("phone_number_id")):
                    raise ErroNegocio("Coloque o token e o Phone Number ID.")
                tel = telefone_whatsapp((dados or {}).get("telefone"))
                if tel:
                    self._enviar_whatsapp(c, tel, "Sobrou+: teste de envio pelo painel. Está funcionando!")
                    return {"ok": True, "mensagem": f"Mensagem de teste enviada para {tel}."}
                r = self.rede("GET", f"{WA_API}/{c.get('api_versao') or 'v21.0'}/{c['phone_number_id']}",
                              cabecalhos={"Authorization": "Bearer " + c["token"]})
                return {"ok": True, "mensagem": f"Número conectado: {r.get('display_phone_number') or r.get('id')}."}
            if nome == "email":
                para = texto((dados or {}).get("telefone") or (dados or {}).get("email"), 160) or ator.extras.get("email")
                if not self._email_cfg():
                    raise ErroNegocio("Preencha servidor e remetente e marque Ligado.")
                ok = self.enviar_email(para, "Sobrou+: teste de e-mail", "Se você recebeu esta mensagem, o envio de e-mail do Sobrou+ está funcionando.")
                return {"ok": ok, "mensagem": f"E-mail de teste enviado para {para}." if ok else "Falhou. Confira servidor, porta, usuário e senha (veja os erros em Sistema)."}
            if nome == "mapas":
                r = self.rota(-10.9111, -37.0717, -10.9472, -37.0731)
                if r["fonte"] != "ruas":
                    return {"ok": False, "mensagem": "Serviço de rotas não respondeu — usando estimativa (linha reta × 1,35)."}
                return {"ok": True, "mensagem": f"Rota de teste em Aracaju: {r['km']} km pelas ruas, ~{r['minutos']} min."}
        except ErroRede as e:
            detalhe = None
            if isinstance(e.corpo, dict):
                erro = e.corpo.get("error")
                detalhe = e.corpo.get("message") or (erro.get("message") if isinstance(erro, dict) else erro)
            return {"ok": False, "mensagem": f"Falhou: {detalhe or e}"}
        raise NaoEncontrado("Integração desconhecida.")

    # ================================================================ MERCADO PAGO
    def _mp(self) -> dict | None:
        c = self.ler_integracao("mercadopago")
        return c if self._integracao_pronta("mercadopago", c) else None

    def pagamento_teste_permitido(self) -> bool:
        c = self.ler_integracao("mercadopago")
        return not self._integracao_pronta("mercadopago", c) or bool(c.get("permitir_teste"))

    def meios_pagamento(self) -> dict:
        real = self._mp() is not None
        return {"teste": self.pagamento_teste_permitido(), "pix": real, "cartao": real}

    def _cab_mp(self, c: dict, idem: str | None = None) -> dict:
        cab = {"Authorization": "Bearer " + c["access_token"]}
        if idem:
            cab["X-Idempotency-Key"] = idem
        return cab

    def iniciar_pagamento_real(self, ator: Ator, pedido_id: str, meio: str, base_url: str | None) -> dict:
        """Pix: devolve QR Code e "copia e cola". Cartão: link do Checkout do Mercado Pago. Confirmação: webhook + consulta."""
        c = self._mp()
        if not c:
            raise ErroNegocio("Pagamento real ainda não foi ativado pela equipe Sobrou+.")
        p = self.banco.um("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if not p or p["cliente_id"] != ator.usuario_id:
            raise NaoEncontrado("Pedido não encontrado.")
        if p["status"] != "aguardando_pagamento":
            raise ErroNegocio("Este pedido não está aguardando pagamento.")
        if p["reserva_expira_em"] and p["reserva_expira_em"] <= self.agora():
            raise ErroNegocio("O tempo da reserva acabou. Faça o pedido de novo.")
        aberto = self.banco.um("SELECT * FROM pagamentos WHERE pedido_id=? AND status='pendente' AND meio=?", (pedido_id, meio))
        if aberto and (not aberto["expira_em"] or aberto["expira_em"] > self.agora()):
            return self._pagamento_publico(aberto)
        cliente = self.banco.um("SELECT nome, email FROM usuarios WHERE id=?", (ator.usuario_id,))
        valor = round(p["total_centavos"] / 100, 2)
        base = (c.get("url_publica") or base_url or "").rstrip("/")
        aviso = f"{base}/api/webhooks/mercadopago" if base.startswith("https://") else None
        empresa = (self.banco.um("SELECT nome FROM empresas WHERE id=?", (p["empresa_id"],)) or {}).get("nome", "Sobrou+")
        descricao = f"Sobrou+ pedido #{p['numero']} — {empresa}"[:120]
        expira = p["reserva_expira_em"] or iso(self.agora_dt() + timedelta(minutes=30))
        try:
            if meio == "pix":
                corpo = {"transaction_amount": valor, "payment_method_id": "pix", "description": descricao,
                         "external_reference": pedido_id, "payer": {"email": cliente["email"], "first_name": cliente["nome"].split(" ")[0]},
                         "date_of_expiration": ler_data(expira).astimezone().isoformat(timespec="milliseconds")}
                if aviso:
                    corpo["notification_url"] = aviso
                r = self.rede("POST", f"{MP_API}/v1/payments", corpo, self._cab_mp(c, f"pix-{pedido_id}-{secrets.token_hex(4)}"))
                dados = (r.get("point_of_interaction") or {}).get("transaction_data") or {}
                pag = {"externo_id": str(r.get("id")), "qr_code": dados.get("qr_code"), "qr_base64": dados.get("qr_code_base64"),
                       "link_pagamento": dados.get("ticket_url"), "expira_em": expira}
            elif meio == "cartao":
                corpo = {"items": [{"title": descricao, "quantity": 1, "unit_price": valor, "currency_id": "BRL"}],
                         "external_reference": pedido_id, "payer": {"email": cliente["email"], "name": cliente["nome"]},
                         "expires": True, "expiration_date_to": ler_data(expira).astimezone().isoformat(timespec="milliseconds"),
                         "payment_methods": {"excluded_payment_types": [{"id": "ticket"}], "installments": 1}}
                if base:
                    volta = f"{base}/#pedido/{pedido_id}"
                    corpo["back_urls"] = {"success": volta, "pending": volta, "failure": volta}
                    corpo["auto_return"] = "approved" if base.startswith("https://") else None
                    corpo = {k: v for k, v in corpo.items() if v is not None}
                if aviso:
                    corpo["notification_url"] = aviso
                r = self.rede("POST", f"{MP_API}/checkout/preferences", corpo, self._cab_mp(c, f"pref-{pedido_id}-{secrets.token_hex(4)}"))
                pag = {"externo_id": None, "qr_code": None, "qr_base64": None,
                       "link_pagamento": r.get("init_point") if not c["access_token"].startswith("TEST-") else (r.get("sandbox_init_point") or r.get("init_point")),
                       "expira_em": expira}
            else:
                raise ErroNegocio("Meio de pagamento inválido.")
        except ErroRede as e:
            self.registrar_erro("mercadopago." + meio, "POST", e)
            raise ErroNegocio("O Mercado Pago não respondeu agora. Tente de novo em instantes.") from e
        pid = novo_id()
        agora = self.agora()
        self.banco.executar("""INSERT INTO pagamentos(id, pedido_id, empresa_id, meio, valor_centavos, status, externo_id, qr_code, qr_base64,
                               link_pagamento, expira_em, criado_em, atualizado_em) VALUES (?,?,?,?,?,'pendente',?,?,?,?,?,?,?)""",
                            (pid, pedido_id, p["empresa_id"], meio, p["total_centavos"], pag["externo_id"], pag["qr_code"], pag["qr_base64"],
                             pag["link_pagamento"], pag["expira_em"], agora, agora))
        self.auditar(ator, "pagamento.iniciar", pedido_id, {"meio": meio, "valor": p["total_centavos"]}, empresa_id=p["empresa_id"])
        return self._pagamento_publico(self.banco.um("SELECT * FROM pagamentos WHERE id=?", (pid,)))

    @staticmethod
    def _pagamento_publico(g: dict) -> dict:
        return {k: g.get(k) for k in ("id", "meio", "status", "valor_centavos", "qr_code", "qr_base64", "link_pagamento", "expira_em")}

    def verificar_pagamento(self, ator: Ator, pedido_id: str) -> dict:
        """O app do cliente pergunta a cada poucos segundos. Consulta o Mercado Pago se ainda estiver pendente."""
        p = self.banco.um("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if not p or p["cliente_id"] != ator.usuario_id:
            raise NaoEncontrado("Pedido não encontrado.")
        if p["status"] == "aguardando_pagamento" and self._mp():
            for g in self.banco.todos("SELECT * FROM pagamentos WHERE pedido_id=? AND status='pendente' AND meio<>'teste'", (pedido_id,)):
                try:
                    if g["externo_id"]:
                        self.processar_pagamento_mp(g["externo_id"])
                    else:
                        r = self.rede("GET", f"{MP_API}/v1/payments/search?external_reference={pedido_id}&sort=date_created&criteria=desc",
                                      cabecalhos=self._cab_mp(self._mp()))
                        for res in r.get("results", [])[:3]:
                            self.processar_pagamento_mp(str(res["id"]))
                except ErroRede:
                    pass
        return self.obter_pedido(ator, pedido_id)

    def webhook_mercadopago(self, consulta: dict, corpo: dict, cabecalhos) -> dict:
        """Aviso do Mercado Pago. Confere a assinatura (se a chave secreta estiver configurada) e CONSULTA o pagamento."""
        c = self._mp()
        if not c:
            return {"ok": False, "motivo": "desligado"}
        dado_id = str(consulta.get("data.id") or (corpo.get("data") or {}).get("id") or consulta.get("id") or "")
        tipo = consulta.get("type") or consulta.get("topic") or corpo.get("type") or corpo.get("topic")
        if not dado_id or tipo not in ("payment", None):
            return {"ok": True, "ignorado": True}
        segredo = c.get("webhook_secret")
        if segredo:
            assinatura = cabecalhos.get("x-signature") or ""
            partes = dict(p.strip().split("=", 1) for p in assinatura.split(",") if "=" in p)
            manifesto = f"id:{dado_id.lower()};request-id:{cabecalhos.get('x-request-id') or ''};ts:{partes.get('ts', '')};"
            esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
            if not partes.get("v1") or not hmac.compare_digest(esperado, partes["v1"]):
                self.registrar_erro("webhook.mercadopago", "POST", ErroNegocio("assinatura inválida"))
                return {"ok": False, "motivo": "assinatura"}
        try:
            return self.processar_pagamento_mp(dado_id)
        except ErroRede as e:
            self.registrar_erro("webhook.mercadopago", "POST", e)
            return {"ok": False, "motivo": "consulta"}

    def processar_pagamento_mp(self, externo_id: str) -> dict:
        c = self._mp()
        r = self.rede("GET", f"{MP_API}/v1/payments/{externo_id}", cabecalhos=self._cab_mp(c))
        pedido_id = r.get("external_reference")
        status_mp = r.get("status")
        valor = round(float(r.get("transaction_amount") or 0) * 100)
        with self.banco.transacao() as cx:
            p = self._uma(cx, "SELECT * FROM pedidos WHERE id=?", (pedido_id,))
            if not p:
                return {"ok": True, "ignorado": "pedido desconhecido"}
            g = self._uma(cx, "SELECT * FROM pagamentos WHERE externo_id=?", (str(externo_id),)) or \
                self._uma(cx, "SELECT * FROM pagamentos WHERE pedido_id=? AND status='pendente' AND meio<>'teste' ORDER BY criado_em DESC", (pedido_id,))
            if not g:
                return {"ok": True, "ignorado": "pagamento desconhecido"}
            if g["status"] in ("aprovado", "estornado"):
                return {"ok": True, "ja_processado": g["status"]}
            cx.execute("UPDATE pagamentos SET externo_id=?, atualizado_em=? WHERE id=?", (str(externo_id), self.agora(), g["id"]))
            if status_mp in ("rejected", "cancelled"):
                cx.execute("UPDATE pagamentos SET status='recusado', atualizado_em=? WHERE id=?", (self.agora(), g["id"]))
                return {"ok": True, "status": "recusado"}
            if status_mp != "approved":
                return {"ok": True, "status": "pendente"}
            if valor != p["total_centavos"]:
                cx.execute("UPDATE pagamentos SET status='divergente', atualizado_em=? WHERE id=?", (self.agora(), g["id"]))
                self.avisar(f"Pagamento do pedido #{p['numero']} com valor diferente do pedido. Conferir.", papel_alvo="plataforma", conn=cx)
                return {"ok": False, "status": "divergente"}
            if p["status"] != "aguardando_pagamento":
                # pagou depois que a reserva venceu ou o pedido foi cancelado: devolve o dinheiro
                cx.execute("UPDATE pagamentos SET status='aprovado', atualizado_em=? WHERE id=?", (self.agora(), g["id"]))
                estornar = True
            else:
                cx.execute("UPDATE pagamentos SET status='aprovado', valor_centavos=?, atualizado_em=? WHERE id=?", (valor, self.agora(), g["id"]))
                self._efetivar_pagamento(cx, p, None, f"pagamento {g['meio']} aprovado pelo Mercado Pago")
                estornar = False
        if estornar:
            self.estornar_externo(g["id"])
            return {"ok": True, "status": "estornado (pedido já não estava aguardando)"}
        self.auditar(None, "pagamento.aprovado", pedido_id, {"meio": g["meio"], "valor": valor}, empresa_id=p["empresa_id"])
        return {"ok": True, "status": "aprovado"}

    def estornar_externo(self, pagamento_id: str) -> bool:
        g = self.banco.um("SELECT * FROM pagamentos WHERE id=?", (pagamento_id,))
        c = self._mp()
        if not g or not g["externo_id"] or not c:
            return False
        try:
            self.rede("POST", f"{MP_API}/v1/payments/{g['externo_id']}/refunds", {}, self._cab_mp(c, f"estorno-{pagamento_id}"))
        except ErroRede as e:
            self.banco.executar("UPDATE pagamentos SET status='estorno_pendente', atualizado_em=? WHERE id=?", (self.agora(), pagamento_id))
            self.registrar_erro("mercadopago.estorno", "POST", e)
            self.avisar("Estorno no Mercado Pago falhou — refazer pelo painel do Mercado Pago.", papel_alvo="plataforma")
            return False
        self.banco.executar("UPDATE pagamentos SET status='estornado', atualizado_em=? WHERE id=?", (self.agora(), pagamento_id))
        return True

    # ================================================================ WHATSAPP
    def _wa(self) -> dict | None:
        c = self.ler_integracao("whatsapp")
        return c if self._integracao_pronta("whatsapp", c) else None

    def enfileirar_whatsapp(self, usuario_id: str, texto_msg: str, conn=None) -> None:
        if not self._wa():
            return
        consulta = (lambda s, p: self._uma(conn, s, p)) if conn is not None else self.banco.um
        u = consulta("SELECT telefone FROM usuarios WHERE id=?", (usuario_id,))
        tel = telefone_whatsapp((u or {}).get("telefone"))
        if not tel:
            return
        sql = "INSERT INTO fila_mensagens(id, canal, usuario_id, telefone, texto, criada_em) VALUES (?,?,?,?,?,?)"
        (conn.execute if conn is not None else self.banco.executar)(sql, (novo_id(), "whatsapp", usuario_id, tel, texto_msg[:900], self.agora()))

    def _enviar_whatsapp(self, c: dict, tel: str, texto_msg: str) -> None:
        url = f"{WA_API}/{c.get('api_versao') or 'v21.0'}/{c['phone_number_id']}/messages"
        if c.get("template"):
            corpo = {"messaging_product": "whatsapp", "to": tel, "type": "template",
                     "template": {"name": c["template"], "language": {"code": c.get("idioma") or "pt_BR"},
                                  "components": [{"type": "body", "parameters": [{"type": "text", "text": texto_msg[:900]}]}]}}
        else:
            corpo = {"messaging_product": "whatsapp", "to": tel, "type": "text", "text": {"body": texto_msg[:900]}}
        self.rede("POST", url, corpo, {"Authorization": "Bearer " + c["token"]})

    def enviar_fila_whatsapp(self, limite: int = 20) -> int:
        c = self._wa()
        if not c:
            return 0
        enviadas = 0
        for m in self.banco.todos("SELECT * FROM fila_mensagens WHERE status='pendente' AND tentativas<3 ORDER BY criada_em LIMIT ?", (limite,)):
            try:
                self._enviar_whatsapp(c, m["telefone"], m["texto"])
                self.banco.executar("UPDATE fila_mensagens SET status='enviada', enviada_em=?, tentativas=tentativas+1 WHERE id=?", (self.agora(), m["id"]))
                enviadas += 1
            except ErroRede as e:
                erro = json.dumps(e.corpo)[:300] if e.corpo else str(e)
                self.banco.executar("UPDATE fila_mensagens SET tentativas=tentativas+1, erro=?, status=CASE WHEN tentativas+1>=3 THEN 'falhou' ELSE 'pendente' END WHERE id=?",
                                    (erro, m["id"]))
        return enviadas

    def resumo_mensagens(self, ator: Ator) -> dict:
        ator.exigir("sistema", "ver")
        cont = {r["status"]: r["n"] for r in self.banco.todos("SELECT status, COUNT(*) AS n FROM fila_mensagens GROUP BY status")}
        ultimas = self.banco.todos("SELECT telefone, texto, status, erro, criada_em, enviada_em FROM fila_mensagens ORDER BY criada_em DESC LIMIT 20")
        for u in ultimas:
            u["telefone"] = (u["telefone"] or "")[:4] + "•••••" + (u["telefone"] or "")[-2:]
        return {"contagem": cont, "ultimas": ultimas}
