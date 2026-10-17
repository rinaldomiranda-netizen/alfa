"""Fluxos (robô de atendimento) — execução determinística.

O robô segue exatamente as etapas cadastradas, uma por uma. Não usa
inteligência artificial e não inventa respostas. Toda publicação exige
uma simulação sem erros antes (governança).

Etapas suportadas:
  mensagem  {"texto"}
  pergunta  {"texto", "variavel", "opcoes"?}
  memoria   {"variavel", "valor"}
  tag       {"tag"}
  condicao  {"variavel", "operador": igual|diferente|contem|nao_contem|comeca_com|existe|nao_existe|em_lista|maior|menor,
             "valor"?, "ir_para"?, "senao_ir_para"?}
  handoff   {"destino": fila|sede, "fila"?, "texto"?, "liberacao"?}   -> passa para um atendente humano
            destino "sede": só a Sede enxerga o pedido (não passa pelo administrador do setor);
            "liberacao": a Sede precisa liberar antes de a resposta chegar ao cliente.
  notificar {"texto"}               -> avisa a Sede (alerta) sem parar o robô
  encerrar  {"texto"?}

Variáveis que o robô já conhece (além das que ele mesmo guarda): nome, empresa, canal,
unidade, unidade_tipo, igreja, origem ("sede" quando a pessoa não pertence a nenhuma igreja/setor).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from .db import agora
from .nucleo import Ator, ErroNegocio, NaoEncontrado, _texto, novo_id

TIPOS = ("mensagem", "pergunta", "memoria", "tag", "condicao", "handoff", "notificar", "encerrar")
OPERADORES = ("igual", "diferente", "contem", "nao_contem", "comeca_com", "existe", "nao_existe", "em_lista", "maior", "menor")
DESTINOS = ("fila", "sede")
GATILHOS = ("sempre", "palavra_chave", "manual")
# O que o robô já sabe sobre a pessoa. Valor None = texto livre; lista = só estes valores existem.
VARIAVEIS_SISTEMA = {
    "nome": None, "empresa": None, "unidade": None, "igreja": None,
    "canal": ["web", "whatsapp", "portal", "interno"],
    "unidade_tipo": ["setor", "campo", "igreja", "congregacao", "departamento"],
    "origem": ["sede", "unidade"],
}
LIMITE_PASSOS_POR_RODADA = 50
_VARIAVEL = re.compile(r"^[a-z_][a-z0-9_]{0,39}$")
_MARCADOR = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto).strip().lower()


@dataclass
class Resultado:
    saidas: list[dict] = field(default_factory=list)
    estado: dict = field(default_factory=dict)
    acao: str | None = None          # None (aguardando resposta) | handoff | encerrar | fim
    fila_id: str | None = None
    destino: str = "fila"            # fila | sede
    exige_liberacao: bool = False
    notificacoes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    loop: bool = False


def validar_etapas(etapas, filas_validas: set[str] | None = None) -> list[str]:
    erros: list[str] = []
    if not isinstance(etapas, list) or not etapas:
        return ["O fluxo precisa ter pelo menos uma etapa."]
    if len(etapas) > 100:
        erros.append("O fluxo pode ter no máximo 100 etapas.")
    total = len(etapas)
    conhecidas = _variaveis_do_fluxo(etapas)
    for numero, etapa in enumerate(etapas, start=1):
        rotulo = f"Etapa {numero}"
        if not isinstance(etapa, dict) or etapa.get("tipo") not in TIPOS:
            erros.append(f"{rotulo}: tipo desconhecido.")
            continue
        tipo = etapa["tipo"]
        if tipo in ("mensagem", "pergunta") and not str(etapa.get("texto") or "").strip():
            erros.append(f"{rotulo}: escreva o texto.")
        for campo_texto in ("texto", "valor"):
            for marcador in _MARCADOR.findall(str(etapa.get(campo_texto) or "")) if tipo != "condicao" or campo_texto == "valor" else []:
                if marcador not in conhecidas:
                    erros.append(f"{rotulo}: {{{{{marcador}}}}} não existe (nenhuma pergunta ou memória com esse nome).")
        if tipo in ("pergunta", "memoria", "condicao") and not _VARIAVEL.match(str(etapa.get("variavel") or "")):
            erros.append(f"{rotulo}: nome da memória inválido (use letras minúsculas, números e _).")
        if tipo == "pergunta" and etapa.get("opcoes"):
            opcoes = etapa["opcoes"]
            if not isinstance(opcoes, list) or len(opcoes) > 10:
                erros.append(f"{rotulo}: no máximo 10 opções.")
            elif any(not str(o).strip() or len(str(o)) > 24 for o in opcoes):
                erros.append(f"{rotulo}: cada opção precisa ter de 1 a 24 caracteres.")
            elif len({_normalizar(str(o)) for o in opcoes}) != len(opcoes):
                erros.append(f"{rotulo}: há opções repetidas.")
        if tipo == "tag" and not str(etapa.get("tag") or "").strip():
            erros.append(f"{rotulo}: escreva a etiqueta.")
        if tipo == "condicao":
            if etapa.get("operador") not in OPERADORES:
                erros.append(f"{rotulo}: operador inválido.")
            variavel = str(etapa.get("variavel") or "")
            if _VARIAVEL.match(variavel) and variavel not in conhecidas:
                erros.append(f"{rotulo}: a memória '{variavel}' não existe (use uma pergunta anterior ou uma das informações do sistema).")
            opcoes_var = conhecidas.get(variavel)
            if opcoes_var and etapa.get("operador") in ("igual", "diferente", "em_lista"):
                valores = [str(etapa.get("valor") or "")] if etapa.get("operador") != "em_lista" else [x for x in str(etapa.get("valor") or "").split(",") if x.strip()]
                validos = {_normalizar(o) for o in opcoes_var}
                for v in valores:
                    if v.strip() and _normalizar(v) not in validos:
                        erros.append(f"{rotulo}: '{v.strip()}' não é uma resposta possível de '{variavel}'. Escolha na lista.")
            if etapa.get("operador") in ("maior", "menor") and _numero(etapa.get("valor")) is None:
                erros.append(f"{rotulo}: para 'maior/menor que' informe um número.")
            if etapa.get("operador") in ("igual", "diferente", "contem", "nao_contem", "comeca_com", "em_lista") and not str(etapa.get("valor") or "").strip():
                erros.append(f"{rotulo}: informe o valor da condição.")
            for chave in ("ir_para", "senao_ir_para"):
                destino = etapa.get(chave)
                if destino in (None, ""):
                    continue
                if not isinstance(destino, int) or not 1 <= destino <= total:
                    erros.append(f"{rotulo}: '{chave}' precisa apontar para uma etapa de 1 a {total}.")
        if tipo == "handoff":
            fila = etapa.get("fila")
            destino = etapa.get("destino") or "fila"
            if destino not in DESTINOS:
                erros.append(f"{rotulo}: destino inválido.")
            elif destino == "fila" and not fila:
                erros.append(f"{rotulo}: escolha a fila de destino.")
            elif fila and filas_validas is not None and fila not in filas_validas:
                erros.append(f"{rotulo}: a fila escolhida não existe mais.")
            if etapa.get("liberacao") and destino != "sede":
                erros.append(f"{rotulo}: a liberação só existe quando o destino é a Sede.")
        if tipo == "notificar" and not str(etapa.get("texto") or "").strip():
            erros.append(f"{rotulo}: escreva o aviso para a Sede.")
    return erros


def _variaveis_do_fluxo(etapas) -> dict:
    """Nome -> lista de respostas possíveis (None = livre) de tudo que o fluxo pode ler."""
    conhecidas: dict = {k: (list(v) if v else None) for k, v in VARIAVEIS_SISTEMA.items()}
    por_pergunta: dict[str, list] = {}
    for etapa in etapas if isinstance(etapas, list) else []:
        if not isinstance(etapa, dict):
            continue
        nome = str(etapa.get("variavel") or "")
        if not _VARIAVEL.match(nome) or nome in VARIAVEIS_SISTEMA:
            continue
        if etapa.get("tipo") == "pergunta" and etapa.get("opcoes") and conhecidas.get(nome, ...) is not None:
            por_pergunta.setdefault(nome, []).extend(str(o) for o in etapa["opcoes"] if isinstance(etapa["opcoes"], list))
            conhecidas[nome] = list(por_pergunta[nome])
        elif etapa.get("tipo") in ("pergunta", "memoria"):
            conhecidas[nome] = None   # resposta livre (ou valor montado): qualquer texto vale
            por_pergunta.pop(nome, None)
    return conhecidas


def _numero(valor):
    try:
        return float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _avaliar(operador: str, valor: str, alvo: str) -> bool:
    nv, na = _normalizar(valor), _normalizar(alvo)
    if operador == "igual":
        return nv == na
    if operador == "diferente":
        return nv != na
    if operador == "contem":
        return bool(na) and na in nv
    if operador == "nao_contem":
        return not (na and na in nv)
    if operador == "comeca_com":
        return bool(na) and nv.startswith(na)
    if operador == "nao_existe":
        return not valor.strip()
    if operador == "em_lista":
        return nv in {_normalizar(x) for x in alvo.split(",") if x.strip()}
    if operador in ("maior", "menor"):
        a, b = _numero(valor), _numero(alvo)
        if a is None or b is None:
            return False
        return a > b if operador == "maior" else a < b
    return bool(valor.strip())  # existe


def _render(texto: str, variaveis: dict) -> str:
    return _MARCADOR.sub(lambda m: str(variaveis.get(m.group(1), "")), texto or "")


def _saida_pergunta(etapa: dict, variaveis: dict) -> dict:
    return {"texto": _render(etapa["texto"], variaveis), "opcoes": list(etapa.get("opcoes") or [])}


def avancar(etapas: list[dict], estado: dict | None, entrada: str | None, contexto: dict | None = None) -> Resultado:
    """Executa o fluxo a partir do estado atual. Função pura: não grava
    nada — quem chama decide o que fazer com o resultado."""
    estado = dict(estado or {})
    variaveis = dict(estado.get("vars") or {})
    variaveis.update({k: v for k, v in (contexto or {}).items() if k not in variaveis})
    passo = int(estado.get("passo") or 0)
    resultado = Resultado()

    if estado.get("aguardando") and entrada is not None and passo < len(etapas):
        etapa = etapas[passo]
        resposta = (entrada or "").strip()
        opcoes = [str(o) for o in (etapa.get("opcoes") or [])]
        if opcoes:
            escolhida = None
            if resposta.isdigit() and 1 <= int(resposta) <= len(opcoes):
                escolhida = opcoes[int(resposta) - 1]
            else:
                for opcao in opcoes:
                    if _normalizar(opcao) == _normalizar(resposta):
                        escolhida = opcao
            if escolhida is None:
                resultado.saidas.append({"texto": "Não entendi. Escolha uma das opções:", "opcoes": []})
                resultado.saidas.append(_saida_pergunta(etapa, variaveis))
                resultado.estado = {**estado, "vars": variaveis}
                return resultado
            resposta = escolhida
        variaveis[etapa["variavel"]] = resposta
        passo += 1
        estado["aguardando"] = False

    executados = 0
    while passo < len(etapas):
        executados += 1
        if executados > LIMITE_PASSOS_POR_RODADA:
            resultado.loop = True
            resultado.acao = "fim"
            break
        etapa = etapas[passo]
        tipo = etapa.get("tipo")
        if tipo == "mensagem":
            resultado.saidas.append({"texto": _render(etapa["texto"], variaveis), "opcoes": []})
            passo += 1
        elif tipo == "pergunta":
            resultado.saidas.append(_saida_pergunta(etapa, variaveis))
            resultado.estado = {**estado, "passo": passo, "vars": variaveis, "aguardando": True}
            return resultado
        elif tipo == "memoria":
            variaveis[etapa["variavel"]] = _render(str(etapa.get("valor") or ""), variaveis)
            passo += 1
        elif tipo == "tag":
            resultado.tags.append(str(etapa["tag"]).strip())
            passo += 1
        elif tipo == "condicao":
            valor = str(variaveis.get(etapa.get("variavel"), "") or "")
            alvo = str(etapa.get("valor") or "")
            verdadeiro = _avaliar(etapa.get("operador"), valor, _render(alvo, variaveis))
            destino = etapa.get("ir_para") if verdadeiro else etapa.get("senao_ir_para")
            passo = (destino - 1) if isinstance(destino, int) and destino >= 1 else passo + 1
        elif tipo == "handoff":
            if str(etapa.get("texto") or "").strip():
                resultado.saidas.append({"texto": _render(etapa["texto"], variaveis), "opcoes": []})
            resultado.acao, resultado.fila_id = "handoff", etapa.get("fila")
            resultado.destino = etapa.get("destino") or "fila"
            resultado.exige_liberacao = bool(etapa.get("liberacao")) and resultado.destino == "sede"
            passo = len(etapas)
            break
        elif tipo == "notificar":
            resultado.notificacoes.append(_render(etapa["texto"], variaveis))
            passo += 1
        elif tipo == "encerrar":
            if str(etapa.get("texto") or "").strip():
                resultado.saidas.append({"texto": _render(etapa["texto"], variaveis), "opcoes": []})
            resultado.acao = "encerrar"
            passo = len(etapas)
            break
        else:
            passo += 1
    if resultado.acao is None:
        resultado.acao = "fim"
    resultado.estado = {**estado, "passo": passo, "vars": variaveis, "aguardando": False, "terminado": True}
    return resultado


def simular(etapas: list[dict], entradas: list[str], contexto: dict | None = None, filas_validas: set[str] | None = None) -> dict:
    erros = validar_etapas(etapas, filas_validas)
    conversa: list[dict] = []
    if erros:
        return {"ok": False, "erros": erros, "conversa": conversa, "final": None, "memoria": {}}
    estado: dict = {}
    avisos_sede: list[str] = []
    resultado = avancar(etapas, estado, None, contexto)
    fila_entradas = list(entradas or [])
    rodadas = 0
    while True:
        rodadas += 1
        for saida in resultado.saidas:
            conversa.append({"de": "robo", **saida})
        for aviso in resultado.notificacoes:
            avisos_sede.append(aviso)
            conversa.append({"de": "sistema", "texto": f"(aviso para a Sede) {aviso}"})
        if resultado.loop:
            erros.append("O fluxo entrou em repetição sem fim (confira as condições 'ir para').")
            break
        if not resultado.estado.get("aguardando"):
            break
        if not fila_entradas:
            conversa.append({"de": "sistema", "texto": "(simulação parou: o robô está esperando uma resposta)"})
            break
        if rodadas > 60:
            erros.append("A simulação passou de 60 respostas.")
            break
        entrada = fila_entradas.pop(0)
        conversa.append({"de": "cliente", "texto": entrada})
        resultado = avancar(etapas, resultado.estado, entrada, contexto)
    if resultado.acao == "handoff" and resultado.destino == "sede":
        resultado_final = "Vai direto para a Sede" + (" e espera a liberação dela" if resultado.exige_liberacao else "")
    else:
        resultado_final = "Passa para um atendente"
    final = {"handoff": resultado_final, "encerrar": "Encerra o atendimento", "fim": "Fim das etapas (passa para um atendente)"}.get(resultado.acao or "", "Aguardando resposta")
    if resultado.estado.get("aguardando"):
        final = "Aguardando resposta do cliente"
    return {
        "ok": not erros, "erros": erros, "conversa": conversa, "final": final,
        "memoria": resultado.estado.get("vars", {}), "tags": resultado.tags,
        "avisos_sede": avisos_sede,
    }


class FluxosMixin:
    def _filas_ids(self, empresa_id: str) -> set[str]:
        return {f["id"] for f in self.banco.todos("SELECT id FROM filas WHERE empresa_id=? AND ativa=1", (empresa_id,))}

    @staticmethod
    def _fluxo_publico(linha: dict) -> dict:
        return {**linha, "etapas": json.loads(linha["etapas"] or "[]"), "simulado_ok": bool(linha["simulado_ok"])}

    def listar_fluxos(self, ator: Ator) -> list[dict]:
        ator.exigir("fluxos", "ver")
        return [self._fluxo_publico(f) for f in self.banco.todos(
            "SELECT * FROM fluxos WHERE empresa_id=? ORDER BY status='rascunho', nome", (ator.empresa,))]

    def obter_fluxo(self, ator: Ator, fluxo_id: str) -> dict:
        ator.exigir("fluxos", "ver")
        linha = self.banco.um("SELECT * FROM fluxos WHERE id=? AND empresa_id=?", (fluxo_id, ator.empresa))
        if not linha:
            raise NaoEncontrado("Fluxo não encontrado.")
        return self._fluxo_publico(linha)

    def salvar_fluxo(self, ator: Ator, dados: dict, fluxo_id: str | None = None) -> dict:
        ator.exigir("fluxos", "editar" if fluxo_id else "criar")
        nome = _texto(dados.get("nome"), "nome do fluxo", maximo=80)
        gatilho = dados.get("gatilho_tipo") or "manual"
        if gatilho not in GATILHOS:
            raise ErroNegocio("Gatilho inválido.")
        valor = (dados.get("gatilho_valor") or "").strip() or None
        if gatilho == "palavra_chave" and not valor:
            raise ErroNegocio("Informe a palavra-chave que inicia o fluxo.")
        etapas = dados.get("etapas") or []
        if not isinstance(etapas, list):
            raise ErroNegocio("Etapas inválidas.")
        erros = validar_etapas(etapas, self._filas_ids(ator.empresa)) if etapas else []
        if erros:
            raise ErroNegocio(" ".join(erros[:3]))
        texto_etapas = json.dumps(etapas, ensure_ascii=False)
        if fluxo_id:
            atual = self.obter_fluxo(ator, fluxo_id)
            mudou = json.dumps(atual["etapas"], ensure_ascii=False) != texto_etapas or atual["gatilho_tipo"] != gatilho or atual["gatilho_valor"] != valor
            status = "rascunho" if mudou else atual["status"]
            self.banco.executar(
                "UPDATE fluxos SET nome=?, gatilho_tipo=?, gatilho_valor=?, etapas=?, status=?, simulado_ok=CASE WHEN ? THEN 0 ELSE simulado_ok END, atualizado_em=? WHERE id=?",
                (nome, gatilho, valor, texto_etapas, status, 1 if mudou else 0, agora(), fluxo_id),
            )
        else:
            fluxo_id = novo_id()
            self.banco.executar(
                "INSERT INTO fluxos(id, empresa_id, nome, gatilho_tipo, gatilho_valor, etapas, status, atualizado_em) VALUES (?,?,?,?,?,?,?,?)",
                (fluxo_id, ator.empresa, nome, gatilho, valor, texto_etapas, "rascunho", agora()),
            )
        self.auditar(ator, "fluxo.salvar", fluxo_id, {"nome": nome})
        return self.obter_fluxo(ator, fluxo_id)

    def simular_fluxo(self, ator: Ator, fluxo_id: str | None, etapas: list | None, entradas: list[str], como: dict | None = None) -> dict:
        ator.exigir("fluxos", "simular")
        fluxo = self.obter_fluxo(ator, fluxo_id) if fluxo_id else None
        usar = etapas if etapas is not None else (fluxo["etapas"] if fluxo else [])
        contexto = {"nome": "Cliente", "empresa": self.obter_config(ator.empresa)["empresa_nome"], "canal": "site",
                    "unidade": "", "unidade_tipo": "", "igreja": "", "origem": "sede"}
        for chave in ("unidade", "unidade_tipo", "igreja", "origem", "canal"):  # "simular como": pessoa de uma igreja, setor ou da Sede
            valor = str((como or {}).get(chave) or "").strip()[:60]
            if valor:
                contexto[chave] = valor
        resultado = simular(usar, [str(e) for e in (entradas or [])][:60], contexto, self._filas_ids(ator.empresa))
        if fluxo and resultado["ok"] and etapas is None:
            self.banco.executar("UPDATE fluxos SET simulado_ok=1 WHERE id=?", (fluxo["id"],))
        return resultado

    def publicar_fluxo(self, ator: Ator, fluxo_id: str, publicar: bool = True) -> dict:
        ator.exigir("fluxos", "publicar")
        fluxo = self.obter_fluxo(ator, fluxo_id)
        if publicar:
            if not fluxo["simulado_ok"]:
                raise ErroNegocio("Rode a simulação sem erros antes de publicar.")
            erros = validar_etapas(fluxo["etapas"], self._filas_ids(ator.empresa))
            if erros:
                raise ErroNegocio(" ".join(erros[:3]))
            self.banco.executar("UPDATE fluxos SET status='publicado', publicado_em=? WHERE id=?", (agora(), fluxo_id))
        else:
            self.banco.executar("UPDATE fluxos SET status='rascunho' WHERE id=?", (fluxo_id,))
        self.auditar(ator, "fluxo.publicar" if publicar else "fluxo.despublicar", fluxo_id)
        return self.obter_fluxo(ator, fluxo_id)

    def _fluxo_para_iniciar(self, empresa_id: str, texto: str | None) -> dict | None:
        publicados = self.banco.todos(
            "SELECT * FROM fluxos WHERE empresa_id=? AND status='publicado' ORDER BY publicado_em", (empresa_id,))
        normal = _normalizar(texto or "")
        if normal:
            for fluxo in publicados:
                if fluxo["gatilho_tipo"] == "palavra_chave" and _normalizar(fluxo["gatilho_valor"] or "") in normal:
                    return fluxo
        for fluxo in publicados:
            if fluxo["gatilho_tipo"] == "sempre":
                return fluxo
        return None
