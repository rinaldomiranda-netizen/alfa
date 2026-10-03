"""Integrações prontas para ativar: Mercado Pago (Pix/cartão + webhook + estorno), WhatsApp e rotas pelas ruas.
Nenhuma chamada sai para a internet: a rede é trocada por uma falsa que imita as respostas oficiais."""
from __future__ import annotations

import hashlib
import hmac
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
        self.distancia_m = 3200

    def __call__(self, metodo, url, corpo=None, cabecalhos=None, tempo=12):
        self.chamadas.append((metodo, url, corpo, cabecalhos))
        if "router" in url or "/route/v1/" in url:
            return {"code": "Ok", "routes": [{"distance": self.distancia_m, "duration": 540,
                                              "geometry": {"coordinates": [[-37.07, -10.91], [-37.06, -10.92]]}}]}
        if url.endswith("/v1/payments") and metodo == "POST":
            pid = str(9000 + len(self.pagamentos))
            self.pagamentos[pid] = {"id": int(pid), "status": "pending", "external_reference": corpo["external_reference"],
                                    "transaction_amount": corpo["transaction_amount"]}
            return {"id": int(pid), "status": "pending",
                    "point_of_interaction": {"transaction_data": {"qr_code": "00020126PIXCOPIAECOLA", "qr_code_base64": "iVBORw0KGgo=", "ticket_url": "https://mp/ticket"}}}
        if "/checkout/preferences" in url:
            return {"id": "pref1", "init_point": "https://mp/checkout/pref1", "sandbox_init_point": "https://sandbox.mp/checkout/pref1"}
        if "/refunds" in url:
            pid = url.split("/v1/payments/")[1].split("/")[0]
            self.pagamentos[pid]["status"] = "refunded"
            return {"id": 1, "status": "approved"}
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
        super().setUp()
        mapas._rotas_memoria.clear()
        self.rede = RedeFalsa()
        self.p.rede = self.rede

    def ligar_mp(self, segredo=None):
        self.p.salvar_integracao(self.adm, "mercadopago", {"ligado": True, "access_token": "TEST-123-abc-token", "webhook_secret": segredo or ""})


class TestMercadoPago(BaseInt):
    def test_desligado_so_teste(self):
        self.assertEqual(self.p.meios_pagamento(), {"teste": True, "pix": False, "cartao": False})
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        with self.assertRaises(ErroNegocio):
            self.p.pagar(self.cli, ped["id"], "pix")

    def test_pix_webhook_assinado_libera_pedido(self):
        self.ligar_mp("segredo-webhook")
        self.assertEqual(self.p.meios_pagamento(), {"teste": False, "pix": True, "cartao": True})
        tela = self.p.integracoes_publicas(self.adm)["mercadopago"]
        self.assertEqual(tela["access_token"], "••••oken")  # segredo nunca volta inteiro
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 2}]})
        with self.assertRaises(ErroNegocio):
            self.p.pagar(self.cli, ped["id"], "teste")  # com pagamento real ligado, teste fica desligado
        r = self.p.pagar(self.cli, ped["id"], "pix", "https://sobrou.exemplo")
        self.assertEqual(r["pagamento_iniciado"]["qr_code"], "00020126PIXCOPIAECOLA")
        corpo_mp = [c for c in self.rede.chamadas if c[1].endswith("/v1/payments")][0][2]
        self.assertEqual(corpo_mp["transaction_amount"], 25.0)
        self.assertEqual(corpo_mp["notification_url"], "https://sobrou.exemplo/api/webhooks/mercadopago")
        externo = r["pagamento_iniciado"] and list(self.rede.pagamentos)[0]
        # aviso falso (sem assinatura) é recusado
        self.assertFalse(self.p.webhook_mercadopago({"data.id": externo, "type": "payment"}, {}, {})["ok"])
        # aviso verdadeiro, mas o MP ainda diz "pendente": não libera
        ts, req = "1700000000", "req-1"
        v1 = hmac.new(b"segredo-webhook", f"id:{externo};request-id:{req};ts:{ts};".encode(), hashlib.sha256).hexdigest()
        cab = {"x-signature": f"ts={ts},v1={v1}", "x-request-id": req}
        self.assertEqual(self.p.webhook_mercadopago({"data.id": externo, "type": "payment"}, {}, cab)["status"], "pendente")
        self.rede.pagamentos[externo]["status"] = "approved"
        self.assertEqual(self.p.webhook_mercadopago({"data.id": externo, "type": "payment"}, {}, cab)["status"], "aprovado")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "pago")
        self.assertEqual(self.p.obter_oferta(self.a, o["id"])["vendida"], 2)
        # aviso repetido não paga duas vezes
        self.assertIn("ja_processado", self.p.webhook_mercadopago({"data.id": externo, "type": "payment"}, {}, cab))
        self.assertTrue(self.p.conciliacao(self.adm)["fecha"])

    def test_valor_diferente_nao_libera(self):
        self.ligar_mp()
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        self.p.pagar(self.cli, ped["id"], "pix")
        ext = list(self.rede.pagamentos)[0]
        self.rede.pagamentos[ext].update(status="approved", transaction_amount=1.0)
        self.p.processar_pagamento_mp(ext)
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "aguardando_pagamento")

    def test_pagou_depois_de_vencer_estorna(self):
        self.ligar_mp()
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        self.p.pagar(self.cli, ped["id"], "pix")
        ext = list(self.rede.pagamentos)[0]
        self.rel.andar(minutes=20)
        self.p.rotina()
        self.rede.pagamentos[ext]["status"] = "approved"
        self.p.processar_pagamento_mp(ext)
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "expirado")
        self.assertEqual(self.rede.pagamentos[ext]["status"], "refunded")

    def test_cancelamento_estorna_no_mp_e_cartao_gera_link(self):
        self.ligar_mp()
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        link = self.p.pagar(self.cli, ped["id"], "cartao", "https://sobrou.exemplo")["pagamento_iniciado"]["link_pagamento"]
        self.assertIn("sandbox.mp", link)  # credencial TEST- usa o checkout de teste
        self.p.pagar(self.cli, ped["id"], "pix")
        ext = list(self.rede.pagamentos)[0]
        self.rede.pagamentos[ext]["status"] = "approved"
        self.p.verificar_pagamento(self.cli, ped["id"])
        self.p.cancelar_pedido(self.cli, ped["id"])
        self.assertEqual(self.rede.pagamentos[ext]["status"], "refunded")
        self.assertTrue(self.p.conciliacao(self.adm)["fecha"])


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
