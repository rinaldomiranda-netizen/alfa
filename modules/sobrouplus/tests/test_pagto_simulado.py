"""Pagamento SIMULADO (cartão/Pix de mentira) só para os sócios liberados em teste."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_fluxos import Base  # noqa: E402

from sobrou.nucleo import ErroNegocio  # noqa: E402


class TestPagtoSimulado(Base):
    def _socio(self):
        r = self.p.criar_testador(self.adm, {"nome": "Paulo Sócio"})
        ators = {}
        for x in r["links"]:
            s = self.p.aceitar_convite(x["caminho"].split("c=")[1], "senhaBoa123", True)
            ators[x["app"]] = self.p.ator_da_sessao(s["token"])
        return r["testador"]["id"], ators

    def _pedido_na_loja_teste(self, ators):
        uni = self.p.banco.um("SELECT * FROM unidades WHERE empresa_id=?", (self.p.mundo_de_teste()["empresa_id"],))
        o = self.oferta(ators["loja"], uni)
        return self.p.criar_pedido(ators["cliente"], {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})

    def test_socio_paga_de_mentira_cartao_e_pix(self):
        tid, a = self._socio()
        self.assertTrue(self.p.meios_pagamento(a["cliente"])["simulado"])
        for meio in ("cartao_simulado", "pix_simulado"):
            ped = self._pedido_na_loja_teste(a)
            r = self.p.pagar(a["cliente"], ped["id"], meio)
            self.assertEqual(r["status"], "pago")
            g = self.p.banco.um("SELECT * FROM pagamentos WHERE pedido_id=? AND status='aprovado'", (ped["id"],))
            self.assertTrue(g["referencia_externa"].startswith("SIMULADO-"))
            self.assertEqual(g["meio"], "teste")

    def test_quem_nao_e_socio_nao_simula(self):
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        self.assertFalse(self.p.meios_pagamento(self.cli)["simulado"])
        with self.assertRaises(ErroNegocio):
            self.p.pagar(self.cli, ped["id"], "cartao_simulado")
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "aguardando_pagamento")

    def test_socio_desligado_nao_simula(self):
        tid, a = self._socio()
        ped = self._pedido_na_loja_teste(a)
        self.p.ligar_testador(self.adm, tid, False)
        self.assertFalse(self.p.meios_pagamento(a["cliente"])["simulado"])
        with self.assertRaises(ErroNegocio):
            self.p.pagar(a["cliente"], ped["id"], "pix_simulado")

    def test_socio_nao_simula_em_loja_de_verdade(self):
        tid, a = self._socio()
        o = self.oferta()  # loja real do teste base (não é demonstração)
        ped = self.p.criar_pedido(a["cliente"], {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        with self.assertRaises(ErroNegocio):
            self.p.pagar(a["cliente"], ped["id"], "cartao_simulado")


if __name__ == "__main__":
    unittest.main()
