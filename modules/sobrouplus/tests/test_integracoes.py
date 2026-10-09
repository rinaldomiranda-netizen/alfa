"""Integrações prontas para ativar: Mercado Pago (Pix/cartão + webhook + estorno), WhatsApp e rotas pelas ruas.
Nenhuma chamada sai para a internet: a rede é trocada por uma falsa que imita as respostas oficiais."""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_fluxos import Base  # noqa: E402

from sobrou import mapas  # noqa: E402
from sobrou.nucleo import ErroNegocio  # noqa: E402
from sobrou.rede import ErroRede  # noqa: E402


class RedeFalsa:
    def __init__(self):
        self.chamadas = []
        self.pagamentos = {}
        self.preferencias = {}
        self.distancia_m = 3200
        self.falhar_pix_uma_vez = False
        self.falhar_preferencia_uma_vez = False

    def __call__(self, metodo, url, corpo=None, cabecalhos=None, tempo=12):
        self.chamadas.append((metodo, url, corpo, cabecalhos))
        if "router" in url or "/route/v1/" in url:
            return {"code": "Ok", "routes": [{"distance": self.distancia_m, "duration": 540,
                                              "geometry": {"coordinates": [[-37.07, -10.91], [-37.06, -10.92]]}}]}
        if url.endswith("/v1/payments") and metodo == "POST":
            if self.falhar_pix_uma_vez:
                self.falhar_pix_uma_vez = False
                raise ErroRede("timeout de teste", 504, {})
            pid = str(9000 + len(self.pagamentos))
            self.pagamentos[pid] = {"id": int(pid), "status": "pending", "external_reference": corpo["external_reference"],
                                    "transaction_amount": corpo["transaction_amount"]}
            return {"id": int(pid), "status": "pending",
                    "point_of_interaction": {"transaction_data": {"qr_code": "00020126PIXCOPIAECOLA", "qr_code_base64": "iVBORw0KGgo=", "ticket_url": "https://mp/ticket"}}}
        if "/checkout/preferences" in url:
            if self.falhar_preferencia_uma_vez:
                self.falhar_preferencia_uma_vez = False
                raise ErroRede("timeout de teste", 504, {})
            pid = "pref" + str(len(self.preferencias) + 1)
            self.preferencias[pid] = {"external_reference": corpo["external_reference"], "amount": corpo["items"][0]["unit_price"]}
            return {"id": pid, "init_point": "https://mp/checkout/" + pid, "sandbox_init_point": "https://sandbox.mp/checkout/" + pid}
        if "/refunds" in url:
            pid = url.split("/v1/payments/")[1].split("/")[0]
            self.pagamentos[pid]["status"] = "refunded"
            return {"id": 1, "status": "approved"}
        if "/v1/payments/" in url and metodo == "PUT":
            pid = url.rsplit("/", 1)[1]
            self.pagamentos[pid]["status"] = "cancelled"
            return {**self.pagamentos[pid]}
        if "/v1/payments/search" in url and metodo == "GET":
            from urllib.parse import parse_qs, urlparse
            ref = parse_qs(urlparse(url).query).get("external_reference", [""])[0]
            return {"results": [p for p in self.pagamentos.values() if p.get("external_reference") == ref]}
        if "/v1/payments/" in url and metodo == "GET":
            pid = url.rsplit("/", 1)[1]
            if pid not in self.pagamentos:
                raise ErroRede("HTTP 404", 404, {})
            return self.pagamentos[pid]
        if "/messages" in url:
            return {"messages": [{"id": "wamid.1"}]}
        raise ErroRede("sem rota falsa para " + url)


class BaseInt(Base):
    def setUp(self):
        for k in ("SOBROU_PAYMENT_PROVIDER", "SOBROU_PAYMENT_ENV", "SOBROU_PAYMENT_WEBHOOK_URL",
                  "MERCADOPAGO_PUBLIC_KEY_SANDBOX", "MERCADOPAGO_ACCESS_TOKEN_SANDBOX", "MERCADOPAGO_WEBHOOK_SECRET_SANDBOX"):
            os.environ.pop(k, None)
        super().setUp()
        mapas._rotas_memoria.clear()
        self.rede = RedeFalsa()
        self.p.rede = self.rede

    def tearDown(self):
        for k in ("SOBROU_PAYMENT_PROVIDER", "SOBROU_PAYMENT_ENV", "SOBROU_PAYMENT_WEBHOOK_URL",
                  "MERCADOPAGO_PUBLIC_KEY_SANDBOX", "MERCADOPAGO_ACCESS_TOKEN_SANDBOX", "MERCADOPAGO_WEBHOOK_SECRET_SANDBOX"):
            os.environ.pop(k, None)
        super().tearDown()

    def ligar_mp(self, segredo="assinatura-de-teste"):
        os.environ.update({"SOBROU_PAYMENT_PROVIDER": "mercadopago", "SOBROU_PAYMENT_ENV": "sandbox",
            "SOBROU_PAYMENT_WEBHOOK_URL": "https://sobrou.exemplo/api/webhooks/mercadopago",
            "MERCADOPAGO_PUBLIC_KEY_SANDBOX": "TEST-public-key",
            "MERCADOPAGO_ACCESS_TOKEN_SANDBOX": "TEST-access-token",
            "MERCADOPAGO_WEBHOOK_SECRET_SANDBOX": segredo})

    def abrir_checkout(self, pedido):
        return self.p.pagar(self.cli, pedido["id"], "checkout", "https://sobrou.exemplo")

    def criar_pagamento_gateway(self, iniciado, status="pending", amount=None, method="pix"):
        g = iniciado["pagamento_iniciado"]
        pid = str(9000 + len(self.rede.pagamentos))
        self.rede.pagamentos[pid] = {"id": int(pid), "status": status, "external_reference": g["id"],
            "transaction_amount": (g["valor_centavos"] / 100) if amount is None else amount, "currency_id": "BRL",
            "payment_method_id": method, "installments": 1, "date_approved": "2026-10-04T12:00:00Z" if status == "approved" else None}
        return pid


class TestMercadoPago(BaseInt):
    def _pedido(self):
        o = self.oferta()
        return self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})

    def test_sem_credenciais_pedido_nao_pode_ser_pago(self):
        self.assertEqual(self.p.meios_pagamento()["gateway_configurado"], False)
        self.assertFalse(self.p.meios_pagamento()["teste"])
        ped = self._pedido()
        with self.assertRaises(ErroNegocio):
            self.p.pagar(self.cli, ped["id"], "checkout")
        with self.assertRaises(ErroNegocio):
            self.p.__class__.pagar(self.p, self.cli, ped["id"], "teste")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "aguardando_pagamento")
        self.assertEqual(self.p.banco.um("SELECT COUNT(*) AS n FROM pagamentos WHERE pedido_id=?", (ped["id"],))["n"], 0)

    def test_checkout_webhook_assinado_aprova_uma_vez(self):
        self.ligar_mp()
        self.assertTrue(self.p.meios_pagamento()["gateway_configurado"])
        telas = self.p.integracoes_publicas(self.adm)["mercadopago"]
        self.assertNotIn("access_token", telas)
        self.assertTrue(telas["access_token_configurado"])
        ped = self._pedido()
        r = self.abrir_checkout(ped)
        tentativa = r["pagamento_iniciado"]["id"]
        self.assertTrue(r["pagamento_iniciado"]["link_pagamento"].startswith("https://sandbox.mp/"))
        corpo_mp = [c for c in self.rede.chamadas if "/checkout/preferences" in c[1]][0][2]
        self.assertEqual(corpo_mp["external_reference"], tentativa)
        self.assertEqual(corpo_mp["notification_url"], "https://sobrou.exemplo/api/webhooks/mercadopago")
        ext = self.criar_pagamento_gateway(r)
        self.assertEqual(self.p.processar_pagamento_mp(ext)["status"], "pendente")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "aguardando_pagamento")
        self.rede.pagamentos[ext]["status"] = "approved"
        self.assertEqual(self.p.processar_pagamento_mp(ext)["status"], "aprovado")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "pago")
        self.assertEqual(self.p.obter_oferta(self.a, self.p.banco.um("SELECT oferta_id FROM pedido_itens WHERE pedido_id=?", (ped["id"],))["oferta_id"])["vendida"], 1)
        self.assertTrue(self.p.conciliacao(self.adm)["fecha"])
        self.assertEqual(self.p.processar_pagamento_mp(ext).get("ja_processado"), "aprovado")

    def test_webhook_exige_assinatura_e_deduplica(self):
        self.ligar_mp()
        ped = self._pedido()
        r = self.abrir_checkout(ped)
        ext = self.criar_pagamento_gateway(r, status="approved")
        self.assertFalse(self.p.webhook_mercadopago({"data.id": ext, "type": "payment"}, {}, {})["ok"])
        ts, req = "1700000000", "req-1"
        def cabecalho(request_id):
            v1 = hmac.new(b"assinatura-de-teste", f"id:{ext};request-id:{request_id};ts:{ts};".encode(), hashlib.sha256).hexdigest()
            return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}
        self.assertEqual(self.p.webhook_mercadopago({"data.id": ext, "type": "payment"}, {"action": "payment.updated"}, cabecalho(req))["status"], "aprovado")
        self.assertEqual(self.p.webhook_mercadopago({"data.id": ext, "type": "payment"}, {"action": "payment.updated"}, cabecalho(req)), {"ok": True, "duplicado": True})
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "pago")

    def test_tentativa_de_checkout_reusa_idempotencia(self):
        self.ligar_mp()
        ped = self._pedido()
        self.rede.falhar_preferencia_uma_vez = True
        with self.assertRaises(ErroNegocio):
            self.abrir_checkout(ped)
        primeira = [c for c in self.rede.chamadas if "/checkout/preferences" in c[1]][-1][3]["X-Idempotency-Key"]
        id_tentativa = self.p.banco.um("SELECT id FROM pagamentos WHERE pedido_id=? AND status='pendente'", (ped["id"],))["id"]
        r = self.abrir_checkout(ped)
        segunda = [c for c in self.rede.chamadas if "/checkout/preferences" in c[1]][-1][3]["X-Idempotency-Key"]
        self.assertEqual(primeira, segunda)
        self.assertEqual(r["pagamento_iniciado"]["id"], id_tentativa)
        self.assertEqual(self.p.banco.um("SELECT COUNT(*) AS n FROM pagamentos WHERE pedido_id=? AND status='pendente'", (ped["id"],))["n"], 1)

    def test_valor_ou_moeda_divergente_nao_libera(self):
        self.ligar_mp()
        ped = self._pedido()
        r = self.abrir_checkout(ped)
        ext = self.criar_pagamento_gateway(r, status="approved", amount=1.0)
        result = self.p.processar_pagamento_mp(ext)
        self.assertEqual(result["status"], "divergente")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "aguardando_pagamento")

    def test_cliente_cancela_cobranca_pendente_no_gateway(self):
        self.ligar_mp()
        ped = self._pedido()
        r = self.abrir_checkout(ped)
        ext = self.criar_pagamento_gateway(r)
        self.p.processar_pagamento_mp(ext)
        pid = r["pagamento_iniciado"]["id"]
        cancelado = self.p.cancelar_pagamento(self.cli, pid)
        self.assertEqual(cancelado["status"], "cancelado")
        self.assertEqual(self.rede.pagamentos[ext]["status"], "cancelled")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "aguardando_pagamento")

    def test_aprovacao_depois_da_reserva_solicita_estorno(self):
        self.ligar_mp()
        ped = self._pedido()
        r = self.abrir_checkout(ped)
        ext = self.criar_pagamento_gateway(r, status="approved")
        self.rel.andar(minutes=20)
        self.p.rotina()
        self.p.processar_pagamento_mp(ext)
        g = self.p.banco.um("SELECT status FROM pagamentos WHERE pedido_id=?", (ped["id"],))
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "expirado")
        self.assertEqual(g["status"], "estorno_pendente")
        self.assertEqual(self.rede.pagamentos[ext]["status"], "refunded")

    def test_cancelamento_pedido_solicita_estorno_e_checkout_link(self):
        self.ligar_mp()
        ped = self._pedido()
        r = self.abrir_checkout(ped)
        self.assertIn("sandbox.mp", r["pagamento_iniciado"]["link_pagamento"])
        ext = self.criar_pagamento_gateway(r, status="approved")
        self.p.verificar_pagamento(self.cli, ped["id"])
        self.p.cancelar_pedido(self.cli, ped["id"])
        self.assertEqual(self.rede.pagamentos[ext]["status"], "refunded")
        self.assertEqual(self.p.banco.um("SELECT status FROM pagamentos WHERE pedido_id=?", (ped["id"],))["status"], "estorno_pendente")


class TestWhatsApp(BaseInt):
    def test_aviso_vai_para_o_celular(self):
        self.p.banco.executar("UPDATE usuarios SET telefone='(79) 99999-1234' WHERE id=?", (self.cli.usuario_id,))
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        self.p.pagar(self.cli, ped["id"])
        self.p.avancar_pedido(self.a, ped["id"], "receber")
        self.assertEqual(self.p.banco.um("SELECT COUNT(*) AS n FROM fila_mensagens WHERE canal='whatsapp'")["n"], 0)  # desligado: nada na fila
        self.p.salvar_integracao(self.adm, "whatsapp", {"ligado": True, "token": "EAAtokenwhats", "phone_number_id": "1234567"})
        self.p.avancar_pedido(self.a, ped["id"], "preparar")
        self.p.avancar_pedido(self.a, ped["id"], "pronto")
        self.assertGreater(self.p.rotina()["whatsapp"], 0)
        envio = [c for c in self.rede.chamadas if "/messages" in c[1]][0]
        self.assertEqual(envio[2]["to"], "5579999991234")
        self.assertIn("Pronto", envio[2]["text"]["body"])


class TestMapas(BaseInt):
    def test_distancia_pelas_ruas_e_raio(self):
        o = self.oferta()
        cot = self.p.cotar(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}], "modo": "entrega", "endereco": "Rua X", "lat": -10.92, "lng": -37.06})
        self.assertEqual((cot["distancia_km"], cot["distancia_fonte"], cot["tempo_min"]), (3.2, "ruas", 9))
        mapas._rotas_memoria.clear()
        self.rede.distancia_m = 15000  # pelas ruas passa do raio de 10 km da loja
        with self.assertRaises(ErroNegocio):
            self.p.cotar(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}], "modo": "entrega", "endereco": "Rua X", "lat": -10.92, "lng": -37.06})

    def test_sem_servico_usa_estimativa(self):
        self.p.rede = lambda *a, **k: (_ for _ in ()).throw(ErroRede("fora do ar"))
        r = self.p.rota(-10.9111, -37.0717, -10.92, -37.06)
        self.assertEqual(r["fonte"], "estimada")


if __name__ == "__main__":
    unittest.main()
