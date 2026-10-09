"""Integrações prontas para ATIVAR: pagamento real (Mercado Pago: Pix e cartão) e WhatsApp (API oficial da Meta).

Credenciais de pagamento são lidas exclusivamente do ambiente do servidor. Nenhum pagamento é confirmado pelo retorno do app ou pelo conteúdo do webhook: o backend valida a assinatura e consulta o Mercado Pago antes de liberar o pedido.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import timedelta

from . import seguranca
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
            dados = json.loads(r["valor"]) if r else {}
        except ValueError:
            return {}
        if not isinstance(dados, dict):
            return {}
        guardado_aberto = False
        for k in SEGREDOS.get(nome, ()):
            if dados.get(k):
                guardado_aberto = guardado_aberto or not str(dados[k]).startswith(seguranca.PREFIXO_PROTEGIDO)
                dados[k] = seguranca.revelar_segredo(dados[k])
        if guardado_aberto and seguranca.segredo_protegido_disponivel():
            self._gravar_integracao(nome, dados)  # token antigo, guardado aberto: protege agora
        return dados

    def _gravar_integracao(self, nome: str, dados: dict) -> None:
        guardar = dict(dados)
        for k in SEGREDOS.get(nome, ()):
            if guardar.get(k):
                guardar[k] = seguranca.proteger_segredo(str(guardar[k]))
        self.banco.executar("INSERT INTO config(chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                            ("int:" + nome, json.dumps(guardar)))

    def integracoes_publicas(self, ator: Ator) -> dict:
        ator.exigir("sistema", "ver")
        saida = {}
        for nome, campos in CAMPOS.items():
            if nome == "mercadopago":
                cfg = self._mp() or {}
                saida[nome] = {"ligado": bool(cfg), "configurado": bool(cfg), "provedor": os.getenv("SOBROU_PAYMENT_PROVIDER", "").strip().lower() or None,
                               "ambiente": os.getenv("SOBROU_PAYMENT_ENV", "sandbox").strip().lower(),
                               "public_key": cfg.get("public_key"), "access_token_configurado": bool(cfg.get("access_token")),
                               "webhook_secret_configurado": bool(cfg.get("webhook_secret")),
                               "webhook_url": os.getenv("SOBROU_PAYMENT_WEBHOOK_URL", "").strip() or None,
                               "parcelas_maximas": self._parcelas_maximas()}
                continue
            c = self.ler_integracao(nome)
            saida[nome] = {k: (_mascarar(c.get(k)) if k in SEGREDOS[nome] else c.get(k)) for k in campos}
            saida[nome]["configurado"] = self._integracao_pronta(nome, c)
        saida["mapas"]["ligado"] = self._cfg_mapas()["ligado"]
        return saida

    def _integracao_pronta(self, nome: str, c: dict | None = None) -> bool:
        c = c if c is not None else self.ler_integracao(nome)
        if nome == "mercadopago":
            return self._mp() is not None
        if nome == "whatsapp":
            return bool(c.get("ligado") and c.get("token") and c.get("phone_number_id"))
        if nome == "email":
            return bool(c.get("ligado") and c.get("servidor") and c.get("remetente"))
        return True

    def salvar_integracao(self, ator: Ator, nome: str, dados: dict) -> dict:
        ator.exigir("sistema", "ver")
        if nome == "mercadopago":
            raise ErroNegocio("Pagamentos são configurados apenas por variáveis de ambiente no servidor. Consulte PAGAMENTOS.md.")
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
                if atual[k] and nome == "mapas" and k in ("rotas_url", "enderecos_url") and not seguranca.url_externa_segura(atual[k]):
                    raise ErroNegocio("Endereço do serviço de mapas inválido: use um endereço https:// da internet.")
                if atual[k] and nome == "email" and k == "servidor" and not seguranca.host_externo_seguro(atual[k]):
                    raise ErroNegocio("Servidor de e-mail inválido: use o endereço do provedor (ex.: smtp.gmail.com).")
        self._gravar_integracao(nome, atual)
        self.auditar(ator, "integracao.salvar", nome, {"campos": sorted(k for k in dados if k in CAMPOS[nome] and k not in SEGREDOS[nome]),
                                                         "segredo_trocado": any(dados.get(k) and not str(dados[k]).startswith("••••") for k in SEGREDOS[nome])},
                     empresa_id=None)
        return self.integracoes_publicas(ator)[nome]

    def testar_integracao(self, ator: Ator, nome: str, dados: dict | None = None) -> dict:
        ator.exigir("sistema", "ver")
        try:
            if nome == "mercadopago":
                c = self._mp()
                if not c:
                    raise ErroNegocio("Configure provedor, ambiente, credenciais e URL HTTPS do webhook no servidor. Consulte PAGAMENTOS.md.")
                r = self.rede("GET", f"{MP_API}/users/me", cabecalhos={"Authorization": "Bearer " + c["access_token"]})
                return {"ok": True, "mensagem": f"Conectado à conta {r.get('nickname') or r.get('id')} no ambiente {c['ambiente']}."}
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
        provedor = os.getenv("SOBROU_PAYMENT_PROVIDER", "").strip().lower()
        ambiente = os.getenv("SOBROU_PAYMENT_ENV", "sandbox").strip().lower()
        if provedor != "mercadopago" or ambiente not in ("sandbox", "production"):
            return None
        sufixo = "SANDBOX" if ambiente == "sandbox" else "PRODUCTION"
        access = os.getenv(f"MERCADOPAGO_ACCESS_TOKEN_{sufixo}", "").strip()
        public = os.getenv(f"MERCADOPAGO_PUBLIC_KEY_{sufixo}", "").strip()
        secret = os.getenv(f"MERCADOPAGO_WEBHOOK_SECRET_{sufixo}", "").strip()
        webhook = os.getenv("SOBROU_PAYMENT_WEBHOOK_URL", "").strip()
        if not (access and public and secret and webhook.startswith("https://")):
            return None
        if ambiente == "sandbox" and not (access.startswith("TEST-") and public.startswith("TEST-")):
            return None
        if ambiente == "production" and (access.startswith("TEST-") or public.startswith("TEST-")):
            return None
        return {"provedor": provedor, "ambiente": ambiente, "access_token": access, "public_key": public,
                "webhook_secret": secret, "webhook_url": webhook}

    @staticmethod
    def _parcelas_maximas() -> int:
        try:
            return max(1, min(24, int(os.getenv("SOBROU_PAYMENT_MAX_INSTALLMENTS", "12"))))
        except (TypeError, ValueError):
            return 12

    def pagamento_teste_permitido(self) -> bool:
        return False

    def meios_pagamento(self) -> dict:
        real = self._mp() is not None
        return {"teste": False, "pix": real, "cartao": real, "boleto": real,
                "parcelas_maximas": self._parcelas_maximas() if real else 0, "gateway_configurado": real}

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
        if meio != "checkout":
            raise ErroNegocio("Use o checkout online para escolher Pix, cartão ou boleto.")
        p = self.banco.um("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
        if not p or p["cliente_id"] != ator.usuario_id:
            raise NaoEncontrado("Pedido não encontrado.")
        if p["status"] != "aguardando_pagamento":
            raise ErroNegocio("Este pedido não está aguardando pagamento.")
        if p["reserva_expira_em"] and p["reserva_expira_em"] <= self.agora():
            raise ErroNegocio("O tempo da reserva acabou. Faça o pedido de novo.")
        expira = p["reserva_expira_em"] or iso(self.agora_dt() + timedelta(minutes=30))
        agora = self.agora()
        with self.banco.transacao() as cx:
            aberto = self._uma(cx, "SELECT * FROM pagamentos WHERE pedido_id=? AND status IN ('pendente','em_analise') AND meio=? AND gateway='mercadopago' AND ambiente=? ORDER BY criado_em DESC LIMIT 1", (pedido_id, meio, c["ambiente"]))
            if aberto and (not aberto["expira_em"] or aberto["expira_em"] > agora):
                pid = aberto["id"]
                idem = aberto.get("idempotency_key") or ("pref-" + pid)
                if aberto["externo_id"] or aberto["qr_code"] or aberto["link_pagamento"]:
                    reutilizar = dict(aberto)
                else:
                    reutilizar = None
            else:
                pid = novo_id()
                reutilizar = None
                idem = "pref-" + pid
                cx.execute("""INSERT INTO pagamentos(id, pedido_id, empresa_id, meio, valor_centavos, status, expira_em, criado_em, atualizado_em,
                              gateway, ambiente, idempotency_key, moeda) VALUES (?,?,?,?,?,'pendente',?,?,?,?,?,?, 'BRL')""",
                           (pid, pedido_id, p["empresa_id"], meio, p["total_centavos"], expira, agora, agora, "mercadopago", c["ambiente"], idem))
        if reutilizar:
            return self._pagamento_publico(reutilizar)
        cliente = self.banco.um("SELECT nome, email FROM usuarios WHERE id=?", (ator.usuario_id,))
        valor = round(p["total_centavos"] / 100, 2)
        base = (base_url or "").rstrip("/")
        aviso = c["webhook_url"]
        empresa = (self.banco.um("SELECT nome FROM empresas WHERE id=?", (p["empresa_id"],)) or {}).get("nome", "Sobrou+")
        descricao = f"Sobrou+ pedido #{p['numero']} — {empresa}"[:120]
        try:
            if meio != "checkout":
                raise ErroNegocio("Use o checkout online para escolher Pix, cartão ou boleto.")
            corpo = {"items": [{"title": descricao, "quantity": 1, "unit_price": valor, "currency_id": "BRL"}],
                     "external_reference": pid, "metadata": {"payment_attempt_id": pid, "order_id": pedido_id},
                     "payer": {"email": cliente["email"], "name": cliente["nome"]},
                     "expires": True, "expiration_date_to": ler_data(expira).astimezone().isoformat(timespec="milliseconds"),
                     "payment_methods": {"installments": self._parcelas_maximas()}}
            if base.startswith("https://"):
                volta = f"{base}/#pedido/{pedido_id}"
                corpo["back_urls"] = {"success": volta, "pending": volta, "failure": volta}
                corpo["auto_return"] = "approved"
            corpo["notification_url"] = aviso
            r = self.rede("POST", f"{MP_API}/checkout/preferences", corpo, self._cab_mp(c, idem))
            link = r.get("sandbox_init_point") if c["ambiente"] == "sandbox" else r.get("init_point")
            if not link or not str(r.get("id") or ""):
                raise ErroNegocio("O Mercado Pago não retornou uma preferência de pagamento válida.")
            pag = {"externo_id": None, "qr_code": None, "qr_base64": None, "preference_id": str(r["id"]),
                   "link_pagamento": link, "expira_em": expira}
        except ErroRede as e:
            self.registrar_erro("mercadopago." + meio, "POST", e)
            raise ErroNegocio("O Mercado Pago não respondeu agora. Tente de novo em instantes.") from e
        agora = self.agora()
        self.banco.executar("""UPDATE pagamentos SET externo_id=?, preference_id=?, qr_code=?, qr_base64=?, link_pagamento=?, expira_em=?, resposta_gateway=?, atualizado_em=?
                               WHERE id=? AND status='pendente'""",
                            (pag.get("externo_id"), pag.get("preference_id"), pag.get("qr_code"), pag.get("qr_base64"), pag.get("link_pagamento"), pag["expira_em"],
                             json.dumps({"gateway_id": pag.get("externo_id") or pag.get("preference_id")}, ensure_ascii=False), agora, pid))
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
            for g in self.banco.todos("SELECT * FROM pagamentos WHERE pedido_id=? AND status IN ('pendente','em_analise') AND meio<>'teste'", (pedido_id,)):
                try:
                    if g["externo_id"]:
                        self.processar_pagamento_mp(g["externo_id"])
                    elif g.get("preference_id"):
                        # Reconciliação server-to-server; a volta do app nunca altera o status por si.
                        r = self.rede("GET", f"{MP_API}/v1/payments/search?external_reference={g['id']}&sort=date_created&criteria=desc",
                                      cabecalhos=self._cab_mp(self._mp()))
                        for res in r.get("results", [])[:5]:
                            self.processar_pagamento_mp(str(res["id"]))
                except ErroRede:
                    pass
        return self.obter_pedido(ator, pedido_id)

    def webhook_mercadopago(self, consulta: dict, corpo: dict, cabecalhos) -> dict:
        """Valida HMAC, registra o evento uma vez e consulta o recurso oficial."""
        c = self._mp()
        if not c:
            return {"ok": False, "motivo": "desligado"}
        dado_id = str(consulta.get("data.id") or (corpo.get("data") or {}).get("id") or consulta.get("id") or "")
        tipo = consulta.get("type") or consulta.get("topic") or corpo.get("type") or corpo.get("topic")
        if not dado_id or tipo != "payment":
            return {"ok": True, "ignorado": True}
        assinatura = cabecalhos.get("x-signature") or ""
        partes = dict(p.strip().split("=", 1) for p in assinatura.split(",") if "=" in p)
        request_id = cabecalhos.get("x-request-id") or ""
        manifesto = f"id:{dado_id.lower()};request-id:{request_id};ts:{partes.get('ts', '')};"
        esperado = hmac.new(c["webhook_secret"].encode(), manifesto.encode(), hashlib.sha256).hexdigest()
        if not request_id or not partes.get("ts") or not partes.get("v1") or not hmac.compare_digest(esperado, partes["v1"]):
            self.registrar_erro("webhook.mercadopago", "POST", ErroNegocio("assinatura inválida"))
            return {"ok": False, "motivo": "assinatura"}
        evento = f"{request_id}:{dado_id}"
        with self.banco.transacao() as cx:
            cur = cx.execute("INSERT OR IGNORE INTO eventos_pagamento(gateway, ambiente, evento_id, tipo, recebido_em) VALUES ('mercadopago',?,?,?,?)",
                             (c["ambiente"], evento, str(corpo.get("action") or tipo), self.agora()))
            if cur.rowcount == 0:
                return {"ok": True, "duplicado": True}
        try:
            resultado = self.processar_pagamento_mp(dado_id)
        except ErroRede as e:
            self.banco.executar("DELETE FROM eventos_pagamento WHERE gateway='mercadopago' AND ambiente=? AND evento_id=?", (c["ambiente"], evento))
            self.registrar_erro("webhook.mercadopago", "POST", e)
            return {"ok": False, "motivo": "consulta"}
        self.banco.executar("UPDATE eventos_pagamento SET processado_em=?, resultado=? WHERE gateway='mercadopago' AND ambiente=? AND evento_id=?",
                            (self.agora(), json.dumps(resultado, ensure_ascii=False)[:500], c["ambiente"], evento))
        return resultado

    def processar_pagamento_mp(self, externo_id: str) -> dict:
        c = self._mp()
        if not c:
            return {"ok": False, "motivo": "desligado"}
        r = self.rede("GET", f"{MP_API}/v1/payments/{externo_id}", cabecalhos=self._cab_mp(c))
        referencia = str(r.get("external_reference") or "")
        valor = round(float(r.get("transaction_amount") or 0) * 100)
        moeda = str(r.get("currency_id") or "")
        status_mp = str(r.get("status") or "")
        metodo_mp = str(r.get("payment_method_id") or r.get("payment_type_id") or "")
        resposta = {k: r.get(k) for k in ("id", "status", "status_detail", "payment_method_id", "payment_type_id",
                                            "transaction_amount", "currency_id", "installments", "date_approved")}
        pedido_id = None
        estornar = False
        with self.banco.transacao() as cx:
            g = self._uma(cx, "SELECT * FROM pagamentos WHERE id=? AND gateway='mercadopago' AND ambiente=?", (referencia, c["ambiente"]))
            if not g or (g["externo_id"] and g["externo_id"] != str(externo_id)):
                return {"ok": True, "ignorado": "tentativa de pagamento não reconhecida"}
            p = self._uma(cx, "SELECT * FROM pedidos WHERE id=?", (g["pedido_id"],))
            if not p:
                return {"ok": True, "ignorado": "pedido desconhecido"}
            pedido_id = p["id"]
            if g["status"] == "aprovado" and status_mp == "approved":
                return {"ok": True, "ja_processado": "aprovado"}
            agora = self.agora()
            if moeda != "BRL" or valor != int(g["valor_centavos"]):
                cx.execute("UPDATE pagamentos SET status='divergente', externo_id=?, moeda=?, resposta_gateway=?, detalhe_status=?, atualizado_em=? WHERE id=?",
                           (str(externo_id), moeda, json.dumps(resposta, ensure_ascii=False), r.get("status_detail"), agora, g["id"]))
                self.avisar(f"Pagamento do pedido #{p['numero']} com valor/moeda divergente. Conferir.", papel_alvo="plataforma", conn=cx)
                return {"ok": False, "status": "divergente"}
            mapeamento = {"approved": "aprovado", "pending": "pendente", "in_process": "em_analise",
                          "rejected": "recusado", "cancelled": "cancelado", "refunded": "estornado", "charged_back": "estornado"}
            status_local = mapeamento.get(status_mp)
            if not status_local:
                return {"ok": False, "motivo": "status_gateway_desconhecido"}
            if status_local == "aprovado":
                if p["status"] != "aguardando_pagamento":
                    cx.execute("UPDATE pagamentos SET status='aprovado', externo_id=?, resposta_gateway=?, detalhe_status=?, atualizado_em=? WHERE id=?",
                               (str(externo_id), json.dumps(resposta, ensure_ascii=False), r.get("status_detail"), agora, g["id"]))
                    estornar = True
                else:
                    cx.execute("UPDATE pagamentos SET status='aprovado', externo_id=?, valor_centavos=?, parcelas=?, resposta_gateway=?, detalhe_status=?, aprovado_em=?, atualizado_em=? WHERE id=?",
                               (str(externo_id), valor, int(r.get("installments") or 1), json.dumps(resposta, ensure_ascii=False),
                                r.get("status_detail"), r.get("date_approved") or agora, agora, g["id"]))
                    if metodo_mp in ("pix", "ticket", "bolbradesco", "pec", "debit_card", "credit_card"):
                        meio_real = "boleto" if metodo_mp in ("ticket", "bolbradesco", "pec") else ("pix" if metodo_mp == "pix" else "cartao")
                        cx.execute("UPDATE pagamentos SET meio=? WHERE id=?", (meio_real, g["id"]))
                    self._efetivar_pagamento(cx, p, None, f"pagamento aprovado pelo Mercado Pago ({metodo_mp})")
            else:
                cx.execute("""UPDATE pagamentos SET status=?, externo_id=?, parcelas=?, resposta_gateway=?, detalhe_status=?, atualizado_em=?,
                           estorno_em=CASE WHEN ?='estornado' THEN ? ELSE estorno_em END,
                           cancelado_em=CASE WHEN ?='cancelado' THEN ? ELSE cancelado_em END WHERE id=?""",
                           (status_local, str(externo_id), int(r.get("installments") or 1), json.dumps(resposta, ensure_ascii=False),
                            r.get("status_detail"), agora, status_local, agora, status_local, agora, g["id"]))
        if estornar:
            self.estornar_externo(g["id"])
            return {"ok": True, "status": "estorno solicitado (pedido não aguardava pagamento)"}
        if status_local == "aprovado":
            self.auditar(None, "pagamento.aprovado", pedido_id, {"meio": metodo_mp, "valor": valor}, empresa_id=p["empresa_id"])
        return {"ok": True, "status": status_local}

    def estornar_externo(self, pagamento_id: str) -> bool:
        g = self.banco.um("SELECT * FROM pagamentos WHERE id=?", (pagamento_id,))
        c = self._mp()
        if not g or not g["externo_id"] or not c:
            return False
        try:
            r = self.rede("POST", f"{MP_API}/v1/payments/{g['externo_id']}/refunds", {}, self._cab_mp(c, f"estorno-{pagamento_id}"))
        except ErroRede as e:
            self.banco.executar("UPDATE pagamentos SET status='estorno_pendente', atualizado_em=? WHERE id=?", (self.agora(), pagamento_id))
            self.registrar_erro("mercadopago.estorno", "POST", e)
            self.avisar("Estorno no Mercado Pago falhou — refazer pelo painel do Mercado Pago.", papel_alvo="plataforma")
            return False
        resumo = {k: r.get(k) for k in ("id", "payment_id", "status", "amount", "date_created")}
        self.banco.executar("UPDATE pagamentos SET status='estorno_pendente', resposta_gateway=?, atualizado_em=? WHERE id=?",
                            (json.dumps(resumo, ensure_ascii=False), self.agora(), pagamento_id))
        return True

    def listar_pagamentos(self, ator: Ator, empresa_id: str | None = None) -> list[dict]:
        ator.exigir("financeiro", "ver")
        where, args = [], []
        if ator.plataforma:
            if empresa_id:
                where.append("pg.empresa_id=?")
                args.append(empresa_id)
        else:
            where.append("pg.empresa_id=?")
            args.append(ator.empresa_alvo(empresa_id))
        sql_where = " WHERE " + " AND ".join(where) if where else ""
        return self.banco.todos("""SELECT pg.id, pg.pedido_id, pg.empresa_id, pg.gateway, pg.ambiente, pg.meio,
            pg.valor_centavos, pg.moeda, pg.status, pg.detalhe_status, pg.externo_id, pg.preference_id,
            pg.parcelas, pg.resposta_gateway, pg.criado_em, pg.atualizado_em, pg.aprovado_em, pg.cancelado_em, pg.estorno_em,
            pd.numero AS pedido_numero, pd.status AS pedido_status, u.nome AS cliente, e.nome AS empresa
            FROM pagamentos pg JOIN pedidos pd ON pd.id=pg.pedido_id
            JOIN usuarios u ON u.id=pd.cliente_id JOIN empresas e ON e.id=pg.empresa_id""" + sql_where + " ORDER BY pg.criado_em DESC LIMIT 500", args)

    def cancelar_externo(self, pagamento_id: str) -> bool:
        g = self.banco.um("SELECT * FROM pagamentos WHERE id=?", (pagamento_id,))
        c = self._mp()
        if not g or not g.get("externo_id") or not c or g.get("gateway") != "mercadopago" or g.get("ambiente") != c["ambiente"]:
            return False
        try:
            self.rede("PUT", f"{MP_API}/v1/payments/{g['externo_id']}", {"status": "cancelled"}, self._cab_mp(c, f"cancel-{g['id']}"))
            self.processar_pagamento_mp(g["externo_id"])
        except ErroRede as e:
            self.registrar_erro("mercadopago.cancelamento", "PUT", e)
            return False
        atualizado = self.banco.um("SELECT status FROM pagamentos WHERE id=?", (pagamento_id,))
        return bool(atualizado and atualizado["status"] == "cancelado")

    def cancelar_pagamento(self, ator: Ator, pagamento_id: str) -> dict:
        g = self.banco.um("SELECT * FROM pagamentos WHERE id=?", (pagamento_id,))
        if not g:
            raise NaoEncontrado("Pagamento não encontrado.")
        pedido = self.banco.um("SELECT cliente_id FROM pedidos WHERE id=?", (g["pedido_id"],))
        if not (ator.plataforma or (ator.papel == "cliente" and pedido and pedido["cliente_id"] == ator.usuario_id)):
            raise NaoEncontrado("Pagamento não encontrado.")
        c = self._mp()
        if not c or g.get("gateway") != "mercadopago" or g.get("ambiente") != c["ambiente"]:
            raise ErroNegocio("Gateway deste pagamento indisponível.")
        if g["status"] not in ("pendente", "em_analise") or not g.get("externo_id"):
            raise ErroNegocio("Só pagamentos pendentes com ID no gateway podem ser cancelados.")
        if not self.cancelar_externo(pagamento_id):
            raise ErroNegocio("O gateway não confirmou o cancelamento. Consulte o status antes de tentar novamente.")
        return self.banco.um("SELECT id, status, cancelado_em, atualizado_em FROM pagamentos WHERE id=?", (pagamento_id,))

    def estornar_pagamento(self, ator: Ator, pagamento_id: str) -> dict:
        if not ator.plataforma:
            raise NaoEncontrado("Pagamento não encontrado.")
        g = self.banco.um("SELECT * FROM pagamentos WHERE id=?", (pagamento_id,))
        c = self._mp()
        if not g or g["status"] != "aprovado" or not g.get("externo_id") or not c or g.get("ambiente") != c["ambiente"]:
            raise ErroNegocio("Não há pagamento aprovado disponível para estorno neste gateway.")
        try:
            r = self.rede("POST", f"{MP_API}/v1/payments/{g['externo_id']}/refunds", {}, self._cab_mp(c, f"refund-{g['id']}"))
        except ErroRede as e:
            self.registrar_erro("mercadopago.estorno", "POST", e)
            raise ErroNegocio("O gateway não confirmou o pedido de estorno.") from e
        resumo = {k: r.get(k) for k in ("id", "payment_id", "status", "amount", "date_created")}
        self.banco.executar("UPDATE pagamentos SET status='estorno_pendente', resposta_gateway=?, atualizado_em=? WHERE id=?",
                            (json.dumps(resumo, ensure_ascii=False), self.agora(), pagamento_id))
        return self.banco.um("SELECT id, status, externo_id, resposta_gateway, atualizado_em FROM pagamentos WHERE id=?", (pagamento_id,))

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
