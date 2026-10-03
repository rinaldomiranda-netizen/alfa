"""Testes ponta a ponta do Sobrou+ (critério de pronto, combinado §28). Rodar: python -m unittest discover tests"""
from __future__ import annotations

import base64
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sobrou.nucleo import ErroNegocio, NaoEncontrado, SemPermissao  # noqa: E402
from sobrou.plataforma import Plataforma  # noqa: E402

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 200).decode()


def _sem_internet(*a, **k):
    from sobrou.rede import ErroRede
    raise ErroRede("testes não usam internet")


class Relogio:
    def __init__(self):
        self.t = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)  # 17:00 em Brasília

    def __call__(self):
        return self.t

    def andar(self, **kw):
        self.t += timedelta(**kw)


def local(rel: Relogio, **kw) -> str:
    return (rel.t + timedelta(**kw)).isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.rel = Relogio()
        self.p = Plataforma(self.pasta, self.rel)
        self.p.rede = _sem_internet
        self.p.garantir_admin_sobrou("admin@sobrou.test")
        self.adm = self.p.ator_da_sessao(self.p.entrar("admin@sobrou.test", "1234")["token"])
        self.emp_a = self.p.criar_empresa(self.adm, {"nome": "Restaurante A", "tipo": "restaurante"})
        self.emp_b = self.p.criar_empresa(self.adm, {"nome": "Padaria B", "tipo": "padaria"})
        self.p.criar_usuario(self.adm, {"nome": "Ana", "email": "ana@a.test", "papel": "admin_empresa", "empresa_id": self.emp_a["id"]})
        self.p.criar_usuario(self.adm, {"nome": "Beto", "email": "beto@b.test", "papel": "admin_empresa", "empresa_id": self.emp_b["id"]})
        self.a = self.p.ator_da_sessao(self.p.entrar("ana@a.test", "1234")["token"])
        self.b = self.p.ator_da_sessao(self.p.entrar("beto@b.test", "1234")["token"])
        self.uni_a = self.p.salvar_unidade(self.a, {"nome": "Centro", "lat": -10.9111, "lng": -37.0717, "instrucoes_retirada": "Balcão"})
        self.uni_b = self.p.salvar_unidade(self.b, {"nome": "Bairro", "lat": -10.95, "lng": -37.05})
        self.p.editar_empresa(self.a, None, {"config": {"aceita_entrega": True, "taxa_entrega_centavos": 600, "raio_entrega_km": 10}})
        self.cli = self.p.ator_da_sessao(self.p.cadastrar_cliente({"nome": "Cris", "email": "cris@c.test", "senha": "senha123ok", "aceite_termos": True})["token"])

    def tearDown(self):
        shutil.rmtree(self.pasta, ignore_errors=True)

    def oferta(self, ator=None, uni=None, **kw):
        ator, uni = ator or self.a, uni or self.uni_a
        foto = self.p.enviar_foto(ator, {"imagem": JPEG})
        dados = {"unidade_id": uni["id"], "nome": "Marmita Executiva", "categoria": "refeicoes", "preco_normal": "24,90",
                 "preco": "12,50", "quantidade_total": 8, "inicio": local(self.rel, minutes=-10), "fim": local(self.rel, hours=3),
                 "retirada_inicio": local(self.rel, hours=1, minutes=30), "retirada_fim": local(self.rel, hours=3),
                 "permite_entrega": True, "foto_id": foto["id"], "peso_kg_unidade": 0.6}
        dados.update(kw)
        o = self.p.salvar_oferta(ator, dados)
        return self.p.mudar_status_oferta(ator, o["id"], "ativa")


class TestCliente(Base):
    def test_oferta_compra_pagamento_pedido_retirada(self):
        o = self.oferta()
        self.assertEqual(o["desconto_pct"], 50)
        self.assertEqual(len(self.p.vitrine({})), 1)
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 2}], "modo": "retirada"})
        self.assertEqual(ped["status"], "aguardando_pagamento")
        self.assertEqual(ped["total_centavos"], 2500)
        self.assertEqual(self.p.obter_oferta(self.a, o["id"])["reservada"], 2)
        ped = self.p.pagar(self.cli, ped["id"])
        self.assertEqual(ped["status"], "pago")
        oo = self.p.obter_oferta(self.a, o["id"])
        self.assertEqual((oo["reservada"], oo["vendida"], oo["disponivel"]), (0, 2, 6))
        # EMPRESA: recebe → prepara → pronto
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        visto_loja = self.p.obter_pedido(self.a, ped["id"])
        self.assertEqual(visto_loja["status"], "aguardando_retirada")
        self.assertNotIn("codigo_retirada", visto_loja)  # loja não vê o PIN
        codigo = f"{ped['numero']}-{ped['codigo_retirada']}"
        with self.assertRaises(ErroNegocio):
            self.p.validar_retirada(self.a, f"{ped['numero']}-9999" if ped["codigo_retirada"] != "9999" else f"{ped['numero']}-0000")
        fim = self.p.validar_retirada(self.a, codigo)
        self.assertEqual(fim["status"], "concluido")
        with self.assertRaises(ErroNegocio):  # duplicidade
            self.p.validar_retirada(self.a, codigo)
        estados = [h["para_status"] for h in fim["historico"]]
        self.assertEqual(estados, ["criado", "aguardando_pagamento", "pago", "recebido", "preparando", "pronto",
                                   "aguardando_retirada", "retirado", "concluido"])

    def test_qr_token_tambem_valida(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        self.assertEqual(self.p.validar_retirada(self.a, ped["token_retirada"])["status"], "concluido")

    def test_nao_vende_acima_do_estoque(self):
        o = self.oferta(quantidade_total=3, limite_por_cliente=10)
        self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 3}]})
        self.assertEqual(self.p.obter_oferta(self.a, o["id"])["status"], "esgotada")
        outro = self.p.ator_da_sessao(self.p.cadastrar_cliente({"nome": "Dani", "email": "d@c.test", "senha": "senha123ok", "aceite_termos": True})["token"])
        with self.assertRaises(ErroNegocio):
            self.p.criar_pedido(outro, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})
        self.assertEqual(self.p.vitrine({}), [])

    def test_limite_por_cliente(self):
        o = self.oferta(limite_por_cliente=2)
        self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 2}]})
        with self.assertRaises(ErroNegocio):
            self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})

    def test_reserva_vence_e_estoque_volta(self):
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 4}]})
        self.rel.andar(minutes=16)
        self.assertEqual(self.p.rotina()["reservas_vencidas"], 1)
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "expirado")
        self.assertEqual(self.p.obter_oferta(self.a, o["id"])["disponivel"], 8)
        with self.assertRaises(ErroNegocio):
            self.p.pagar(self.cli, ped["id"])

    def test_cancelamento_estorna_e_devolve(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 2}]})["id"])
        ped = self.p.cancelar_pedido(self.cli, ped["id"])
        self.assertEqual(ped["status"], "cancelado")
        self.assertEqual(ped["pagamentos"][0]["status"], "estornado")
        self.assertEqual(self.p.obter_oferta(self.a, o["id"])["disponivel"], 8)

    def test_cesta_surpresa_exige_faixa(self):
        with self.assertRaises(ErroNegocio):
            self.oferta(tipo="cesta", nome="Cesta da padaria")
        o = self.oferta(tipo="cesta", nome="Cesta da padaria", valor_estimado_min="30", valor_estimado_max="45")
        self.assertEqual(o["tipo_nome"], "Cesta surpresa")


class TestDispatch(Base):
    def test_pedido_entregador_coleta_rota_entrega(self):
        self.p.criar_usuario(self.adm, {"nome": "Edu", "email": "edu@e.test", "papel": "entregador"})
        self.p.criar_usuario(self.adm, {"nome": "Fê", "email": "fe@e.test", "papel": "entregador"})
        edu = self.p.ator_da_sessao(self.p.entrar("edu@e.test", "1234")["token"])
        fe = self.p.ator_da_sessao(self.p.entrar("fe@e.test", "1234")["token"])
        self.p.enviar_posicao(edu, -10.912, -37.072)  # pertinho da loja
        self.p.enviar_posicao(fe, -10.99, -37.10)     # longe
        self.p.ficar_online(edu, True)
        self.p.ficar_online(fe, True)
        o = self.oferta()
        ped = self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}], "modo": "entrega",
                                            "endereco": "Rua X, 10", "lat": -10.92, "lng": -37.06})
        self.assertEqual(ped["total_centavos"], 1250 + 600)
        self.p.pagar(self.cli, ped["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        painel = self.p.painel_entregador(edu)
        self.assertEqual(len(painel["ativas"]), 1, "o mais perto recebe a oferta")
        corrida = painel["ativas"][0]
        # Edu recusa → vai para Fê (fallback)
        self.p.responder_corrida(edu, corrida["id"], False)
        self.assertEqual(len(self.p.painel_entregador(fe)["ativas"]), 1)
        # Fê deixa o prazo vencer → ninguém mais (Edu recusou) → fica aguardando
        self.rel.andar(seconds=120)
        self.p.rotina()
        self.assertEqual(self.p.painel_dispatch(self.adm)["sem_entregador"], 1)
        # Logística designa manualmente
        er_edu = self.p.banco.um("SELECT id FROM entregadores WHERE usuario_id=?", (edu.usuario_id,))["id"]
        self.p.designar_manual(self.adm, corrida["id"], er_edu)
        self.p.responder_corrida(edu, corrida["id"], True)
        self.assertEqual(self.p.obter_pedido(self.cli, ped["id"])["status"], "entregador_designado")
        self.p.avancar_corrida(edu, corrida["id"], "cheguei_loja")
        self.p.avancar_corrida(edu, corrida["id"], "coletei")
        with self.assertRaises(ErroNegocio):
            self.p.avancar_corrida(edu, corrida["id"], "entreguei", "0000" if ped["codigo_retirada"] != "0000" else "1111")
        painel = self.p.avancar_corrida(edu, corrida["id"], "entreguei", ped["codigo_retirada"])
        self.assertEqual(painel["ganhos_total_centavos"], 600)
        fim = self.p.confirmar_recebimento(self.cli, ped["id"])
        self.assertEqual(fim["status"], "concluido")
        self.assertIn("em_rota", [h["para_status"] for h in fim["historico"]])

    def test_sem_gps_nao_entra_no_dispatch(self):
        self.p.criar_usuario(self.adm, {"nome": "Gil", "email": "gil@e.test", "papel": "entregador"})
        gil = self.p.ator_da_sessao(self.p.entrar("gil@e.test", "1234")["token"])
        self.p.ficar_online(gil, True)
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}], "modo": "entrega",
                                                                     "endereco": "Rua Y"})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        self.assertEqual(self.p.painel_entregador(gil)["ativas"], [])


class TestFinanceiro(Base):
    def _venda(self, q=2):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": q}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        return self.p.validar_retirada(self.a, ped["token_retirada"])

    def test_cobranca_taxa_repasse_conciliacao(self):
        ped = self._venda(2)
        self.assertEqual(ped["taxa_centavos"], 300)      # 12% de 2500
        self.assertEqual(ped["repasse_centavos"], 2200)
        r = self.p.resumo_financeiro(self.adm)
        self.assertEqual((r["gmv_centavos"], r["receita_plataforma_centavos"], r["a_repassar_centavos"]), (2500, 300, 2200))
        self.assertEqual(r["economia_clientes_centavos"], 2480)
        self.assertTrue(self.p.conciliacao(self.adm)["fecha"])
        with self.assertRaises(SemPermissao):
            self.p.calcular_repasse(self.a, self.emp_a["id"])  # empresa não paga a si mesma
        rep = self.p.calcular_repasse(self.adm, self.emp_a["id"])
        self.assertEqual(rep["valor_centavos"], 2200)
        with self.assertRaises(ErroNegocio):
            self.p.calcular_repasse(self.adm, self.emp_a["id"])  # nada em dobro
        self.p.marcar_repasse_pago(self.adm, rep["id"], "PIX teste 001")
        self.assertEqual(self.p.resumo_financeiro(self.a)["a_repassar_centavos"], 0)
        self.assertTrue(self.p.conciliacao(self.adm)["fecha"])


class TestAntissobra(Base):
    def test_preco_progressivo_respeita_minimo_e_registra(self):
        o = self.oferta(regra_preco="progressivo", preco_minimo="9,00",
                        regra_preco_dados=[{"minutos_antes_fim": 60, "preco": "10,00"}, {"minutos_antes_fim": 30, "preco": "9,00"}])
        self.assertEqual(o["preco_centavos"], 1250)
        self.rel.andar(hours=2, minutes=5)
        self.p.rotina()
        self.assertEqual(self.p.obter_oferta(self.a, o["id"])["preco_centavos"], 1000)
        self.rel.andar(minutes=30)
        self.p.rotina()
        oo = self.p.obter_oferta(self.a, o["id"])
        self.assertEqual(oo["preco_centavos"], 900)
        self.assertEqual([h["origem"] for h in oo["historico_precos"]], ["regra", "regra"])
        with self.assertRaises(ErroNegocio):
            self.oferta(regra_preco="progressivo", preco_minimo="9,00", regra_preco_dados=[{"minutos_antes_fim": 60, "preco": "5"}])

    def test_janela_expira_sobra_e_nao_retirado(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 1}]})["id"])
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        self.rel.andar(hours=3, minutes=31)
        r = self.p.rotina()
        self.assertEqual((r["ofertas_encerradas"], r["nao_retirados"]), (1, 1))
        oo = self.p.obter_oferta(self.a, o["id"])
        self.assertEqual((oo["status"], oo["expirada"], oo["vendida"]), ("encerrada", 7, 1))
        self.assertEqual(self.p.obter_pedido(self.a, ped["id"])["status"], "nao_retirado")
        self.assertEqual(self.p.vitrine({}), [])


class TestDoacao(Base):
    def test_nao_vendida_instituicao_aceite_coleta_destinacao(self):
        inst = self.p.salvar_instituicao(None, {"nome": "Casa Esperança", "responsavel": "Irmã Lia", "aceite_termos": True})
        o = self.oferta()
        self.rel.andar(hours=4)
        self.p.rotina()
        with self.assertRaises(ErroNegocio):  # instituição não autorizada
            self.p.propor_doacao(self.a, {"oferta_id": o["id"], "instituicao_id": inst["id"], "quantidade": 5})
        self.p.autorizar_instituicao(self.adm, inst["id"], True)
        self.p.criar_usuario(self.adm, {"nome": "Lia", "email": "lia@i.test", "papel": "instituicao", "instituicao_id": inst["id"]})
        lia = self.p.ator_da_sessao(self.p.entrar("lia@i.test", "1234")["token"])
        d = self.p.propor_doacao(self.a, {"oferta_id": o["id"], "instituicao_id": inst["id"], "quantidade": 5})
        self.assertEqual(self.p.impacto(self.a)["kg_doados"], 0)
        with self.assertRaises(ErroNegocio):  # não pula etapas
            self.p.avancar_doacao(lia, d["id"], "confirmar", {"pessoas_beneficiadas": 10})
        with self.assertRaises(ErroNegocio):  # empresa não aceita no lugar da instituição
            self.p.avancar_doacao(self.a, d["id"], "aceitar")
        self.p.avancar_doacao(lia, d["id"], "aceitar")
        with self.assertRaises(ErroNegocio):
            self.p.avancar_doacao(self.a, d["id"], "coletar", {})  # sem responsável
        self.p.avancar_doacao(self.a, d["id"], "coletar", {"responsavel": "Seu João (van da Casa)"})
        fim = self.p.avancar_doacao(lia, d["id"], "confirmar", {"pessoas_beneficiadas": 12})
        self.assertEqual(fim["status"], "destinada")
        self.assertTrue(all(fim[k] for k in ("proposta_por", "proposta_em", "aceita_por", "aceita_em", "coleta_em",
                                             "coleta_responsavel", "destinada_por", "destinada_em")))
        imp = self.p.impacto(self.a)
        self.assertEqual((imp["kg_doados"], imp["pessoas_beneficiadas"], imp["instituicoes_atendidas"]), (3.0, 12, 1))
        oo = self.p.obter_oferta(self.a, o["id"])
        self.assertEqual((oo["expirada"], oo["destinada"]), (3, 5))


class TestImpacto(Base):
    def test_venda_vira_kg(self):
        o = self.oferta()
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": o["id"], "quantidade": 3}]})["id"])
        self.assertEqual(self.p.impacto(self.a)["kg_vendidos"], 0)  # só conta quando conclui
        for acao in ("receber", "preparar", "pronto"):
            self.p.avancar_pedido(self.a, ped["id"], acao)
        self.p.validar_retirada(self.a, ped["token_retirada"])
        self.assertEqual(self.p.impacto(self.a)["kg_vendidos"], 1.8)
        self.assertEqual(self.p.impacto(cliente_id=self.cli.usuario_id)["economia_clientes_centavos"], 3720)
        self.assertEqual(self.p.impacto(self.b)["kg_vendidos"], 0)


class TestSeguranca(Base):
    def test_empresa_a_nao_acessa_empresa_b(self):
        ob = self.oferta(self.b, self.uni_b, nome="Pão de ontem")
        ped = self.p.pagar(self.cli, self.p.criar_pedido(self.cli, {"itens": [{"oferta_id": ob["id"], "quantidade": 1}]})["id"])
        with self.assertRaises(NaoEncontrado):
            self.p.obter_oferta(self.a, ob["id"])
        with self.assertRaises(NaoEncontrado):
            self.p.salvar_oferta(self.a, {"nome": "hack"}, ob["id"])
        with self.assertRaises(NaoEncontrado):
            self.p.obter_pedido(self.a, ped["id"])
        with self.assertRaises(NaoEncontrado):
            self.p.avancar_pedido(self.a, ped["id"], "receber")
        with self.assertRaises(SemPermissao):
            self.p.listar_pedidos(self.a, self.emp_b["id"])
        with self.assertRaises(NaoEncontrado):
            self.p.obter_empresa(self.a, self.emp_b["id"])
        with self.assertRaises(NaoEncontrado):
            self.p.validar_retirada(self.a, ped["token_retirada"])
        self.assertEqual(self.p.listar_pedidos(self.a), [])
        self.assertEqual([o["id"] for o in self.p.listar_ofertas(self.a)], [])
        self.assertEqual(self.p.resumo_financeiro(self.a)["pedidos"], 0)
        outro = self.p.ator_da_sessao(self.p.cadastrar_cliente({"nome": "Eva", "email": "eva@c.test", "senha": "senha123ok", "aceite_termos": True})["token"])
        with self.assertRaises(NaoEncontrado):
            self.p.obter_pedido(outro, ped["id"])

    def test_papeis(self):
        self.p.criar_usuario(self.a, {"nome": "Op", "email": "op@a.test", "papel": "operador_empresa"})
        op = self.p.ator_da_sessao(self.p.entrar("op@a.test", "1234")["token"])
        with self.assertRaises(SemPermissao):
            self.p.resumo_financeiro(op)
        with self.assertRaises(SemPermissao):
            self.p.criar_usuario(op, {"nome": "x", "email": "x@a.test", "papel": "admin_empresa"})
        with self.assertRaises(SemPermissao):
            self.p.criar_usuario(self.a, {"nome": "x", "email": "x@a.test", "papel": "admin_sobrou"})
        with self.assertRaises(SemPermissao):
            self.p.criar_pedido(self.a, {"itens": []})
        with self.assertRaises(SemPermissao):
            self.p.aprovar_empresa(self.a, self.emp_a["id"])

    def test_empresa_nao_aprovada_nao_publica(self):
        sess = self.p.cadastrar_empresa({"nome": "Nova", "tipo": "cafe", "email_responsavel": "n@n.test", "senha": "senha123ok", "aceite_termos": True})
        n = self.p.ator_da_sessao(sess["token"])
        u = self.p.salvar_unidade(n, {"nome": "Loja"})
        foto = self.p.enviar_foto(n, {"imagem": JPEG})
        o = self.p.salvar_oferta(n, {"unidade_id": u["id"], "nome": "Café", "preco_normal": "10", "preco": "5", "quantidade_total": 2,
                                     "inicio": local(self.rel), "fim": local(self.rel, hours=2), "retirada_inicio": local(self.rel),
                                     "retirada_fim": local(self.rel, hours=2), "foto_id": foto["id"]})
        with self.assertRaises(ErroNegocio):
            self.p.mudar_status_oferta(n, o["id"], "ativa")

    def test_bloqueio_por_tentativas_e_foto_invalida(self):
        for _ in range(5):
            with self.assertRaises(Exception):
                self.p.entrar("ana@a.test", "errada")
        with self.assertRaises(ErroNegocio):
            self.p.entrar("ana@a.test", "1234")
        with self.assertRaises(ErroNegocio):
            self.p.enviar_foto(self.b, {"imagem": base64.b64encode(b"<svg>").decode()})

    def test_auditoria(self):
        o = self.oferta()
        self.p.alterar_preco(self.a, o["id"], "11,00")
        acoes = [x["acao"] for x in self.p.listar_auditoria(self.a)]
        self.assertIn("preco.manual", acoes)
        self.assertIn("oferta.criar", acoes)
        self.assertNotIn("empresa.criar", [x["acao"] for x in self.p.listar_auditoria(self.b) if x["alvo"] == self.emp_a["id"]])


if __name__ == "__main__":
    unittest.main()
