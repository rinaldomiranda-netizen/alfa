"""Testes com os sócios: o Desenvolvedor RMD cadastra uma pessoa e o sistema cria, na Loja Teste RMD,
uma conta para cada aplicativo (Central, Loja, Caixa, Entregador e Cliente), cada uma com o seu link de acesso.

Cada aplicativo tem endereço, nome, ícone e sessão próprios (/apps/<nome>/), então instalar um não
substitui o outro no celular. As contas usam dados de TESTE (loja marcada como demonstração).
"""
from __future__ import annotations

import re
import secrets
import unicodedata

from .integracoes import telefone_whatsapp
from .nucleo import Ator, ErroNegocio, NaoEncontrado, SemPermissao, novo_id, texto

# app -> (papel, nome que aparece no celular, para que serve)
APPS_TESTE = {
    "central": ("admin_sobrou", "Sobrou+ Central", "Equipe Sobrou+: empresas, pedidos, financeiro e relatórios."),
    "loja": ("admin_empresa", "Sobrou+ Loja", "Administração da loja parceira: ofertas, estoque, pedidos e financeiro."),
    "caixa": ("operador_empresa", "Sobrou+ Caixa", "Balcão/caixa da loja: recebe os pedidos e confere o código de retirada."),
    "entregador": ("entregador", "Sobrou+ Entregador", "Entregador: fica online, aceita corridas e confirma a entrega."),
    "cliente": ("cliente", "Sobrou+ Cliente", "Cliente: vê as ofertas, compra, paga (modo teste) e retira."),
}
DOMINIO_TESTE = "teste.sobrou"


def _slug(nome: str) -> str:
    base = unicodedata.normalize("NFKD", (nome or "").split(" ")[0]).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", base)[:20] or "socio"


class TestesMixin:
    def _exigir_desenvolvedor(self, ator: Ator) -> None:
        if ator.usuario_id != self.id_dono() and ator.papel != "admin_sobrou":
            raise SemPermissao("Só o Desenvolvedor RMD compartilha o sistema para testes.")

    def _contas_testador(self, testador_id: str) -> list[dict]:
        linhas = self.banco.todos("""SELECT t.app, u.id AS usuario_id, u.email, u.nome, u.ativo, u.ultimo_acesso, u.aceite_termos_em
                                     FROM testador_contas t JOIN usuarios u ON u.id=t.usuario_id WHERE t.testador_id=?""", (testador_id,))
        ordem = list(APPS_TESTE)
        for x in linhas:
            x["nome_app"] = APPS_TESTE[x["app"]][1]
            x["senha_criada"] = bool(x.pop("aceite_termos_em"))  # só quem abriu o link e criou a senha aceitou os termos
        return sorted(linhas, key=lambda x: ordem.index(x["app"]))

    def _links(self, ator: Ator, contas: list[dict]) -> list[dict]:
        saida = []
        for x in contas:
            token = self.gerar_convite(ator, x["usuario_id"])
            saida.append({"app": x["app"], "nome_app": APPS_TESTE[x["app"]][1], "email": x["email"],
                          "caminho": f"/apps/{x['app']}/acesso?c={token}"})
        return saida

    def listar_testadores(self, ator: Ator) -> dict:
        self._exigir_desenvolvedor(ator)
        itens = self.banco.todos("SELECT * FROM testadores ORDER BY criado_em DESC")
        for t in itens:
            t["contas"] = self._contas_testador(t["id"])
        return {"itens": itens, "apps": [{"app": k, "nome": v[1], "descricao": v[2]} for k, v in APPS_TESTE.items()]}

    def criar_testador(self, ator: Ator, dados: dict) -> dict:
        self._exigir_desenvolvedor(ator)
        nome = texto(dados.get("nome"), 80, True, "o nome")
        tel_bruto = texto(dados.get("telefone"), 30)
        tel = telefone_whatsapp(tel_bruto) if tel_bruto else None
        if tel_bruto and not tel:
            raise ErroNegocio("Celular inválido. Use DDD + número, por exemplo 79 99999-9999.")
        mundo = self.mundo_de_teste()
        eid = mundo["empresa_id"]
        slug = base = _slug(nome)
        n = 1
        while self.banco.um("SELECT 1 FROM usuarios WHERE email LIKE ?", (f"{slug}.%@{DOMINIO_TESTE}",)):
            n += 1
            slug = f"{base}{n}"
        tid = novo_id()
        self.banco.executar("INSERT INTO testadores(id, nome, telefone, ativo, criado_por, criado_em) VALUES (?,?,?,1,?,?)",
                            (tid, nome, tel, ator.usuario_id, self.agora()))
        contas = []
        for app, (papel, nome_app, _d) in APPS_TESTE.items():
            # Senha aleatória que ninguém conhece: a pessoa cria a dela pelo link (ninguém entra antes dela).
            u = self._inserir_usuario(f"{nome} ({nome_app.replace('Sobrou+ ', '')} — teste)", f"{slug}.{app}@{DOMINIO_TESTE}", papel,
                                      secrets.token_urlsafe(18) + "a1", eid if papel in ("admin_empresa", "operador_empresa") else None,
                                      None, tel, trocar=False)
            if papel == "entregador":
                self.banco.executar("INSERT INTO entregadores(id, usuario_id, empresa_id, tipo, veiculo, capacidade, criado_em) VALUES (?,?,?,?,?,?,?)",
                                    (novo_id(), u["id"], eid, "proprio", "Moto (teste)", 3, self.agora()))
            self.banco.executar("INSERT INTO testador_contas(testador_id, app, usuario_id) VALUES (?,?,?)", (tid, app, u["id"]))
            contas.append({"app": app, "usuario_id": u["id"], "email": u["email"]})
        self.auditar(ator, "testes.socio_criado", tid, {"nome": nome}, empresa_id=None)
        t = self.banco.um("SELECT * FROM testadores WHERE id=?", (tid,))
        return {"testador": t, "links": self._links(ator, contas)}

    def novos_links_testador(self, ator: Ator, testador_id: str) -> dict:
        self._exigir_desenvolvedor(ator)
        t = self.banco.um("SELECT * FROM testadores WHERE id=?", (testador_id,))
        if not t:
            raise NaoEncontrado("Pessoa de teste não encontrada.")
        if not t["ativo"]:
            raise ErroNegocio("Os acessos desta pessoa estão desligados. Ligue de novo antes de gerar links.")
        contas = self._contas_testador(testador_id)
        self.auditar(ator, "testes.novos_links", testador_id, empresa_id=None)
        return {"testador": t, "links": self._links(ator, contas)}

    def ligar_testador(self, ator: Ator, testador_id: str, ligado: bool) -> dict:
        self._exigir_desenvolvedor(ator)
        t = self.banco.um("SELECT * FROM testadores WHERE id=?", (testador_id,))
        if not t:
            raise NaoEncontrado("Pessoa de teste não encontrada.")
        ids = [x["usuario_id"] for x in self.banco.todos("SELECT usuario_id FROM testador_contas WHERE testador_id=?", (testador_id,))]
        for uid in ids:
            self.banco.executar("UPDATE usuarios SET ativo=? WHERE id=?", (1 if ligado else 0, uid))
            if not ligado:
                self.banco.executar("DELETE FROM sessoes WHERE usuario_id=?", (uid,))
                self.banco.executar("UPDATE convites SET usado_em=? WHERE usuario_id=? AND usado_em IS NULL", (self.agora(), uid))
        self.banco.executar("UPDATE testadores SET ativo=? WHERE id=?", (1 if ligado else 0, testador_id))
        self.auditar(ator, "testes.ligar" if ligado else "testes.desligar", testador_id, empresa_id=None)
        return {"ok": True}
