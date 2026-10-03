"""Dados de DEMONSTRAÇÃO do Sobrou+ (banco separado: data/demo). Tudo marcado como demonstração — nada é dado real.

Fotos: imagens ILUSTRATIVAS fictícias (estilo fotografia real, geradas para a demonstração — pasta demo_fotos).
Na loja de verdade, cada parceiro envia a foto real do alimento. Nunca desenho/cartoon.
"""
from __future__ import annotations

from datetime import timedelta

from .nucleo import iso, novo_id

USUARIOS = {
    "admin_sobrou": ("Equipe Sobrou+ (demo)", "admin@demo.sobrou"),
    "admin_empresa": ("Marta — Sabor da Casa (demo)", "marta@demo.sobrou"),
    "operador_empresa": ("Caio — balcão (demo)", "caio@demo.sobrou"),
    "financeiro": ("Financeiro Sobrou+ (demo)", "financeiro@demo.sobrou"),
    "entregador": ("Edu — entregador (demo)", "edu@demo.sobrou"),
    "cliente": ("Cliente demonstração", "cliente@demo.sobrou"),
    "instituicao": ("Casa Esperança (demo)", "casa@demo.sobrou"),
}


def garantir_demonstracao(p) -> dict:
    """Cria (uma vez) o mundo de demonstração e devolve {papel: usuario_id}."""
    ja = p.banco.um("SELECT valor FROM config WHERE chave='demo_pronta'")
    if not ja:
        _semear(p)
    ids = {}
    for papel, (_nome, email) in USUARIOS.items():
        u = p.banco.um("SELECT id FROM usuarios WHERE email=?", (email,))
        if u:
            ids[papel] = u["id"]
    _garantir_fotos(p)
    _renovar_ofertas(p)
    _garantir_planos_demo(p)
    return ids


def _garantir_planos_demo(p):
    """Lojas de demonstração ganham um plano (para ver taxa, mensalidade e destaque funcionando). Só mexe em quem está sem plano."""
    p.garantir_planos()
    planos = {r["nome"]: r["id"] for r in p.banco.todos("SELECT id, nome FROM planos")}
    ordem = [planos.get("Destaque"), planos.get("Profissional"), planos.get("Essencial")]
    for i, e in enumerate(p.banco.todos("SELECT id FROM empresas WHERE demonstracao=1 AND plano_id IS NULL ORDER BY criada_em")):
        if ordem[i % 3]:
            p.banco.executar("UPDATE empresas SET plano_id=? WHERE id=?", (ordem[i % 3], e["id"]))


FOTOS = {"Marmita Executiva": "marmita", "Kit 3 salgados assados": "salgados", "Cesta surpresa da padaria": "padaria",
         "Bolo de milho inteiro": "bolo_milho", "Caixa de frutas e verduras": "hortifruti"}


def _garantir_fotos(p):
    import shutil
    from pathlib import Path
    pasta = Path(__file__).resolve().parent / "demo_fotos"
    for o in p.banco.todos("""SELECT o.id, o.nome, o.empresa_id FROM ofertas o JOIN empresas e ON e.id=o.empresa_id
                              WHERE e.demonstracao=1 AND o.foto_id IS NULL"""):
        nome = FOTOS.get(o["nome"])
        if not nome or not (pasta / f"{nome}.jpg").exists():
            continue
        fid = novo_id()
        destino = p.pasta_fotos / o["empresa_id"]
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pasta / f"{nome}.jpg", destino / f"{fid}.jpg")
        shutil.copyfile(pasta / f"{nome}_mini.jpg", destino / f"{fid}_mini.jpg")
        p.banco.executar("INSERT INTO fotos(id, empresa_id, arquivo, miniatura, tipo, bytes, criada_em) VALUES (?,?,?,?,?,?,?)",
                         (fid, o["empresa_id"], f"{o['empresa_id']}/{fid}.jpg", f"{o['empresa_id']}/{fid}_mini.jpg", "image/jpeg",
                          (destino / f"{fid}.jpg").stat().st_size, p.agora()))
        p.banco.executar("UPDATE ofertas SET foto_id=? WHERE id=?", (fid, o["id"]))


def _semear(p):
    b = p.banco
    agora = p.agora()
    adm = p.garantir_admin_sobrou(USUARIOS["admin_sobrou"][1], USUARIOS["admin_sobrou"][0])
    b.executar("UPDATE usuarios SET trocar_senha=0 WHERE id=?", (adm["id"],))
    from .nucleo import Ator
    a = Ator(adm["id"], "admin_sobrou", adm["nome"])
    e1 = p.criar_empresa(a, {"nome": "Sabor da Casa (demonstração)", "tipo": "restaurante", "demonstracao": True})
    e2 = p.criar_empresa(a, {"nome": "Padaria Pão Quente (demonstração)", "tipo": "padaria", "demonstracao": True})
    e3 = p.criar_empresa(a, {"nome": "Hortifrúti Verde Vale (demonstração)", "tipo": "hortifruti", "demonstracao": True})
    for e in (e1, e2, e3):
        b.executar("UPDATE config_empresa SET aceita_entrega=1, taxa_entrega_centavos=700, raio_entrega_km=8 WHERE empresa_id=?", (e["id"],))
    unidades = {}
    for e, nome, end, bairro, lat, lng, instr in (
        (e1, "Centro", "Rua de exemplo, 100", "Centro", -10.9111, -37.0717, "Retirada no balcão lateral"),
        (e2, "Bairro Novo", "Av. de exemplo, 250", "Bairro Novo", -10.9260, -37.0560, "Falar com o caixa"),
        (e3, "Mercado Municipal", "Box 12 (exemplo)", "Centro", -10.9150, -37.0500, "Box 12, ao lado da entrada"),
    ):
        uid = novo_id()
        b.executar("""INSERT INTO unidades(id, empresa_id, nome, endereco, bairro, cidade, lat, lng, instrucoes_retirada, criada_em)
                      VALUES (?,?,?,?,?,?,?,?,?,?)""", (uid, e["id"], nome, end, bairro, "Aracaju", lat, lng, instr, agora))
        unidades[e["id"]] = uid
    for papel in ("admin_empresa", "operador_empresa"):
        nome, email = USUARIOS[papel]
        p.criar_usuario(a, {"nome": nome, "email": email, "papel": papel, "empresa_id": e1["id"]})
    p.criar_usuario(a, {"nome": USUARIOS["financeiro"][0], "email": USUARIOS["financeiro"][1], "papel": "financeiro"})
    p.criar_usuario(a, {"nome": USUARIOS["entregador"][0], "email": USUARIOS["entregador"][1], "papel": "entregador", "veiculo": "Moto"})
    inst = p.salvar_instituicao(a, {"nome": "Casa Esperança (demonstração)", "responsavel": "Irmã Lia", "cidade": "Aracaju", "pessoas_atendidas": 80})
    p.autorizar_instituicao(a, inst["id"], True)
    p.criar_usuario(a, {"nome": USUARIOS["instituicao"][0], "email": USUARIOS["instituicao"][1], "papel": "instituicao", "instituicao_id": inst["id"]})
    p._inserir_usuario(USUARIOS["cliente"][0], USUARIOS["cliente"][1], "cliente", None)
    b.executar("UPDATE usuarios SET trocar_senha=0 WHERE email LIKE '%@demo.sobrou'")
    ofertas = [
        (e1, "produto", "Marmita Executiva", "refeicoes", 2490, 1250, 8, 0.6, "Arroz, feijão, carne do dia e salada. Feita hoje. (imagem ilustrativa)"),
        (e1, "kit", "Kit 3 salgados assados", "refeicoes", 1800, 790, 6, 0.35, "Salgados do balcão da tarde. (imagem ilustrativa)"),
        (e2, "cesta", "Cesta surpresa da padaria", "cesta_surpresa", 3500, 1490, 10, 1.2, "Pães, bolos e doces do dia — a padaria monta. (imagem ilustrativa)"),
        (e2, "produto", "Bolo de milho inteiro", "doces", 3200, 1600, 3, 1.0, "Bolo inteiro, feito pela manhã. (imagem ilustrativa)"),
        (e3, "cesta", "Caixa de frutas e verduras", "frutas", 4000, 1800, 12, 3.0, "Frutas e verduras boas, fora do padrão de vitrine. (imagem ilustrativa)"),
    ]
    for e, tipo, nome, cat, normal, preco, qtd, peso, desc in ofertas:
        oid = novo_id()
        b.executar("""INSERT INTO ofertas(id, empresa_id, unidade_id, tipo, nome, descricao, categoria, preco_normal_centavos, preco_centavos,
                      preco_base_centavos, valor_estimado_min_centavos, valor_estimado_max_centavos, quantidade_total, peso_kg_unidade,
                      inicio, fim, retirada_inicio, retirada_fim, permite_retirada, permite_entrega, status, criada_em, atualizada_em)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,'ativa',?,?)""",
                  (oid, e["id"], unidades[e["id"]], tipo, nome, desc, cat, normal, preco, preco,
                   normal if tipo == "cesta" else None, normal + 1500 if tipo == "cesta" else None, qtd, peso,
                   agora, agora, agora, agora, agora, agora))
        b.executar("INSERT INTO movimentos_estoque(id, oferta_id, empresa_id, tipo, quantidade, motivo, quando) VALUES (?,?,?,?,?,?,?)",
                   (novo_id(), oid, e["id"], "entrada", qtd, "demonstração", agora))
    b.executar("INSERT INTO config(chave, valor) VALUES ('demo_pronta', '1')")


def _renovar_ofertas(p):
    """Na demonstração, as ofertas valem 'hoje': janela de venda e retirada sempre a partir de agora."""
    agora = p.agora_dt()
    fim = iso(agora + timedelta(hours=4))
    p.banco.executar("""UPDATE ofertas SET inicio=?, fim=?, retirada_inicio=?, retirada_fim=?, status='ativa',
                        expirada=0, reservada=0, vendida=0, destinada=0
                        WHERE empresa_id IN (SELECT id FROM empresas WHERE demonstracao=1)
                          AND id NOT IN (SELECT oferta_id FROM pedido_itens) AND (fim<? OR status<>'ativa')""",
                     (iso(agora - timedelta(minutes=5)), fim, iso(agora + timedelta(minutes=30)), fim, iso(agora + timedelta(hours=1))))
